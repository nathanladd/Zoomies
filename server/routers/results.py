from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from server.database import get_db
from server.models import GameSession, Player, Answer, Question
from server.schemas import (
    SessionResultRead, GameSessionRead, PlayerRead, AnswerRead,
    QuestionAnalytics, StudentHistory,
)

router = APIRouter(prefix="/api/results", tags=["results"])


@router.get("/session/{session_id}", response_model=SessionResultRead)
async def get_session_results(session_id: int, db: AsyncSession = Depends(get_db)):
    s = await db.get(GameSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")

    player_cnt = (await db.execute(
        select(func.count()).where(Player.session_id == s.id)
    )).scalar() or 0

    session_read = GameSessionRead(
        id=s.id, quiz_id=s.quiz_id, game_type=s.game_type,
        status=s.status, current_q_index=s.current_q_index,
        started_at=s.started_at, ended_at=s.ended_at,
        player_count=player_cnt,
        quiz_name=s.quiz.name if s.quiz else None,
    )

    players_stmt = select(Player).where(Player.session_id == session_id).order_by(Player.total_score.desc())
    players = (await db.execute(players_stmt)).scalars().all()

    answers_stmt = select(Answer).where(Answer.session_id == session_id)
    answers = (await db.execute(answers_stmt)).scalars().all()

    return SessionResultRead(
        session=session_read,
        players=[PlayerRead.model_validate(p) for p in players],
        answers=[AnswerRead.model_validate(a) for a in answers],
    )


@router.get("/questions", response_model=list[QuestionAnalytics])
async def get_question_analytics(
    topic_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    q_stmt = select(Question)
    if topic_id is not None:
        q_stmt = q_stmt.where(Question.topic_id == topic_id)
    questions = (await db.execute(q_stmt)).scalars().all()

    out: list[QuestionAnalytics] = []
    for q in questions:
        a_stmt = select(Answer).where(Answer.question_id == q.id)
        answers = (await db.execute(a_stmt)).scalars().all()
        total = len(answers)
        if total == 0:
            continue
        correct = sum(1 for a in answers if a.is_correct)
        avg_time = sum(a.response_time_ms for a in answers) / total
        out.append(QuestionAnalytics(
            question_id=q.id,
            question_text=q.text,
            times_asked=total,
            times_correct=correct,
            accuracy_pct=round(correct / total * 100, 1),
            avg_response_time_ms=round(avg_time, 0),
        ))

    out.sort(key=lambda x: x.accuracy_pct)
    return out


@router.get("/student/{student_name}", response_model=StudentHistory)
async def get_student_history(student_name: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Player).where(func.lower(Player.name) == student_name.lower()).order_by(Player.joined_at.desc())
    result = await db.execute(stmt)
    players = result.scalars().all()

    if not players:
        raise HTTPException(404, "No records found for this student")

    total_score = sum(p.total_score for p in players)
    avg_score = total_score / len(players) if players else 0

    return StudentHistory(
        name=student_name,
        sessions_played=len(players),
        total_score=total_score,
        avg_score=round(avg_score, 1),
        sessions=[PlayerRead.model_validate(p) for p in players],
    )


@router.get("/students", response_model=list[StudentHistory])
async def list_student_histories(db: AsyncSession = Depends(get_db)):
    stmt = select(Player.name, func.count().label("cnt"), func.sum(Player.total_score).label("total")).group_by(
        func.lower(Player.name)
    )
    result = await db.execute(stmt)
    rows = result.all()

    out: list[StudentHistory] = []
    for name, cnt, total in rows:
        out.append(StudentHistory(
            name=name,
            sessions_played=cnt,
            total_score=total or 0,
            avg_score=round((total or 0) / cnt, 1) if cnt else 0,
            sessions=[],
        ))
    out.sort(key=lambda x: x.total_score, reverse=True)
    return out
