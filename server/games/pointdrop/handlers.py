import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.database import async_session
from server.models import GameSession, Quiz, QuizQuestion, Player, Answer
from server.games.pointdrop.engine import PointDropEngine
from server.websocket.manager import manager

# Active game engines: session_id -> PointDropEngine
active_games: dict[int, PointDropEngine] = {}


async def create_game(session_id: int, db: AsyncSession) -> PointDropEngine:
    """Initialize a PointDrop engine for the given session."""
    session = await db.get(GameSession, session_id)
    if not session:
        raise ValueError("Session not found")
    quiz = await db.get(Quiz, session.quiz_id)
    if not quiz:
        raise ValueError("Quiz not found")

    qq_stmt = (
        select(QuizQuestion)
        .where(QuizQuestion.quiz_id == quiz.id)
        .order_by(QuizQuestion.position)
    )
    result = await db.execute(qq_stmt)
    quiz_questions = result.scalars().all()

    questions: list[dict[str, Any]] = []
    for qq in quiz_questions:
        q = qq.question
        if not q:
            continue
        questions.append({
            "id": q.id,
            "text": q.text,
            "image_filename": q.image_filename,
            "correct_answer": q.correct_answer,
            "wrong_answer_1": q.wrong_answer_1,
            "wrong_answer_2": q.wrong_answer_2,
            "wrong_answer_3": q.wrong_answer_3,
            "time_seconds": q.time_seconds,
            "question_type": q.question_type,
        })

    engine = PointDropEngine(
        session_id=session_id,
        quiz_name=quiz.name,
        questions=questions,
        randomize_order=quiz.randomize_order,
    )
    active_games[session_id] = engine
    return engine


def get_game(session_id: int) -> PointDropEngine | None:
    return active_games.get(session_id)


async def handle_student_ws(ws: WebSocket, session_id: int) -> None:
    """Handle a student WebSocket connection for PointDrop."""
    engine = get_game(session_id)
    if not engine:
        await ws.close(code=4000, reason="No active game for this session")
        return

    player_id: int | None = None

    try:
        # Wait for join message
        raw = await ws.receive_text()
        data = json.loads(raw)

        if data.get("type") != "player_join":
            await ws.close(code=4001, reason="Expected player_join message")
            return

        name = data.get("name", "").strip()
        if not name:
            await ws.close(code=4002, reason="Name is required")
            return

        # Create player in DB (short-lived session)
        async with async_session() as db:
            player = Player(session_id=session_id, name=name)
            db.add(player)
            await db.commit()
            await db.refresh(player)
            player_id = player.id

        # Register with connection manager and engine
        await manager.connect_student(session_id, player_id, ws)
        join_info = await engine.on_player_join(player_id, name)

        # Confirm join to this student
        await manager.send_to_student(session_id, player_id, {
            "type": "join_confirmed",
            "player_id": player_id,
            "name": name,
        })

        # Broadcast to all
        await manager.broadcast_to_all(session_id, {
            "type": "player_joined",
            **join_info,
        })

        # Listen for messages
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "submit_answer":
                choice = msg.get("choice", "")
                elapsed_ms = msg.get("elapsed_ms", 0)
                result = await engine.on_submit_answer(player_id, choice, elapsed_ms)

                if "error" not in result:
                    # Save answer and update score (short-lived session)
                    async with async_session() as db:
                        answer = Answer(
                            player_id=player_id,
                            question_id=engine.current_question.question_id if engine.current_question else 0,
                            session_id=session_id,
                            selected_answer=result.get("selected_answer_text"),
                            response_time_ms=elapsed_ms,
                            points_earned=result["points"],
                            is_correct=result["is_correct"],
                        )
                        db.add(answer)
                        player_obj = await db.get(Player, player_id)
                        if player_obj:
                            player_obj.total_score = engine.players[player_id]["score"]
                        await db.commit()

                    # Confirm to student
                    await manager.send_to_student(session_id, player_id, {
                        "type": "answer_confirmed",
                        "choice": choice,
                        "locked": True,
                    })

                    # Update instructor with answer count
                    answered, total = engine.get_answer_count()
                    await manager.send_to_instructor(session_id, {
                        "type": "answer_count",
                        "answered": answered,
                        "total": total,
                    })
                else:
                    await manager.send_to_student(session_id, player_id, {
                        "type": "error",
                        "message": result["error"],
                    })

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if player_id is not None:
            manager.disconnect_student(session_id, player_id)
            # Notify others
            if engine and player_id in engine.players:
                name = engine.players[player_id]["name"]
                await manager.broadcast_to_all(session_id, {
                    "type": "player_left",
                    "player_id": player_id,
                    "name": name,
                    "player_count": len(engine.players) - 1,
                })


