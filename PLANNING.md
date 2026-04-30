# RUDI — Classroom Quiz Game

**Rudi** — *named for Rudolf Christian Karl Diesel, the engineer whose spark of an idea still drives us forward.*
(Originally shipped as **Zündpunkt**; renamed to Rudi in 0.5.x.)

**Version:** 3.0
**Platform:** Windows
**Stack:** Python 3.12 · FastAPI · SQLite · PyQt6 · TailwindCSS

---

# 1. Project Overview

## 1.1 What it is

Rudi is a single-purpose classroom quiz game for a local intranet. The instructor runs the app, projects one question at a time, and students join from their own browsers with just a name. Each question has a live countdown, progressive elimination of wrong answers, and a continuous point decay that rewards fast answers without leaving slower players too far behind. When the quiz ends, a leaderboard is shown; that's it.

## 1.2 What changed from the old design

This project was previously split into a "Cognit" platform shell and a "PointDrop" game module with post-game analytics (per-question aggregation, student history across sessions, etc.). Those have been collapsed into a single product — first shipped as **Zündpunkt**, now renamed to **Rudi** — and analytics have been removed in favor of an in-game leaderboard only.

Concretely:

- One product name, one set of menus: **Rudi** (formerly Zündpunkt).
- **No post-game analytics.** The `Answer` table, the `/api/results/*` endpoints, and the *Results* tab in the instructor app are gone.
- **Simpler session schema.** `GameSession.game_type` and `GameSession.current_q_index` are removed. There is only one game.
- **Flattened code layout.** `server/games/pointdrop/` → `server/game/`, `instructor/games/pointdrop/` → `instructor/game/`, `static/pointdrop/` → `static/game/`.
- **Renamed "Display" window → "Projection" window** throughout the instructor app.
- **Database filename:** `cognit.db` → `zundpunkt.db` → `rudi.db` (legacy files are renamed in place on first launch).
- **Route rename:** `/pointdrop` → `/play`.
- **Backup / restore** of the question database is now a built-in feature (see §12).

---

# 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INSTRUCTOR'S COMPUTER                               │
│                                                                             │
│   ┌──────────────────┐   ┌──────────────────┐   ┌────────────────────────┐  │
│   │  Admin Window    │   │ Projection Window│   │    FastAPI Server      │  │
│   │  (PyQt6)         │   │  (PyQt6)         │   │    (uvicorn)           │  │
│   │                  │   │                  │   │                        │  │
│   │  - Manage Q's    │   │  - Fullscreen    │   │  - REST API            │  │
│   │  - Build quizzes │   │  - Show question │   │  - WebSocket hub       │  │
│   │  - Start/control │   │  - Timer + score │   │  - Game logic          │  │
│   │  - Leaderboard   │   │  - Leaderboard   │   │  - SQLite database     │  │
│   │  - Backup menu   │   │  - F11 full      │   │  - Backup / restore    │  │
│   └──────────────────┘   └──────────────────┘   └────────────────────────┘  │
│            │                      │                        │                │
│            └──────────────────────┴────────────────────────┘                │
│                                   │                                         │
└───────────────────────────────────┼─────────────────────────────────────────┘
                                    │ HTTP + WebSocket (port 5000)
                                    │ Local Intranet (Wi-Fi / Ethernet)
                                    │
        ┌───────────────────────────┼───────────────────────────┐
