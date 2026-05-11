from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from server.auth import require_auth, verify_ws_token
from server.config import BASE_DIR, MEDIA_DIR, USER_DATA_DIR
from server.database import init_db, get_db
from server.routers import topics, questions, quizzes, games, admin, settings
from server.routers import auth as auth_router
from server.game.handlers import (
    load_engine, handle_student_ws, handle_instructor_ws,
    join_codes,
)
from server.log_broadcast import broadcaster
from version import SERVER_VERSION

# Config ensures user-writable data/media/backup dirs exist.
# Static assets live in BASE_DIR (bundled read-only in frozen mode), so only
# create the tree in dev where BASE_DIR is the project root.
if not getattr(__import__("sys"), "frozen", False):
    (BASE_DIR / "static" / "game" / "css").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "static" / "game" / "js").mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    broadcaster.install()
    await init_db()
    yield


app = FastAPI(title="Rudi", version=SERVER_VERSION, lifespan=lifespan)

# Static web UI is bundled read-only (BASE_DIR = _MEIPASS in frozen mode;
# project root in dev). Uploaded media lives under USER_DATA_DIR/media which
# is user-writable. MEDIA_DIR (USER_DATA_DIR/media/questions) is already
# ensured to exist by server.config.
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/media", StaticFiles(directory=str(USER_DATA_DIR / "media")), name="media")

# Register API routers
app.include_router(auth_router.router)
app.include_router(topics.router)
app.include_router(questions.router)
app.include_router(quizzes.router)
app.include_router(games.router)
app.include_router(admin.router)
app.include_router(settings.router)


# ── Meta ──────────────────────────────────────────────────────────────────────────

@app.get("/api/version")
async def api_version():
    return {"version": SERVER_VERSION}


# ── HTML page routes ───────────────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse(
        str(BASE_DIR / "static" / "index.html"),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/play")
async def play_game():
    return FileResponse(
        str(BASE_DIR / "static" / "game" / "game.html"),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


# ── Engine bootstrap + WebSocket endpoints ──────────────────────────────────────────────

@app.post("/api/games/{game_id}/init", dependencies=[Depends(require_auth)])
async def init_game_engine(game_id: int, db: AsyncSession = Depends(get_db)):
    try:
        engine = await load_engine(game_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "ok", "game_id": game_id, "question_count": engine.question_count}


@app.websocket("/ws/student/{join_code}")
async def ws_student(websocket: WebSocket, join_code: str):
    game_id = join_codes.get(join_code.upper())
    if game_id is None:
        await websocket.accept()
        await websocket.close(code=4000, reason="Invalid game code")
        return
    await handle_student_ws(websocket, game_id)


@app.websocket("/ws/instructor/{game_id}")
async def ws_instructor(websocket: WebSocket, game_id: int, token: str | None = None):
    if not verify_ws_token(token):
        await websocket.accept()
        await websocket.close(code=4001, reason="Unauthorized")
        return
    await handle_instructor_ws(websocket, game_id)


@app.websocket("/ws/logs")
async def ws_logs(websocket: WebSocket, token: str | None = None):
    """Stream server log output to the instructor app."""
    if not verify_ws_token(token):
        await websocket.accept()
        await websocket.close(code=4001, reason="Unauthorized")
        return
    await broadcaster.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive; client won't send much
    except Exception:
        pass
    finally:
        await broadcaster.disconnect(websocket)
