from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from server.database import get_db
from server.models import GameSession, Quiz, Player
from server.schemas import GameSessionCreate, GameSessionRead, PlayerRead

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _session_to_read(s: GameSession, player_count: int = 0, quiz_name: str | None = None) -> GameSessionRead:
    return GameSessionRead(
        id=s.id, quiz_id=s.quiz_id,
        status=s.status,
        started_at=s.started_at, ended_at=s.ended_at,
        player_count=player_count, quiz_name=quiz_name,
    )


@router.get("", response_model=list[GameSessionRead])
async def list_sessions(
    quiz_id: int | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(GameSession).order_by(GameSession.id.desc())
    if quiz_id is not None:
        stmt = stmt.where(GameSession.quiz_id == quiz_id)
    if status is not None:
        stmt = stmt.where(GameSession.status == status)
    result = await db.execute(stmt)
    sessions = result.scalars().all()

    out: list[GameSessionRead] = []
    for s in sessions:
        cnt = (await db.execute(
            select(func.count()).where(Player.session_id == s.id)
        )).scalar() or 0
        quiz_name = s.quiz.name if s.quiz else None
        out.append(_session_to_read(s, cnt, quiz_name))
    return out


@router.get("/{session_id}", response_model=GameSessionRead)
async def get_session(session_id: int, db: AsyncSession = Depends(get_db)):
    s = await db.get(GameSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    cnt = (await db.execute(
        select(func.count()).where(Player.session_id == s.id)
    )).scalar() or 0
    quiz_name = s.quiz.name if s.quiz else None
    return _session_to_read(s, cnt, quiz_name)


@router.post("", response_model=GameSessionRead, status_code=201)
async def create_session(body: GameSessionCreate, db: AsyncSession = Depends(get_db)):
    quiz = await db.get(Quiz, body.quiz_id)
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    s = GameSession(quiz_id=body.quiz_id)
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return _session_to_read(s, 0, quiz.name)


@router.put("/{session_id}/start", response_model=GameSessionRead)
async def start_session(session_id: int, db: AsyncSession = Depends(get_db)):
    s = await db.get(GameSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    if s.status != "waiting":
        raise HTTPException(400, "Session is not in waiting state")
    s.status = "active"
    s.started_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(s)
    cnt = (await db.execute(
        select(func.count()).where(Player.session_id == s.id)
    )).scalar() or 0
    return _session_to_read(s, cnt, s.quiz.name if s.quiz else None)


@router.put("/{session_id}/end", response_model=GameSessionRead)
async def end_session(session_id: int, db: AsyncSession = Depends(get_db)):
    s = await db.get(GameSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    s.status = "finished"
    s.ended_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(s)
    cnt = (await db.execute(
        select(func.count()).where(Player.session_id == s.id)
    )).scalar() or 0
    return _session_to_read(s, cnt, s.quiz.name if s.quiz else None)


@router.get("/{session_id}/players", response_model=list[PlayerRead])
async def list_players(session_id: int, db: AsyncSession = Depends(get_db)):
    s = await db.get(GameSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    stmt = select(Player).where(Player.session_id == session_id).order_by(Player.total_score.desc())
    result = await db.execute(stmt)
    return [PlayerRead.model_validate(p) for p in result.scalars().all()]


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: int, db: AsyncSession = Depends(get_db)):
    s = await db.get(GameSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    await db.delete(s)
    await db.commit()