┌───────▼───────┐           ┌───────▼───────┐           ┌───────▼───────┐
│    Student    │           │    Student    │           │    Student    │
│    Browser    │           │    Browser    │           │    Browser    │
│  - Join game  │           │  - Join game  │           │  - Join game  │
│  - Answer Q's │           │  - Answer Q's │           │  - Answer Q's │
│  - See score  │           │  - See score  │           │  - See score  │
└───────────────┘           └───────────────┘           └───────────────┘
```

---

# 3. Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Backend framework** | FastAPI | REST API + native WebSocket support |
| **ASGI server** | uvicorn | Runs FastAPI with async capabilities |
| **Database** | SQLite | File-based, portable, no setup required |
| **Async DB driver** | aiosqlite | Non-blocking database operations |
| **ORM** | SQLAlchemy 2.0 (async) | Database models and queries |
| **Validation** | Pydantic 2 | Request/response data validation |
| **Desktop GUI** | PyQt6 | Instructor admin + projection windows |
| **Student interface** | HTML + CSS + JS | Browser-based, works on any laptop |
| **Styling** | TailwindCSS (CDN) | Modern responsive UI |
| **Real-time** | Native WebSocket | Instant sync between server and clients |
| **HTTP client** | httpx | Instructor GUI → server communication |
| **File handling** | aiofiles | Async image upload/serving |
| **Image processing** | Pillow (optional) | Image validation/resizing |
| **Backup** | `sqlite3.Connection.backup()` + `zipfile` | Online DB backup bundled with media |

`requirements.txt` lists the pinned minimums.

---

# 4. Project Structure

```
Rudi/
│
├── server/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Settings, DB_PATH, POINTS_*
│   ├── database.py                # Async SQLAlchemy engine + init_db
│   ├── models.py                  # ORM models (no Answer table)
│   ├── schemas.py                 # Pydantic schemas
│   │
│   ├── routers/
│   │   ├── topics.py              # CRUD for topics
│   │   ├── questions.py           # CRUD for questions + image upload
│   │   ├── quizzes.py             # CRUD for quizzes
│   │   ├── sessions.py            # Session lifecycle
│   │   └── admin.py               # Backup / restore endpoints
│   │
│   ├── websocket/
│   │   └── manager.py             # WebSocket connection manager
│   │
│   └── game/                      # Game engine (single game, no more /games/ layer)
│       ├── base.py                # Abstract BaseGame (kept for clarity)
│       ├── engine.py              # GameEngine state machine
│       ├── scoring.py             # Square-root point decay
│       ├── elimination.py         # Answer elimination scheduling
│       └── handlers.py            # WebSocket handlers (instructor + student)
│
├── instructor/
│   ├── main.py                    # PyQt6 MainWindow + Database menu
│   ├── api_client.py              # HTTP client to server
│   │
│   ├── core/                      # Tabs for content management
│   │   ├── topic_manager.py
│   │   ├── question_pool.py
│   │   └── quiz_builder.py
│   │
│   └── game/                      # Game tab
│       ├── control_panel.py       # GameControlPanel (live controls)
│       └── projection_window.py   # ProjectionWindow (fullscreen display)
│
├── static/                        # Student web UI
│   ├── index.html                 # Join page (name + session number)
│   └── game/
│       ├── game.html
│       ├── css/styles.css
│       └── js/game.js
│
├── media/
│   └── questions/                 # Uploaded question images
│
├── data/
│   └── rudi.db                    # SQLite database (auto-created)
│
├── backups/                       # Backup zip archives (auto-created)
│
├── requirements.txt
├── run_server.py                  # Launch uvicorn server
├── run_instructor.py              # Launch PyQt6 instructor app
├── test_integration.py
├── test_ws.py
└── README.md
```

---

# 5. Question Pool & Quiz Builder

## 5.1 Concept

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         QUESTION POOL                                     │
│                    (Master repository of all questions)                   │
│                                                                           │
│   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐               │
│   │    Topic:     │   │    Topic:     │   │    Topic:     │               │
│   │    Math       │   │   Science     │   │   History     │   ...         │
│   ├───────────────┤   ├───────────────┤   ├───────────────┤               │
│   │  Q1, Q2, …    │   │  Q5, Q6, …    │   │  Q8, Q9, …    │               │
│   └───────────────┘   └───────────────┘   └───────────────┘               │
└───────────────────────────────────────────────────────────────────────────┘
                    │                         │
                    ▼                         ▼
┌─────────────────────────────┐   ┌─────────────────────────────┐
│  Quiz: "Math Test Ch.1"     │   │  Quiz: "Science Final"      │
├─────────────────────────────┤   ├─────────────────────────────┤
│  1. Q1 (from Math)          │   │  1. Q5 (from Science)       │
│  2. Q3 (from Math)          │   │  2. Q6 (from Science)       │
│  3. Q2 (from Math)          │   │  3. Q7 (from Science)       │
└─────────────────────────────┘   └─────────────────────────────┘
```

