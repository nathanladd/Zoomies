import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.database import async_session
from server.models import Game, Quiz, QuizQuestion, Player, QuestionAnswerStat
from server.game.engine import GameEngine
from server.websocket.manager import manager

# Active game engines: game_id -> GameEngine
active_games: dict[int, GameEngine] = {}


# Sentinel answer_text used in question_answer_stats to record a player who
# was shown the question but never picked any choice before time expired.
NO_RESPONSE_KEY = "__no_response__"


def _stat_key(text: str) -> str:
    """Strip the leading "X) " label from a display choice so the saved stat
    matches the raw answer text shown in the question editor."""
    if not text:
        return text
    if len(text) > 3 and text[0] in "ABCD" and text[1:3] == ") ":
        return text[3:]
    return text


async def _record_answer_stat(question_id: int, answer_text: str, delta: int = 1) -> None:
    """Increment the cumulative tally for (question_id, answer_text) by ``delta``."""
    if not answer_text or delta <= 0:
        return
    async with async_session() as db:
        stmt = select(QuestionAnswerStat).where(
            QuestionAnswerStat.question_id == question_id,
            QuestionAnswerStat.answer_text == answer_text,
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.times_chosen += delta
        else:
            db.add(QuestionAnswerStat(
                question_id=question_id,
                answer_text=answer_text,
                times_chosen=delta,
            ))
        try:
            await db.commit()
        except Exception:
            await db.rollback()


async def load_engine(game_id: int, db: AsyncSession) -> GameEngine:
    """Initialize a Rudi game engine for the given game."""
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
            "randomize_answers": q.randomize_answers,
            "correct_index": q.correct_index,
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
    """Handle a student WebSocket connection for Rudi."""
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

        # Reuse an existing Player row for this (game_id, name) if one exists —
        # this is what a mid-game WS reconnect looks like. A fresh join gets a
        # fresh row. We match case-insensitively on name so a flaky reconnect
        # with slightly different casing still rejoins the same player.
        is_reconnect = False
        async with async_session() as db:
            existing = (await db.execute(
                select(Player).where(
                    Player.game_id == game_id,
                    Player.name == name,
                )
            )).scalar_one_or_none()
            if existing is not None:
                player_id = existing.id
                is_reconnect = True
            else:
                player = Player(game_id=game_id, name=name)
                db.add(player)
                await db.commit()
                await db.refresh(player)
                player_id = player.id

        # If this player already has a live WS in the manager, drop the old
        # socket so the manager only ever holds one connection per player_id.
        old_ws = manager.student_connections.get(game_id, {}).get(player_id)
        if old_ws is not None and old_ws is not ws:
            try:
                await old_ws.close(code=4003, reason="Replaced by reconnect")
            except Exception:
                pass

        # Register with connection manager (skip accept — already accepted above)
        if game_id not in manager.student_connections:
            manager.student_connections[game_id] = {}
        manager.student_connections[game_id][player_id] = ws
        if is_reconnect and player_id in engine.players:
            # Preserve the in-memory score on reconnect; no need to re-announce.
            join_info = {
                "player_id": player_id,
                "name": name,
                "player_count": len(engine.players),
            }
            print(f"[WS-STUDENT] Player {player_id} ({name}) reconnected to game {game_id}")
        else:
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

                    # Notify instructor which player answered and whether correct
                    await manager.send_to_instructor(game_id, {
                        "type": "player_answered",
                        "player_id": player_id,
                        "name": engine.players[player_id]["name"],
                        "is_correct": bool(result.get("is_correct", False)),
                    })

                    # Persist a cumulative tally of how often this answer
                    # text has been chosen for this question across all games.
                    # Fire-and-forget so simultaneous submissions don't
                    # serialize on this write.
                    q_state = engine.current_question
                    if q_state is not None:
                        asyncio.create_task(_record_answer_stat(
                            q_state.question_id,
                            _stat_key(result.get("choice", "")),
                        ))

                    # If every player has answered, reveal early instead of
                    # waiting for the timer to expire.
                    if total > 0 and answered >= total and engine.status == "active":
                        await _reveal_and_broadcast(game_id, engine)

                else:
                    await manager.send_to_student(game_id, player_id, {
                        "type": "error",
                        "message": result["error"],
                    })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS-STUDENT] Error: {e}")
        import traceback
        traceback.print_exc()
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
    """Handle the instructor WebSocket connection for Rudi."""
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
                    engine.timer_task = timer_task

            elif msg_type == "reveal":
                await _reveal_and_broadcast(game_id, engine)

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

            # 5 Hz is plenty for the visible timer and halves WS chatter vs 10 Hz.
            await asyncio.sleep(0.2)

        # Time expired — auto-reveal
        if engine.current_question and engine.status == "active":
            await _reveal_and_broadcast(game_id, engine)

    except asyncio.CancelledError:
        pass


async def _reveal_and_broadcast(game_id: int, engine: GameEngine) -> None:
    """Cancel the running per-question timer (if any) and broadcast the reveal.

    Idempotent: only fires when the engine is still in the ``active`` state, so
    early all-answered reveal, the instructor reveal button, and timer expiry
    can all call this safely without double-broadcasting.
    """
    if engine.status != "active":
        return
    timer_task = getattr(engine, "timer_task", None)
    # If we're being called from inside the timer task itself (the natural
    # expiry path), do NOT cancel it — that schedules a CancelledError which
    # fires at the next await (inside on_reveal or broadcast_to_all) and
    # the question_end message never reaches the clients, leaving the timer
    # visibly frozen at the last tick. The loop is already exiting anyway.
    current = asyncio.current_task()
    if (
        timer_task is not None
        and not timer_task.done()
        and timer_task is not current
    ):
        timer_task.cancel()
    engine.timer_task = None

    # Snapshot the question + per-player answer dict before on_reveal flips
    # state, so we can record one "no response" per player who never picked.
    q_state = engine.current_question
    no_response_count = 0
    no_response_qid: int | None = None
    if q_state is not None:
        no_response_qid = q_state.question_id
        no_response_count = max(0, len(engine.players) - len(q_state.answers))

    reveal_info = await engine.on_reveal()

    await manager.broadcast_to_all(game_id, {
        "type": "question_end",
        **reveal_info,
    })

    # Persist the no-response tally as a fire-and-forget background task.
    # We must NOT await this here: when this function is invoked from inside
    # the per-question timer loop (the natural-expiry path), the loop has
    # just been told to cancel itself a few lines above. Any extra awaited
    # IO before the broadcast would let that pending CancelledError fire
    # mid-flight and the question_end message would never reach the clients,
    # which manifests as the timer freezing at the last tick.
    if no_response_qid is not None and no_response_count > 0:
        asyncio.create_task(
            _record_answer_stat(no_response_qid, NO_RESPONSE_KEY, no_response_count)
        )
