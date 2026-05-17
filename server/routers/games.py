import secrets
import string
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from server.auth import require_auth
from server.database import get_db
from server.models import Game, Quiz, Player
from server.schemas import GameCreate, GameRead, PlayerRead

router = APIRouter(prefix="/api/games", tags=["games"], dependencies=[Depends(require_auth)])

# Exclude visually ambiguous characters: O, I, L
_CODE_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ"


async def _unique_join_code(db: AsyncSession) -> str:
    while True:
        code = "".join(secrets.choice(_CODE_CHARS) for _ in range(6))
        existing = (await db.execute(
            select(Game).where(Game.join_code == code)
        )).scalar_one_or_none()
        if existing is None:
            return code


def _game_to_read(g: Game, player_count: int = 0, quiz_name: str | None = None) -> GameRead:
    return GameRead(
        id=g.id, join_code=g.join_code, quiz_id=g.quiz_id,
        status=g.status,
        started_at=g.started_at, ended_at=g.ended_at,
        player_count=player_count, quiz_name=quiz_name,
    )


@router.get("", response_model=list[GameRead])
async def list_games(
    quiz_id: int | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Game).order_by(Game.id.desc())
    if quiz_id is not None:
        stmt = stmt.where(Game.quiz_id == quiz_id)
    if status is not None:
        stmt = stmt.where(Game.status == status)
    result = await db.execute(stmt)
    games = result.scalars().all()

    out: list[GameRead] = []
    for g in games:
        cnt = (await db.execute(
            select(func.count()).where(Player.game_id == g.id)
        )).scalar() or 0
        quiz_name = g.quiz.name if g.quiz else None
        out.append(_game_to_read(g, cnt, quiz_name))
    return out


@router.get("/{game_id}", response_model=GameRead)
async def get_game(game_id: int, db: AsyncSession = Depends(get_db)):
    g = await db.get(Game, game_id)
    if not g:
        raise HTTPException(404, "Game not found")
    cnt = (await db.execute(
        select(func.count()).where(Player.game_id == g.id)
    )).scalar() or 0
    quiz_name = g.quiz.name if g.quiz else None
    return _game_to_read(g, cnt, quiz_name)


@router.post("", response_model=GameRead, status_code=201)
async def create_game(body: GameCreate, db: AsyncSession = Depends(get_db)):
    quiz = await db.get(Quiz, body.quiz_id)
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    join_code = await _unique_join_code(db)
    g = Game(quiz_id=body.quiz_id, join_code=join_code)
    db.add(g)
    await db.commit()
    await db.refresh(g)
    return _game_to_read(g, 0, quiz.name)


@router.put("/{game_id}/start", response_model=GameRead)
async def start_game(game_id: int, db: AsyncSession = Depends(get_db)):
    g = await db.get(Game, game_id)
    if not g:
        raise HTTPException(404, "Game not found")
    if g.status != "waiting":
        raise HTTPException(400, "Game is not in waiting state")
    g.status = "active"
    g.started_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(g)
    cnt = (await db.execute(
        select(func.count()).where(Player.game_id == g.id)
    )).scalar() or 0
    return _game_to_read(g, cnt, g.quiz.name if g.quiz else None)


@router.put("/{game_id}/end", response_model=GameRead)
async def end_game(game_id: int, db: AsyncSession = Depends(get_db)):
    g = await db.get(Game, game_id)
    if not g:
        raise HTTPException(404, "Game not found")
    g.status = "finished"
    g.ended_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(g)
    cnt = (await db.execute(
        select(func.count()).where(Player.game_id == g.id)
    )).scalar() or 0
    return _game_to_read(g, cnt, g.quiz.name if g.quiz else None)


@router.get("/{game_id}/players", response_model=list[PlayerRead])
async def list_players(game_id: int, db: AsyncSession = Depends(get_db)):
    g = await db.get(Game, game_id)
    if not g:
        raise HTTPException(404, "Game not found")
    stmt = select(Player).where(Player.game_id == game_id).order_by(Player.total_score.desc())
    result = await db.execute(stmt)
    return [PlayerRead.model_validate(p) for p in result.scalars().all()]


@router.delete("/{game_id}", status_code=204)
async def delete_game(game_id: int, db: AsyncSession = Depends(get_db)):
    g = await db.get(Game, game_id)
    if not g:
        raise HTTPException(404, "Game not found")
    await db.delete(g)
    await db.commit()