Questions exist independently in the pool. Quizzes are ordered selections of questions; the same question can appear in multiple quizzes.

## 5.2 Operations

| Scope | Operations |
|---|---|
| **Topics** | create / list / update / delete (questions are set to NULL topic on delete) |
| **Questions** | create / list / filter by topic / update / delete; upload or remove an image |
| **Quizzes** | create / list / update (name, description, randomize flag) / delete |
| **Quiz questions** | add / remove / reorder |

## 5.3 Sessions (runtime only)

A `GameSession` is a single instance of playing a quiz (e.g. "Period 1 on Jan 12"). Sessions hold `id`, `quiz_id`, `status` (`waiting` / `active` / `finished`), `started_at`, `ended_at`. Players attached to a session have a `name` and `total_score`. Per-answer response times are **not** persisted — the final leaderboard is the only retained outcome.

---

# 6. Database Schema

## 6.1 ER diagram

```
┌─────────────────────┐
│       Topic         │
├─────────────────────┤
│ id (PK)             │
│ name (unique)       │
│ description         │
│ created_at          │
└──────────┬──────────┘
           │ 1
           │
           ▼ N
┌─────────────────────┐         ┌─────────────────────┐
│      Question       │         │        Quiz         │
├─────────────────────┤         ├─────────────────────┤
│ id (PK)             │         │ id (PK)             │
│ topic_id (FK)       │         │ name                │
│ question_type       │         │ description         │
│ text                │         │ randomize_order     │
│ image_filename      │◄───┐    │ created_at          │
│ correct_answer      │    │    └──────────┬──────────┘
│ wrong_answer_1      │    │               │ 1
│ wrong_answer_2 (?)  │    │               │
│ wrong_answer_3 (?)  │    │               ▼ N
│ time_seconds        │    │    ┌─────────────────────┐
│ created_at          │    │    │    QuizQuestion     │
└─────────────────────┘    │    ├─────────────────────┤
                           │    │ id (PK)             │
                           └────│ question_id (FK)    │
                                │ quiz_id (FK)        │
                                │ position            │
                                └─────────────────────┘

┌─────────────────────┐         ┌─────────────────────┐
│    GameSession      │         │       Player        │
├─────────────────────┤    1  N ├─────────────────────┤
│ id (PK)             │◄────────│ session_id (FK)     │
│ quiz_id (FK)        │         │ id (PK)             │
│ status              │         │ name                │
│ started_at          │         │ total_score         │
│ ended_at            │         │ joined_at           │
└─────────────────────┘         └─────────────────────┘
```

There is no `Answer` table. Correctness and per-answer points are computed in-memory inside the running `GameEngine` and only the cumulative `Player.total_score` is written to the DB.

## 6.2 Tables

### Topic
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | autoincrement |
| name | TEXT | NOT NULL, UNIQUE |
| description | TEXT | nullable |
| created_at | DATETIME | NOT NULL |

### Question
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | autoincrement |
| topic_id | INTEGER FK → topics.id | nullable, `ON DELETE SET NULL` |
| question_type | TEXT | `multiple_choice` / `true_false` / `technician_ab` |
| text | TEXT | nullable (image-only OK) |
| image_filename | TEXT | nullable |
| correct_answer | TEXT | NOT NULL |
| wrong_answer_1 | TEXT | NOT NULL |
| wrong_answer_2 | TEXT | nullable |
| wrong_answer_3 | TEXT | nullable |
| time_seconds | INTEGER | default 10, range 5–30 |
| created_at | DATETIME | NOT NULL |

**Question types:**

| Type | Answers | Elimination | Randomized positions |
|---|---|---|---|
| `multiple_choice` | 4 (1 correct + 3 wrong) | Yes, at 33% and 66% | Yes |
| `true_false` | 2 (True / False) | No | No (fixed A/B) |
| `technician_ab` | 4 (fixed ASE choices) | Yes, at 33% and 66% | No (fixed A/B/C/D) |

### Quiz
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT | NOT NULL |
| description | TEXT | nullable |
| randomize_order | BOOLEAN | default FALSE |
| created_at | DATETIME | NOT NULL |

