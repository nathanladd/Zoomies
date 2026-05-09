# Rudi

*Named for Rudolf Christian Karl Diesel — the engineer whose spark of an idea still drives us forward.*

Rudi is a classroom quiz game. Students join from their own browsers on the local network; the instructor runs one question at a time with a live timer, progressive answer elimination, and continuous scoring. A projection window shows the current question to the whole room while each student sees the answer choices on their own device.

## Quick Start

### Server

The server runs independently — on Ubuntu for a permanent setup, or locally for development.

**Ubuntu (permanent deployment):** see [deploy/README-server.md](deploy/README-server.md) for the full systemd setup.

**Local / development:**

```powershell
pip install -r requirements.txt
python run_server.py
```

The server starts at `http://0.0.0.0:5000`. The SQLite database and media folder are created automatically on first launch.

### Instructor App

```powershell
pip install -r requirements.txt
python run_instructor.py
```

The app connects to `localhost:5000` by default. To point it at a remote server open **File → Settings** and update the host and port — this is saved to `connection.json` next to the executable.

### Students Join

Students open a browser and navigate to `http://<server-ip>:5000`, enter their name and the game ID, and land on the game page.

## Architecture

| Component | Where it runs | Technology | Description |
|-----------|---------------|------------|-------------|
| **Backend** | Ubuntu server | FastAPI + uvicorn | REST API, WebSocket hub, game logic — runs as a systemd service |
| **Database** | Ubuntu server | SQLite + SQLAlchemy 2.0 (async) | Portable file-based storage |
| **Instructor GUI** | Instructor's Windows PC | PyQt6 | Desktop app; connects to the server over HTTP/WebSocket |
| **Student UI** | Students' browsers | HTML + TailwindCSS + JavaScript | Browser-based, works on any device |
| **Real-time** | — | Native WebSocket | Live sync between server and all clients |

## Project Structure

```
Rudi/
├── server/              # FastAPI backend
│   ├── main.py          # App entry point
│   ├── config.py        # Settings + DB path
│   ├── database.py      # Async SQLAlchemy setup
│   ├── models.py        # ORM models
│   ├── schemas.py       # Pydantic schemas
│   ├── routers/         # REST API (topics, questions, quizzes, games, admin)
│   ├── websocket/       # Connection manager
│   └── game/            # Game engine
│       ├── engine.py    # GameEngine state machine
│       ├── scoring.py   # Square-root point decay
│       ├── elimination.py
│       ├── handlers.py  # WebSocket handlers
│       └── base.py      # Abstract base
├── instructor/          # PyQt6 instructor application
│   ├── main.py          # Tabs + Database menu (Backup / Restore)
│   ├── api_client.py    # HTTP client to server
│   ├── connection_settings.py
│   ├── core/            # Topic, Question, Quiz UI
│   └── game/            # Control panel + projection window
├── static/              # Student web UI
│   ├── index.html       # Join page
│   └── game/            # Game page + css/ + js/
├── deploy/              # Ubuntu systemd service template
├── installer/           # Inno Setup configuration
├── media/questions/     # Uploaded question images
├── data/                # SQLite database (auto-created)
├── backups/             # Backup archives (auto-created)
├── entry.py             # Frozen app entry point (GUI vs. server dispatch)
├── version.py           # Single source of truth for app version
├── build.ps1            # Windows installer build script
├── Rudi.spec            # PyInstaller spec
├── requirements.txt
├── requirements-server.txt
├── requirements-build.txt
├── run_server.py
├── run_instructor.py
├── test_integration.py
└── test_ws.py
```

## Features

- **Question pool** organized by topic, with optional images per question.
- **Question types**: `multiple_choice` (4 answers, shuffled), `true_false`, and `technician_ab` (fixed A/B/C/D, ASE-style).
- **Quiz builder** assembles quizzes from the pool, with drag-order and per-quiz order randomization.
- **Live game** with progressive elimination (wrong answers disabled at 33% and 66% of the timer) and a square-root point-decay curve that keeps scores closer while still rewarding quick answers.
- **Projection window** with join URL, game ID, live timer, question text + image, and leaderboard. Frameless; press **F11** for fullscreen.
- **No accounts** — students join with just their name and the game ID.
- **Database backup / restore** from the instructor app's *Database* menu, or via `POST /api/admin/backup` and `POST /api/admin/restore`. See `PLANNING.md` §12 for the full procedure.

## Scoring

Points follow a square-root decay curve between `POINTS_MAX = 1000` and `POINTS_MIN = 100`:

```
points = POINTS_MIN + (POINTS_MAX − POINTS_MIN) × √(remaining / total)
```

| Elapsed | Points |
|---|---|
| 0% | 1000 |
| 25% | 879 |
| 50% | 736 |
| 75% | 550 |
| 100% | 100 |

Correct answer → earn the current point value. Wrong or no answer → 0 points for that question.

## Testing

The server must be running before executing these tests.

```powershell
python test_integration.py   # end-to-end REST API tests
python test_ws.py            # WebSocket connectivity test
```

## Building the Windows Installer

See [BUILD.md](BUILD.md) for full instructions. Quick summary:

```powershell
# One-time setup: Python 3.13 venv + Inno Setup 6
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-build.txt

# Build installer
.\build.ps1
# Output: dist\installer\Rudi-Setup-<version>.exe
```

Partial builds: `.\build.ps1 -SkipInstaller` or `.\build.ps1 -SkipPyInstaller`.
