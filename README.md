# Rudi

<<<<<<< HEAD
*Named for Rudolf Christian Karl Diesel — the engineer whose spark of an idea still drives us forward.*
=======
*Rudi - What I would think friends called Rudolph Christian, Karl Diesel (The inventopr of the diesel engine)*
>>>>>>> 7304b35f9aac8beab15f8b13eeec08748a837a41

Rudi is a classroom quiz game. Students join from their own browsers on the local network; the instructor runs one question at a time with a live timer, progressive answer elimination, and continuous scoring. A projection window shows the current question to the whole room while each student sees the answer choices on their own device.

## Quick Start

### 1. Install dependencies

```powershell
pip install -r requirements.txt
```

### 2. Start the server

```powershell
python run_server.py
```

The server runs at `http://localhost:5000`. The SQLite database (`data/rudi.db`) and media folder are created automatically on first launch. If you are upgrading from a pre-rename install, the old `data/zundpunkt.db` is renamed in place on first launch.

### 3. Launch the instructor app

```powershell
python run_instructor.py
```

### 4. Students join

Students open a browser and navigate to `http://<instructor-ip>:5000`, enter their name and the session number, and land on the game page.

## Architecture

| Component | Technology | Description |
|-----------|------------|-------------|
| **Backend** | FastAPI + uvicorn | REST API, WebSocket hub, game logic |
| **Database** | SQLite + SQLAlchemy 2.0 (async) | Portable file-based storage |
| **Instructor GUI** | PyQt6 | Desktop app with tabs + projection window |
| **Student UI** | HTML + TailwindCSS + JavaScript | Browser-based, works on any device |
| **Real-time** | Native WebSocket | Live sync between server and all clients |

## Project Structure

```
Rudi/
├── server/              # FastAPI backend
│   ├── main.py          # App entry point
│   ├── config.py        # Settings + DB path
│   ├── database.py      # Async SQLAlchemy setup
│   ├── models.py        # ORM models
│   ├── schemas.py       # Pydantic schemas
│   ├── routers/         # REST API (topics, questions, quizzes, sessions, admin)
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
│   ├── core/            # Topic, Question, Quiz UI
│   └── game/            # Control panel + projection window
├── static/              # Student web UI
│   ├── index.html       # Join page
│   └── game/            # Game page + css/ + js/
├── media/questions/     # Uploaded question images
├── data/                # SQLite database (auto-created)
├── backups/             # Backup archives (auto-created)
├── requirements.txt
├── run_server.py
└── run_instructor.py
```

## Features

- **Question pool** organized by topic, with optional images per question.
- **Quiz builder** assembles quizzes from the pool, with drag-order and per-quiz order randomization.
- **Live game** with progressive elimination (wrong answers disabled at 33% and 66% of the timer) and a square-root point-decay curve that keeps scores closer while still rewarding quick answers.
- **Projection window** with join URL, session number, live timer, question text + image, and leaderboard. Frameless; press **F11** for fullscreen.
- **No accounts** — students join with just their name and the session number.
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
