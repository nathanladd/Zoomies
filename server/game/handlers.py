import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.database import async_session
from server.models import Game, Quiz, QuizQuestion, Player
from server.game.engine import GameEngine
from server.websocket.manager import manager

# Active game engines: game_id -> GameEngine
active_games: dict[int, GameEngine] = {}


async def load_engine(game_id: int, db: AsyncSession) -> GameEngine:
    """Initialize a Zündpunkt game engine for the given game."""
    game = await db.get(Game, game_id)
    if not game:
        raise ValueError("Game not found")
    quiz = await db.get(Quiz, game.quiz_id)
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

    engine = GameEngine(
        game_id=game_id,
        quiz_name=quiz.name,
        questions=questions,
        randomize_order=quiz.randomize_order,
    )
    active_games[game_id] = engine
    return engine


def get_engine(game_id: int) -> GameEngine | None:
    return active_games.get(game_id)


async def handle_student_ws(ws: WebSocket, game_id: int) -> None:
    """Handle a student WebSocket connection for Zündpunkt."""
    print(f"[WS-STUDENT] Connection attempt for game {game_id}")
    engine = get_engine(game_id)
    if not engine:
        print(f"[WS-STUDENT] No active engine for game {game_id}, closing")
        await ws.accept()
        await ws.close(code=4000, reason="No active engine for this game")
        return

    await ws.accept()
    print(f"[WS-STUDENT] Accepted for game {game_id}")
    player_id: int | None = None

    try:
        # Wait for join message
        raw = await ws.receive_text()
        data = json.loads(raw)
        print(f"[WS-STUDENT] Received: {data}")

        if data.get("type") != "player_join":
            await ws.close(code=4001, reason="Expected player_join message")
            return

        name = data.get("name", "").strip()
        if not name:
            await ws.close(code=4002, reason="Name is required")
            return

        # Create player in DB (short-lived DB session via async_session factory).
        async with async_session() as db:
            player = Player(game_id=game_id, name=name)
            db.add(player)
            await db.commit()
            await db.refresh(player)
            player_id = player.id

        # Register with connection manager (skip accept — already accepted above)
        if game_id not in manager.student_connections:
            manager.student_connections[game_id] = {}
        manager.student_connections[game_id][player_id] = ws
        join_info = await engine.on_player_join(player_id, name)
        print(f"[WS-STUDENT] Player {player_id} ({name}) joined game {game_id}")

        # Confirm join to this student
        await manager.send_to_student(game_id, player_id, {
            "type": "join_confirmed",
            "player_id": player_id,
            "name": name,
        })

        # Broadcast to all
        await manager.broadcast_to_all(game_id, {
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
                    # Update the player's cumulative score (no per-answer persistence)
                    async with async_session() as db:
                        player_obj = await db.get(Player, player_id)
                        if player_obj:
                            player_obj.total_score = engine.players[player_id]["score"]
                            await db.commit()

                    # Confirm to student
                    await manager.send_to_student(game_id, player_id, {
                        "type": "answer_confirmed",
                        "choice": choice,
                        "locked": True,
                    })

                    # Update instructor with answer count
                    answered, total = engine.get_answer_count()
                    await manager.send_to_instructor(game_id, {
                        "type": "answer_count",
                        "answered": answered,
                        "total": total,
                    })
                else:
                    await manager.send_to_student(game_id, player_id, {
                        "type": "error",
                        "message": result["error"],
                    })

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if player_id is not None:
            manager.disconnect_student(game_id, player_id)
            # Notify others
            if engine and player_id in engine.players:
                name = engine.players[player_id]["name"]
                await manager.broadcast_to_all(game_id, {
                    "type": "player_left",
                    "player_id": player_id,
                    "name": name,
                    "player_count": len(engine.players) - 1,
                })


async def _update_game_status(game_id: int, status: str) -> None:
    """Update a game's status row in the DB using a short-lived DB session."""
    async with async_session() as db:
        game = await db.get(Game, game_id)
        if game:
            game.status = status
            if status == "active" and not game.started_at:
                game.started_at = datetime.now(timezone.utc)
            if status == "finished" and not game.ended_at:
                game.ended_at = datetime.now(timezone.utc)
            await db.commit()


async def handle_instructor_ws(ws: WebSocket, game_id: int) -> None:
    """Handle the instructor WebSocket connection for Zündpunkt."""
    print(f"[WS-INSTR] Connection attempt for game {game_id}")
    engine = get_engine(game_id)
    if not engine:
        print(f"[WS-INSTR] No active engine for game {game_id}")
        await ws.accept()
        await ws.close(code=4000, reason="No active engine for this game")
        return

    await manager.connect_instructor(game_id, ws)
    print(f"[WS-INSTR] Connected for game {game_id}")
    timer_task: asyncio.Task | None = None

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")
            print(f"[WS-INSTR] Received: {msg_type}")

            if msg_type == "start_game":
                start_info = await engine.on_start()
                await _update_game_status(game_id, "active")
                student_count = manager.get_student_count(game_id)
                print(f"[WS-INSTR] Broadcasting game_start to {student_count} students")

                await manager.broadcast_to_all(game_id, {
                    "type": "game_start",
                    **start_info,
                })

            elif msg_type == "next_question":
                q_info = await engine.on_next_question()
                print(f"[WS-INSTR] next_question result: {'None (no more)' if q_info is None else 'Q' + str(q_info.get('index', '?'))}")
                if q_info is None:
                    # No more questions — end game
                    end_info = await engine.on_end()
                    await _update_game_status(game_id, "finished")

                    await manager.broadcast_to_all(game_id, {
                        "type": "game_end",
                        **end_info,
                    })
                    active_games.pop(game_id, None)
                    break
                else:
                    student_count = manager.get_student_count(game_id)
                    print(f"[WS-INSTR] Broadcasting question_start to {student_count} students, choices={q_info.get('choices', [])}")
                    await manager.broadcast_to_all(game_id, {
                        "type": "question_start",
                        **q_info,
                    })

                    # Send correct answer to instructor only
                    correct = engine.current_question.correct_display if engine.current_question else ""
                    await manager.send_to_instructor(game_id, {
                        "type": "question_answer",
                        "correct_answer": correct,
                    })

                    # Start timer loop for points updates and eliminations
                    if timer_task and not timer_task.done():
                        timer_task.cancel()
                    timer_task = asyncio.create_task(
                        _question_timer_loop(game_id, engine)
                    )

            elif msg_type == "reveal":
                if timer_task and not timer_task.done():
                    timer_task.cancel()
                reveal_info = await engine.on_reveal()
                await manager.broadcast_to_all(game_id, {
                    "type": "question_end",
                    **reveal_info,
                })

            elif msg_type == "end_game":
                if timer_task and not timer_task.done():
                    timer_task.cancel()
                end_info = await engine.on_end()
                await _update_game_status(game_id, "finished")

                await manager.broadcast_to_all(game_id, {
                    "type": "game_end",
                    **end_info,
                })
                active_games.pop(game_id, None)
                break

            elif msg_type == "get_status":
                await manager.send_to_instructor(game_id, {
                    "type": "status",
                    **engine.get_status(),
                })

    except WebSocketDisconnect:
        print(f"[WS-INSTR] Instructor disconnected from game {game_id}")
    except Exception as e:
        print(f"[WS-INSTR] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if timer_task and not timer_task.done():
            timer_task.cancel()
        manager.disconnect_instructor(game_id)


async def _question_timer_loop(game_id: int, engine: GameEngine) -> None:
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
                await manager.broadcast_to_all(game_id, {
                    "type": "choice_eliminated",
                    "choice": eliminated,
                    "remaining_choices": remaining,
                })

            # Send points update
            await manager.broadcast_to_all(game_id, {
                "type": "points_update",
                "current_points": engine.current_question.current_points,
                "time_remaining_ms": engine.current_question.time_remaining_ms,
            })

            await asyncio.sleep(0.1)  # 100ms interval

        # Time expired — auto-reveal
        if engine.current_question and engine.status == "active":
            reveal_info = await engine.on_reveal()
            await manager.broadcast_to_all(game_id, {
                "type": "question_end",
                **reveal_info,
            })

    except asyncio.CancelledError:
        pass