### QuizQuestion
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| quiz_id | INTEGER FK → quizzes.id | `ON DELETE CASCADE` |
| question_id | INTEGER FK → questions.id | `ON DELETE CASCADE` |
| position | INTEGER | ordering inside the quiz |

### GameSession
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| quiz_id | INTEGER FK → quizzes.id | |
| status | TEXT | `waiting` / `active` / `finished` |
| started_at | DATETIME | nullable |
| ended_at | DATETIME | nullable |

### Player
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| session_id | INTEGER FK → game_sessions.id | `ON DELETE CASCADE` |
| name | TEXT | NOT NULL |
| total_score | INTEGER | default 0 |
| joined_at | DATETIME | NOT NULL |

## 6.3 Answer randomization

1. Questions store correct + up to 3 wrong answers, no letter assignment.
2. At game time the server shuffles the answers for `multiple_choice` into A/B/C/D and remembers which slot is correct for that session.
3. `true_false` and `technician_ab` keep fixed letter order.
4. Elimination picks random wrong answers at 33% and 66% of the timer; the correct answer is never eliminated.
5. Students submit by text; the server compares the selection to `correct_answer`.

## 6.4 Question-order randomization

If `quiz.randomize_order = TRUE`, the server shuffles the `QuizQuestion` list at session start. The randomized order lives in memory for the session only — it is not persisted.

---

# 7. Game Mechanics

## 7.1 Quiz lifecycle

```
SETUP            WAITING           ACTIVE              FINISHED
  │                 │                 │                    │
  ▼                 ▼                 ▼                    ▼
Create         Students         Question Loop        Final leaderboard
session         join            (per-question)       (rankings shown,
                                                      session ends)
```

Per question:

1. Show question.
2. Start timer + points decay + elimination schedule.
3. Collect answers as they arrive.
4. Instructor reveals (or timer expires).
5. Show correct answer + updated leaderboard on projection.
6. Wait for instructor to advance.

## 7.2 Question timeline (10-second example)

```
TIME:     0s         3s         6s         9s         10s
          │          │          │          │          │
POINTS:   1000 ─── 800 ─── 700 ─── 500 ──────────▶ 100
          (square-root decay — see §7.3)
CHOICES:  [A][B][C][D]   [B][C][D]    [B][D]
                     │             │
                     ▼             ▼
                 Eliminate     Eliminate
                    A             C
                 (33%)         (66%)
```

## 7.3 Scoring — square-root decay

The previous build used a linear decay between max and min points. That made the score gap balloon quickly: a player answering at the half-way mark received only 55% of the max. The current scoring curve keeps scores closer together while still rewarding fast answers:

```
points = POINTS_MIN + (POINTS_MAX − POINTS_MIN) × √(remaining / total)
```

Configuration lives in `server/config.py`:

| Parameter | Value |
|---|---|
| `POINTS_MAX` | 1000 |
| `POINTS_MIN` | 100 |

Example for a 10-second question:

| Elapsed | Linear (old) | √-curve (current) |
|---|---|---|
| 0.0s | 1000 | **1000** |
| 2.5s | 775 | **879** |
| 5.0s | 550 | **736** |
| 7.5s | 325 | **550** |
| 9.0s | 190 | **385** |
| 10.0s | 100 | **100** |

Correct answer → earn the current point value. Wrong or missing → 0.

## 7.4 Elimination

| Time mark | Action | Choices remaining |
|---|---|---|
| 0% | Question appears | 4 |
| 33% | Eliminate 1 wrong answer | 3 |
| 66% | Eliminate 1 wrong answer | 2 |
| 100% | Timer expires, reveal | 2 |

Correct answer is never eliminated. Students who have already answered see no change. Instructor manually advances (no auto-advance between questions).

## 7.5 Per-question time limits

| Setting | Value |
|---|---|
| Default | 10 s |
| Minimum | 5 s |
| Maximum | 30 s |

---

# 8. User Interfaces

## 8.1 Student flow

- **Join page** (`/`): big `RUDI` banner, tagline, name + session number fields, "Join Game" button.
- **Game page** (`/play?session=…&name=…`): waiting → question → locked → result → final leaderboard. WebSocket-driven, one screen active at a time.

