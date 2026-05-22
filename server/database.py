from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from server.config import DATABASE_URL, DATA_DIR, MEDIA_DIR


class Base(DeclarativeBase):
    pass


engine = create_async_engine(DATABASE_URL, echo=False)


@event.listens_for(engine.sync_engine, "connect")
def _enable_sqlite_fk(dbapi_connection, connection_record):  # noqa: ARG001
    """SQLite ignores ON DELETE CASCADE unless foreign keys are explicitly enabled per connection."""
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:
        pass


async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        from server.models import (  # noqa: F401
            Topic, Question, Quiz, QuizQuestion,
            Game, Player, QuestionAnswerStat,
        )
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_run_lightweight_migrations)


def _run_lightweight_migrations(sync_conn) -> None:
    """Best-effort additive ALTER TABLE for SQLite databases pre-dating new columns."""
    from sqlalchemy import text

    def _column_exists(table: str, column: str) -> bool:
        rows = sync_conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return any(r[1] == column for r in rows)

    if not _column_exists("questions", "randomize_answers"):
        sync_conn.execute(text(
            "ALTER TABLE questions ADD COLUMN randomize_answers BOOLEAN NOT NULL DEFAULT 1"
        ))

    if not _column_exists("questions", "correct_index"):
        sync_conn.execute(text(
            "ALTER TABLE questions ADD COLUMN correct_index INTEGER NOT NULL DEFAULT 0"
        ))

    if not _column_exists("games", "join_code"):
        sync_conn.execute(text(
            "ALTER TABLE games ADD COLUMN join_code TEXT"
        ))
        # Assign codes to any existing games that don't have one.
        import secrets
        _CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
        rows = sync_conn.execute(text("SELECT id FROM games WHERE join_code IS NULL")).fetchall()
        for (game_id,) in rows:
            while True:
                code = "".join(secrets.choice(_CHARS) for _ in range(6))
                exists = sync_conn.execute(
                    text("SELECT 1 FROM games WHERE join_code = :c"), {"c": code}
                ).fetchone()
                if not exists:
                    break
            sync_conn.execute(
                text("UPDATE games SET join_code = :c WHERE id = :id"),
                {"c": code, "id": game_id},
            )


async def get_db() -> AsyncSession:  # type: ignore[misc]
    async with async_session() as session:
        yield session
