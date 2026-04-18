from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from server.config import BASE_DIR, MEDIA_DIR
from server.database import init_db, get_db
from server.routers import topics, questions, quizzes, sessions, admin
from server.game.handlers import (
    create_game, handle_student_ws, handle_instructor_ws,
)

# Ensure directories exist before mounting
(BASE_DIR / "static" / "game" / "css").mkdir(parents=True, exist_ok=True)
(BASE_DIR / "static" / "game" / "js").mkdir(parents=True, exist_ok=True)
(BASE_DIR / "media" / "questions").mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Zündpunkt", version="2.0.0", lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/media", StaticFiles(directory=str(BASE_DIR / "media")), name="media")

# Register API routers
app.include_router(topics.router)
app.include_router(questions.router)
app.include_router(quizzes.router)
app.include_router(sessions.router)
app.include_router(admin.router)


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


# ── WebSocket endpoints ───────────────────────────────────────────────────────

@app.post("/api/sessions/{session_id}/init-game")
async def init_game(session_id: int, db: AsyncSession = Depends(get_db)):
    try:
        engine = await create_game(session_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "ok", "session_id": session_id, "question_count": engine.question_count}


@app.websocket("/ws/student/{session_id}")
async def ws_student(websocket: WebSocket, session_id: int):
    await handle_student_ws(websocket, session_id)


@app.websocket("/ws/instructor/{session_id}")
async def ws_instructor(websocket: WebSocket, session_id: int):
    await handle_instructor_ws(websocket, session_id)