## 8.2 Projection window (instructor)

The projection window is what the classroom sees. Frameless, dark background, `background-color: #0f172a`.

**Waiting screen contents (top → bottom):**

1. `RUDI` header (large, indigo, with glow).
2. Italic tagline: *Named for Rudolf Christian Karl Diesel — the engineer whose spark of an idea still drives us forward.*
3. Smaller dim caption: *A classroom quiz game.*
4. "Join at" + local IP + port.
5. Session number.
6. Player count + the joined names.

**During a question:** progress counter, timer bar, current point value, question text, optional image, answer count (`18/24 students`). Answer choices are *not* shown — students see those on their own devices.

**After reveal / at game end:** correct-answer banner, leaderboard.

**F11 hint:** a small dim label (`Press F11 for fullscreen · Esc to exit`) is pinned to the bottom-right corner whenever the window is in windowed mode, and automatically disappears when fullscreen. Implemented as a free-floating child `QLabel` repositioned in `resizeEvent` / `showEvent`.

## 8.3 Instructor admin window

Tabs: **Topics**, **Questions**, **Quiz Builder**, **Game**. Plus a top-level **Database** menu with **Backup Database…** and **Restore Database…** items.

Game tab contents:

- Quiz selector + "Create Session"
- Controls: Start Game · Next Question · Reveal Answer · End Game
- Current-question panel (text + choices, correct answer highlighted after reveal)
- **Open Projection** button (toggles the projection window)
- Live leaderboard (left) + server console + instructor console (right), each collapsible via a splitter

---

# 9. REST API

All JSON. Base URL `http://<host>:5000`.

| Method | Path | Purpose |
|---|---|---|
| GET/POST/PUT/DELETE | `/api/topics` | Topic CRUD |
| GET/POST/PUT/DELETE | `/api/questions` | Question CRUD |
| POST / DELETE | `/api/questions/{id}/image` | Image upload / remove |
| GET/POST/PUT/DELETE | `/api/quizzes` | Quiz CRUD |
| POST / PUT / DELETE | `/api/quizzes/{id}/questions…` | Add / reorder / remove |
| GET/POST/PUT/DELETE | `/api/sessions` | Session CRUD + start / end |
| POST | `/api/sessions/{id}/init-game` | Build in-memory `GameEngine` |
| POST | `/api/admin/backup` | Create a backup zip (see §12) |
| POST | `/api/admin/restore` | Restore from a backup zip (see §12) |

WebSocket endpoints:

- `ws://…/ws/instructor/{session_id}`
- `ws://…/ws/student/{session_id}`

---

# 10. WebSocket Events

| Event | Direction | Payload |
|---|---|---|
| `player_join` | student → server | `{name}` |
| `join_confirmed` | server → student | `{player_id, name}` |
| `player_joined` | server → all | `{player_id, name, player_count}` |
| `player_left` | server → all | `{player_id, name, player_count}` |
| `start_game` | instructor → server | `{}` |
| `game_start` | server → all | `{quiz_name, question_count}` |
| `next_question` | instructor → server | `{}` |
| `question_start` | server → all | `{index, total, text, image_url, choices, time_seconds, max_points, question_type}` |
| `question_answer` | server → instructor | `{correct_answer}` |
| `points_update` | server → all | `{current_points, time_remaining_ms}` (sent ~10× / s) |
| `choice_eliminated` | server → all | `{choice, remaining_choices}` |
| `submit_answer` | student → server | `{choice, elapsed_ms}` |
| `answer_confirmed` | server → student | `{choice, locked: true}` |
| `answer_count` | server → instructor | `{answered, total}` |
| `reveal` | instructor → server | `{}` |
| `question_end` | server → all | `{correct_choice, player_scores[], answers_received, total_players}` |
| `end_game` | instructor → server | `{}` |
| `game_end` | server → all | `{final_rankings[], question_count, player_count}` |

---

# 11. Image Handling

| Constraint | Value |
|---|---|
| Supported formats | PNG, JPEG, GIF, WebP |
| Maximum file size | 5 MB |
| Maximum dimensions | 1920 × 1080 (optional resize) |
| Storage location | `media/questions/` |
| Naming | `q_{question_id}_{timestamp}.{ext}` |