async def _update_session_status(session_id: int, status: str) -> None:
    """Update a game session's status in the DB with a short-lived session."""
    async with async_session() as db:
        session = await db.get(GameSession, session_id)
        if session:
            session.status = status
            if status == "active" and not session.started_at:
                session.started_at = datetime.now(timezone.utc)
            if status == "finished" and not session.ended_at:
                session.ended_at = datetime.now(timezone.utc)
            await db.commit()


async def _update_session_q_index(session_id: int, q_index: int) -> None:
    """Update the current question index in the DB."""
    async with async_session() as db:
        session = await db.get(GameSession, session_id)
        if session:
            session.current_q_index = q_index
            await db.commit()


async def handle_instructor_ws(ws: WebSocket, session_id: int) -> None:
    """Handle the instructor WebSocket connection for PointDrop."""
    engine = get_game(session_id)
    if not engine:
        await ws.close(code=4000, reason="No active game for this session")
        return

    await manager.connect_instructor(session_id, ws)
    timer_task: asyncio.Task | None = None

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "start_game":
                start_info = await engine.on_start()
                await _update_session_status(session_id, "active")

                await manager.broadcast_to_all(session_id, {
                    "type": "game_start",
                    **start_info,
                })

            elif msg_type == "next_question":
                q_info = await engine.on_next_question()
                if q_info is None:
                    # No more questions — end game
                    end_info = await engine.on_end()
                    await _update_session_status(session_id, "finished")

                    await manager.broadcast_to_all(session_id, {
                        "type": "game_end",
                        **end_info,
                    })
                    active_games.pop(session_id, None)
                    break
                else:
                    await _update_session_q_index(session_id, engine.current_index)

                    await manager.broadcast_to_all(session_id, {
                        "type": "question_start",
                        **q_info,
                    })

                    # Start timer loop for points updates and eliminations
                    if timer_task and not timer_task.done():
                        timer_task.cancel()
                    timer_task = asyncio.create_task(
                        _question_timer_loop(session_id, engine)
                    )

            elif msg_type == "reveal":
                if timer_task and not timer_task.done():
                    timer_task.cancel()
                reveal_info = await engine.on_reveal()
                await manager.broadcast_to_all(session_id, {
                    "type": "question_end",
                    **reveal_info,
                })

            elif msg_type == "end_game":
                if timer_task and not timer_task.done():
                    timer_task.cancel()
                end_info = await engine.on_end()
                await _update_session_status(session_id, "finished")

                await manager.broadcast_to_all(session_id, {
                    "type": "game_end",
                    **end_info,
                })
                active_games.pop(session_id, None)
                break

            elif msg_type == "get_status":
                await manager.send_to_instructor(session_id, {
                    "type": "status",
                    **engine.get_status(),
                })

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if timer_task and not timer_task.done():
            timer_task.cancel()
        manager.disconnect_instructor(session_id)


async def _question_timer_loop(session_id: int, engine: PointDropEngine) -> None:
    """Background task that sends points updates and fires eliminations."""
    try:
        while engine.current_question and not engine.current_question.is_expired:
            # Check for eliminations
            eliminated = engine.check_elimination()
            if eliminated:
                remaining = [
                    c for c in engine.current_question.display_choices
                    if c not in engine.current_question.eliminated
                ]
                await manager.broadcast_to_all(session_id, {
                    "type": "choice_eliminated",
                    "choice": eliminated,
                    "remaining_choices": remaining,
                })

            # Send points update
            await manager.broadcast_to_all(session_id, {
                "type": "points_update",
                "current_points": engine.current_question.current_points,
                "time_remaining_ms": engine.current_question.time_remaining_ms,
            })

            await asyncio.sleep(0.1)  # 100ms interval

        # Time expired — auto-reveal
        if engine.current_question and engine.status == "active":
            reveal_info = await engine.on_reveal()
            await manager.broadcast_to_all(session_id, {
                "type": "question_end",
                **reveal_info,
            })

    except asyncio.CancelledError:
        pass
