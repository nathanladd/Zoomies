# Cognit

Cognit is a modular educational assessment platform that manages question pools, builds quizzes/tests, tracks results, and hosts interactive games. Designed for classroom use on a local intranet.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start the Server

```bash
python run_server.py
```

The server runs at `http://localhost:5000`. The SQLite database and media directories are created automatically on first launch.

### 3. Launch the Instructor App

In a separate terminal:

```bash
python run_instructor.py
```

### 4. Students Join

Students open a browser and navigate to `http://<instructor-ip>:5000` to join an active game session.

## Architecture

| Component | Technology | Description |
|-----------|------------|-------------|
| **Backend** | FastAPI + uvicorn | REST API, WebSocket hub, game logic |
| **Database** | SQLite + SQLAlchemy 2.0 (async) | Portable file-based storage |
| **Instructor GUI** | PyQt6 | Desktop app for managing content and running games |
| **Student UI** | HTML + TailwindCSS + JavaScript | Browser-based, works on any device |
| **Real-time** | Native WebSocket | Live sync between server and all clients |

## Project Structure

```
Cognit/
├── server/              # FastAPI backend
│   ├── main.py          # App entry point
│   ├── config.py        # Settings
│   ├── database.py      # Async SQLAlchemy setup
│   ├── models.py        # ORM models
│   ├── schemas.py       # Pydantic schemas
│   ├── routers/         # REST API endpoints
│   ├── websocket/       # Connection manager
│   └── games/           # Game modules (extensible)
│       └── pointdrop/   # PointDrop game engine
├── instructor/          # PyQt6 instructor application
│   ├── main.py          # GUI entry point
│   ├── api_client.py    # HTTP client to server
│   ├── core/            # Topic, Question, Quiz, Results UI
│   └── games/           # Game-specific UI
│       └── pointdrop/   # Control panel + display window
├── static/              # Student web UI
│   ├── index.html       # Join page
│   └── pointdrop/       # PointDrop game pages
├── media/questions/     # Uploaded question images
├── data/                # SQLite database (auto-created)
├── requirements.txt
├── run_server.py
└── run_instructor.py
```

## Features

### Cognit Core
- **Question Pool** — Create, edit, organize questions by topic with optional images
- **Quiz Builder** — Assemble quizzes from the pool, reorder questions, toggle randomization
- **Results Tracker** — Session logs, player scores, per-question analytics, student history

### PointDrop Game Module
- **Live quiz game** with elimination mechanics and continuous scoring
- **Progressive elimination** — wrong answers disabled at 33% and 66% time marks
- **Continuous scoring** — points decrease by the millisecond (1000 → 100)
- **Dual display** — instructor control panel + fullscreen projector window
- **No accounts needed** — students join with just their name