`Question.text` and `Question.image_filename` may each be filled or empty — a question may be text-only, image-only, or both.

---

# 12. Database Backup & Restore

The database is small and irreplaceable once quizzes have been authored. Backing it up is therefore a first-class feature.

## 12.1 What gets backed up

- `data/rudi.db` — the SQLite file (topics, questions, quizzes, quiz_questions, game_sessions, players).
- `media/questions/` — image files referenced by `Question.image_filename`.

Both must be bundled together; image filenames in the DB are useless without the files and vice versa.

## 12.2 Backup zip layout

```
rudi-<timestamp>.zip
├── data/
│   └── rudi.db
└── media/
    └── questions/
        ├── q_001_*.png
        └── …
```

## 12.3 In-app backup

**Instructor app → Database menu → Backup Database…**

1. Instructor picks a destination zip path (default: `~/rudi-<timestamp>.zip`).
2. Instructor GUI calls `POST /api/admin/backup?path=<chosen>`.
3. Server:
   - Uses SQLite's online backup API (`sqlite3.Connection.backup(dst_conn)`) to copy the DB to a temp file without blocking writes.
   - Writes the temp DB plus the contents of `media/questions/` into a `ZIP_DEFLATED` archive at the chosen path.
   - Returns `{path, size_bytes, created_at}`.
4. Instructor GUI shows a confirmation with the size.

If no `path` query is provided, the server writes to `backups/rudi-<timestamp>.zip` under the project root.

## 12.4 In-app restore

**Instructor app → Database menu → Restore Database…**

1. Instructor confirms the replacement warning.
2. Instructor picks a backup zip.
3. Instructor GUI calls `POST /api/admin/restore` with `{path}`.
4. Server:
   - Moves the current `data/rudi.db` and `media/questions/` into `data/pre-restore-<timestamp>/` so the previous state is recoverable.
   - Extracts the zip over `data/` and `media/questions/`.
   - Returns `{status, restored_from, previous_state, notice}` telling the instructor to **restart the server** (the running SQLAlchemy engine is still holding the old file handle).
5. Instructor GUI shows the restart instruction.

If the zip is malformed, the server rolls the safety copies back before returning a 400.

## 12.5 Manual PowerShell procedure (fallback)

Use this when the app isn't running or the user prefers a command-line workflow.

**Backup:**

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dest  = "backups\rudi-$stamp"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item "data\rudi.db" "$dest\rudi.db"
Copy-Item "media\questions"  "$dest\questions" -Recurse
Compress-Archive -Path "$dest\*" -DestinationPath "$dest.zip"
```

**Restore:**

```powershell
# Stop the server first!
Expand-Archive -Path "backups\rudi-<timestamp>.zip" -DestinationPath "."
# Then start the server again.
```

## 12.6 Optional: rotating auto-backup

Not implemented yet. Intended behavior: on server startup, if `backups/auto/rudi-<YYYYMMDD>.db` doesn't exist for today, create it via the online backup API; keep the 14 most-recent daily files, delete older ones. Add as a small task in `server/main.py` lifespan.

---

# 13. Build Status

| Area | Status |
|---|---|
| FastAPI backend + SQLAlchemy models | Done |
| Topic / Question / Quiz REST API | Done |
| Session REST API (simplified, no game_type) | Done |
| Instructor PyQt6 app (Topics/Questions/Quizzes/Game tabs) | Done |
| Game engine (elimination + √-decay scoring) | Done |
| Projection window with Rudi tagline + F11 hint | Done |
| Student web UI (join + play + results) | Done |
| Zündpunkt → Rudi rename migration | Done |
| Removal of Answer table + Results tab + analytics endpoints | Done |
| `/api/admin/backup` + `/api/admin/restore` | Done |
| Instructor Database menu (Backup / Restore) | Done |
| Rotating auto-backups | Not started (optional) |

---

# 14. Summary

Rudi is a tribute to Rudolf Diesel — press, start a quiz, fire. One product, one name, one database, one game mode. Students on their own screens, the projection on the wall, live scoring that still cares about speed without punishing the slower half of the class, and a backup button in the menu so you never lose the quizzes you authored.
