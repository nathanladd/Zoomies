# COGNIT — Educational Assessment Platform

## Complete Project Planning Document

**Version:** 2.0  
**Date:** January 12, 2026  
**Platform:** Windows

---

# 1. PROJECT OVERVIEW

## 1.1 Platform Concept

**Cognit** is a modular educational assessment platform that manages question pools, builds quizzes/tests, tracks results, and hosts interactive games. It's designed to be extensible — new game modes and assessment types can be added over time while sharing the same question pool and results infrastructure.

## 1.2 Modular Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              COGNIT CORE                                     │
│                                                                             │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│   │  Question Pool  │  │  Quiz Builder   │  │ Results Tracker │             │
│   │  Management     │  │                 │  │                 │             │
│   │                 │  │  - Build quizzes│  │  - Session logs │             │
│   │  - Topics       │  │  - Select Q's   │  │  - Player scores│             │
│   │  - Questions    │  │  - Order Q's    │  │  - Analytics    │             │
│   │  - CRUD ops     │  │  - Edit later   │  │  - Export data  │             │
│   └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                              GAME MODULES                                    │
│                                                                             │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│   │   PointDrop     │  │   (Future)      │  │   (Future)      │             │
│   │   Quiz Game     │  │   Standard Test │  │   Other Games   │             │
│   │                 │  │                 │  │                 │             │
│   │  - Elimination  │  │  - Timed tests  │  │  - Team modes   │             │
│   │  - Live scoring │  │  - No scoring   │  │  - Tournaments  │             │
│   │  - Leaderboard  │  │  - Review mode  │  │  - etc.         │             │
│   └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 1.3 Components

### Cognit Core
- **Question Pool** — Master repository of questions organized by topics
- **Quiz Builder** — Create assessments by selecting questions from the pool
- **Results Tracker** — Store and analyze outcomes from all game sessions

### PointDrop (Game Module)
- **Live quiz game** with elimination mechanics and continuous scoring
- Students compete in real-time on a local intranet
- Game-show style with declining points and answer elimination

## 1.4 Key Features

**Cognit Core:**
- **Question Pool Management** — Create, edit, and organize questions with optional images
- **Topic Organization** — Categorize questions for easy filtering
- **Quiz Builder** — Assemble quizzes from the question pool
- **Results Tracking** — Store all session results for review and analysis
- **Extensible** — Add new game modules without modifying the core

**PointDrop Game:**
- **Student Participation** — Students join with just their name (no accounts required)
- **Live Game Show Mode** — One question at a time, all students answer simultaneously
- **Progressive Elimination** — Wrong answers are disabled over time
- **Continuous Scoring** — Points decrease by the millisecond to minimize ties
- **Dual Display** — Instructor control panel + separate projector window
- **Automatic Grading** — Instant scoring and leaderboard updates

---

# 2. SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INSTRUCTOR'S COMPUTER                               │
│                                                                             │
│   ┌──────────────────┐   ┌──────────────────┐   ┌────────────────────────┐  │
│   │  Admin Window    │   │  Display Window  │   │    FastAPI Server      │  │
│   │  (PyQt6)         │   │  (PyQt6)         │   │    (uvicorn)           │  │
│   │                  │   │                  │   │                        │  │
│   │  - Manage Q's    │   │  - Fullscreen    │   │  - REST API            │  │
│   │  - Build quizzes │   │  - Show question │   │  - WebSocket hub       │  │
│   │  - Start/control │   │  - Timer + score │   │  - Game logic          │  │
│   │  - View scores   │   │  - Leaderboard   │   │  - SQLite database     │  │
│   └──────────────────┘   └──────────────────┘   └────────────────────────┘  │
│            │                      │                        │                │
│            └──────────────────────┴────────────────────────┘                │
│                                   │                                         │
└───────────────────────────────────┼─────────────────────────────────────────┘
                                    │
                                    │ HTTP + WebSocket (port 5000)
                                    │ Local Intranet (Wi-Fi / Ethernet)
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
┌───────▼───────┐           ┌───────▼───────┐           ┌───────▼───────┐
│    Student    │           │    Student    │           │    Student    │
│    Laptop     │           │    Laptop     │           │    Laptop     │
│   (Browser)   │           │   (Browser)   │           │   (Browser)   │
│               │           │               │           │               │
│  - Join game  │           │  - Join game  │           │  - Join game  │
│  - Answer Q's │           │  - Answer Q's │           │  - Answer Q's │
│  - View score │           │  - View score │           │  - View score │
└───────────────┘           └───────────────┘           └───────────────┘
```

---

# 3. TECHNOLOGY STACK

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Backend Framework** | FastAPI | REST API + native WebSocket support |
| **ASGI Server** | uvicorn | Runs FastAPI with async capabilities |
| **Database** | SQLite | File-based, portable, no setup required |
| **Async DB Driver** | aiosqlite | Non-blocking database operations |
| **ORM** | SQLAlchemy 2.0 (async) | Database models and queries |
| **Validation** | Pydantic | Request/response data validation |
| **Desktop GUI** | PyQt6 | Instructor admin and display windows |
| **Student Interface** | HTML + CSS + JavaScript | Browser-based, works on any laptop |
| **Styling** | TailwindCSS | Modern, responsive UI |
| **Real-time Communication** | Native WebSocket | Instant sync between server and all clients |
| **HTTP Client** | httpx | Instructor GUI to server communication |
| **File Handling** | aiofiles | Async image upload/serving |
| **Image Processing** | Pillow (optional) | Image validation and resizing |

---

# 4. DEPENDENCIES

**requirements.txt:**

```
# FastAPI + Server
fastapi>=0.109
uvicorn[standard]>=0.27
websockets>=12.0

# Database
sqlalchemy[asyncio]>=2.0
aiosqlite>=0.19

# Validation
pydantic>=2.5

# Desktop GUI
PyQt6>=6.6

# HTTP Client (for instructor app)
httpx>=0.26

# File Handling
python-multipart>=0.0.6
aiofiles>=23.2

# Image Processing (optional)
Pillow>=10.2
```

---

# 5. QUESTION POOL & QUIZ BUILDER

## 5.1 Concept Overview

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         QUESTION POOL                                   │
│                    (Master repository of all questions)                 │
│                                                                         │
│   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐              │
│   │    Topic:     │   │    Topic:     │   │    Topic:     │              │
│   │    Math       │   │   Science     │   │   History     │   ...        │
│   ├───────────────┤   ├───────────────┤   ├───────────────┤              │
│   │  Q1: 2+2=?    │   │  Q5: H2O is?  │   │  Q8: 1776?    │              │
│   │  Q2: 5x3=?    │   │  Q6: Sun is?  │   │  Q9: WWII?    │              │
│   │  Q3: 10/2=?   │   │  Q7: DNA?     │   │  Q10: Egypt?  │              │
│   │  Q4: 7-3=?    │   │  ...         │   │  ...         │              │
│   └───────────────┘   └───────────────┘   └───────────────┘              │
│                                                                         │
└───────────────────────────────────────────────────────────────────────────┘
                    │                         │
                    ▼                         ▼
┌─────────────────────────────┐   ┌─────────────────────────────┐
│  Quiz: "Math Test Ch.1"   │   │  Quiz: "Science Final"    │
├─────────────────────────────┤   ├─────────────────────────────┤
│  1. Q1 (from Math)        │   │  1. Q5 (from Science)     │
│  2. Q3 (from Math)        │   │  2. Q6 (from Science)     │
│  3. Q2 (from Math)        │   │  3. Q7 (from Science)     │
└─────────────────────────────┘   └─────────────────────────────┘
         (editable)                   (editable)
```

## 5.2 Question Pool Management

| Operation | Description |
|-----------|-------------|
| **Create** | Add new questions to the pool with topic assignment |
| **Read** | Browse/search questions, filter by topic |
| **Update** | Edit question text, choices, image, time, or topic |
| **Delete** | Remove questions from pool (warns if used in quizzes) |

## 5.3 Topic Management

| Operation | Description |
|-----------|-------------|
| **Create** | Add new topics (e.g., "Algebra", "Chemistry", "Civil War") |
| **Read** | List all topics with question counts |
| **Update** | Rename topics |
| **Delete** | Remove topics (must reassign or delete questions first) |

## 5.4 Quiz Builder

| Operation | Description |
|-----------|-------------|
| **Create** | New quiz with name and description |
| **Add Questions** | Select questions from pool (any topic) |
| **Reorder** | Drag-and-drop to change question order |
| **Randomize Order** | Shuffle all questions into random order during quiz setup |
| **Remove Questions** | Remove questions from quiz (stays in pool) |
| **Edit** | Change quiz name, description, or questions at any time |
| **Delete** | Remove quiz (questions remain in pool) |

**Key Principle:** Questions exist independently in the pool. Quizzes are just ordered selections of questions. The same question can appear in multiple quizzes.

## 5.5 Quiz Lifecycle & Results Tracking

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           QUIZ LIFECYCLE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   QUIZ DEFINITION (saved, reusable)                                         │
│   ┌─────────────────────────────┐                                           │
│   │  Quiz: "Chapter 5 Review"   │                                           │
│   │  - 10 questions selected    │                                           │
│   │  - Saved in database        │                                           │
│   └─────────────────────────────┘                                           │
│                │                                                            │
│                │  Can be administered multiple times                        │
│                ▼                                                            │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        GAME SESSIONS                                │   │
│   │                                                                     │   │
│   │  Session #1              Session #2              Session #3         │   │
│   │  Jan 12, Period 1        Jan 12, Period 3        Jan 15, Period 1   │   │
│   │  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐│   │
│   │  │ Alice: 8500 pts │     │ Dan: 9200 pts   │     │ Alice: 9100 pts ││   │
│   │  │ Bob: 7200 pts   │     │ Eve: 8800 pts   │     │ Grace: 8900 pts ││   │
│   │  │ Carol: 6900 pts │     │ Frank: 7500 pts │     │ Henry: 8200 pts ││   │
│   │  └─────────────────┘     └─────────────────┘     └─────────────────┘│   │
│   │                                                                     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                │                                                            │
│                ▼                                                            │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                     RESULTS TRACKING                                │   │
│   │                                                                     │   │
│   │  Per Session:                    Per Student (by name):             │   │
│   │  - Date/time administered        - All sessions participated in    │   │
│   │  - All participants & scores     - Scores across sessions          │   │
│   │  - Per-question breakdown        - Per-question performance        │   │
│   │  - Game type used                - Progress over time              │   │
│   │                                                                     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key Concepts:**

| Concept | Description |
|---------|-------------|
| **Quiz** | A saved template — select questions once, administer many times |
| **GameSession** | One instance of administering a quiz (e.g., "Period 1 on Jan 12") |
| **Player** | A student's participation in one session (identified by name) |
| **Answer** | Each student's response to each question in a session |

**Results Queries:**
- "Show me all sessions of Quiz X" → List of GameSessions
- "Show me Alice's history" → Filter Players by name, join to sessions
- "How did Period 1 do vs Period 3?" → Compare sessions
- "Which questions are students missing most?" → Aggregate Answers by question

---

# 6. DATABASE SCHEMA

## 6.1 Entity Relationship Diagram

```
┌─────────────────────┐
│       Topic         │
├─────────────────────┤
│ id (PK)             │
│ name                │
│ description         │
│ created_at          │
└─────────────────────┘
         │
         │ 1
         │
         ▼ N
┌─────────────────────┐         ┌─────────────────────┐
│      Question       │         │        Quiz         │
├─────────────────────┤         ├─────────────────────┤
│ id (PK)             │         │ id (PK)             │
│ topic_id (FK)       │         │ name                │
│ question_type       │         │ description         │
│ text                │         │ created_at          │
│ image_filename      │◄───┐    └─────────────────────┘
│ correct_answer      │    │              │
│ wrong_answer_1      │    │              │ 1
│ wrong_answer_2 (?)  │    │              │
│ wrong_answer_3 (?)  │    │              ▼ N
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
├─────────────────────┤         ├─────────────────────┤
│ id (PK)             │◄────────│ session_id (FK)     │
│ quiz_id (FK)        │    1  N │ id (PK)             │
│ status              │         │ name                │
│ current_q_index     │         │ total_score         │
│ started_at          │         │ joined_at           │
│ ended_at            │         └─────────────────────┘
└─────────────────────┘                   │
         │                                │ 1
         │ 1                              │
         │                                ▼ N
         │                      ┌─────────────────────┐
         │                      │       Answer        │
         │                      ├─────────────────────┤
         └──────────────────────│ session_id (FK)     │
                           N    │ player_id (FK)      │
                                │ question_id (FK)    │
                                │ id (PK)             │
                                │ choice              │
                                │ response_time_ms    │
                                │ points_earned       │
                                │ is_correct          │
                                └─────────────────────┘
```

## 6.2 Table Definitions

### Topic
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Auto-increment ID |
| name | TEXT | NOT NULL, UNIQUE | Topic name (e.g., "Algebra") |
| description | TEXT | NULLABLE | Optional description |
| created_at | DATETIME | NOT NULL | Creation timestamp |

### Question
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Auto-increment ID |
| topic_id | INTEGER | FOREIGN KEY, NULLABLE | Reference to Topic (optional) |
| question_type | TEXT | NOT NULL, DEFAULT 'multiple_choice' | 'multiple_choice', 'true_false', or 'technician_ab' |
| text | TEXT | NULLABLE | Question text (optional if image-only) |
| image_filename | TEXT | NULLABLE | Filename of attached image |
| correct_answer | TEXT | NOT NULL | The correct answer text |
| wrong_answer_1 | TEXT | NOT NULL | First incorrect answer |
| wrong_answer_2 | TEXT | NULLABLE | Second incorrect answer (NULL for true/false) |
| wrong_answer_3 | TEXT | NULLABLE | Third incorrect answer (NULL for true/false) |
| time_seconds | INTEGER | NOT NULL, DEFAULT 10 | Time limit (5-15 seconds) |
| created_at | DATETIME | NOT NULL | Creation timestamp |

**Question Types:**

| Type | Answers | Elimination | Randomized |
|------|---------|-------------|------------|
| `multiple_choice` | 4 (1 correct + 3 wrong) | Yes, at 33% and 66% | Yes |
| `true_false` | 2 (True/False) | No | No |
| `technician_ab` | 4 (fixed choices) | Yes, at 33% and 66% | No |

**Technician A/B Format (ASE Style):**
```
Question: "A vehicle has [problem]. Technician A says [statement A].
           Technician B says [statement B]. Who is correct?"

Choices (always in this order):
  A) Technician A only
  B) Technician B only
  C) Both Technician A and Technician B
  D) Neither Technician A nor Technician B

Correct answer stored as: 'A', 'B', 'C', or 'D'
```

**Randomization at Display Time:**
- **Multiple choice:** All 4 answers shuffled into random A/B/C/D positions each session
- **True/False:** Always A) True, B) False (fixed order)
- **Technician A/B:** Always A) Tech A, B) Tech B, C) Both, D) Neither (fixed order)
- Server tracks which position holds the correct answer
- Elimination applies to multiple choice and technician_ab questions

### Quiz
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Auto-increment ID |
| name | TEXT | NOT NULL | Quiz title |
| description | TEXT | NULLABLE | Optional description |
| randomize_order | BOOLEAN | NOT NULL, DEFAULT FALSE | Whether to shuffle question order each session |
| created_at | DATETIME | NOT NULL | Creation timestamp |

### QuizQuestion
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Auto-increment ID |
| quiz_id | INTEGER | FOREIGN KEY | Reference to Quiz |
| question_id | INTEGER | FOREIGN KEY | Reference to Question |
| position | INTEGER | NOT NULL | Order in quiz (1, 2, 3...) |

### GameSession
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Auto-increment ID |
| quiz_id | INTEGER | FOREIGN KEY | Reference to Quiz being played |
| game_type | TEXT | NOT NULL | Game module used: 'pointdrop', 'standard_test', etc. |
| status | TEXT | NOT NULL | waiting / active / finished |
| current_q_index | INTEGER | NOT NULL | Current question position |
| started_at | DATETIME | NULLABLE | When session started |
| ended_at | DATETIME | NULLABLE | When session ended |

### Player
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Auto-increment ID |
| session_id | INTEGER | FOREIGN KEY | Reference to GameSession |
| name | TEXT | NOT NULL | Student's display name |
| total_score | INTEGER | NOT NULL, DEFAULT 0 | Cumulative score |
| joined_at | DATETIME | NOT NULL | When player joined |

### Answer
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Auto-increment ID |
| player_id | INTEGER | FOREIGN KEY | Reference to Player |
| question_id | INTEGER | FOREIGN KEY | Reference to Question |
| session_id | INTEGER | FOREIGN KEY | Reference to GameSession |
| selected_answer | TEXT | NULLABLE | The answer text selected (not a letter) |
| response_time_ms | INTEGER | NOT NULL | Milliseconds to answer |
| points_earned | INTEGER | NOT NULL | Points awarded |
| is_correct | BOOLEAN | NOT NULL | Whether answer was correct |

---

## 6.3 Answer Randomization Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    DATABASE (Question Pool)                         │
│                                                                     │
│   Question #42:                                                     │
│   - text: "What is the capital of France?"                         │
│   - correct_answer: "Paris"                                         │
│   - wrong_answer_1: "London"                                        │
│   - wrong_answer_2: "Berlin"                                        │
│   - wrong_answer_3: "Madrid"                                        │
│                                                                     │
└─────────────────────────────────┴─────────────────────────────────────┘
                                  │
                                  ▼  Server shuffles at display time
                                  
┌─────────────────────────────────────────────────────────────────────────┐
│                    GAME SESSION (Runtime)                           │
│                                                                     │
│   Displayed to students (randomized):                               │
│   - A) Berlin                                                       │
│   - B) Paris        ◄── correct (server tracks this)                │
│   - C) Madrid                                                       │
│   - D) London                                                       │
│                                                                     │
│   Elimination order (also randomized): D → A → (B & C remain)       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

**How it works:**
1. **Question stored** with correct + 3 wrong answers (no letter assignment)
2. **Game starts** → server randomly assigns answers to A/B/C/D positions
3. **Server remembers** which position has the correct answer for this session
4. **Eliminations** → server picks random wrong answers to disable (not always A first)
5. **Student answers** → server compares selected text to `correct_answer` field
6. **Next question** → shuffle again with new random positions

---

## 6.4 Question Order Randomization

### Overview

When `quiz.randomize_order = TRUE`, the server shuffles the question order at the start of each game session. This ensures students experience a different question sequence each time the quiz is administered, while maintaining consistent answer randomization for each question.

### Randomization Flow

```
DATABASE (Quiz Definition)                     GAME SESSION (Runtime)
                                                
Quiz: "Chapter 5 Review"                        Session #1 (Jan 12):
- randomize_order: TRUE                         - Q3, Q1, Q4, Q2, Q5
- Questions in position order:                  Session #2 (Jan 15):
  1. Q1: "What is 2+2?"                          - Q5, Q2, Q1, Q3, Q4
  2. Q2: "What is 5x3?"                          Session #3 (Jan 20):
  3. Q3: "What is 10/2?"                         - Q2, Q4, Q1, Q5, Q3
  4. Q4: "What is 7-3?"
  5. Q5: "What is 8+1?"
```

### Implementation Logic

1. **Quiz Creation**: Instructor sets `randomize_order = TRUE` in Quiz Builder
2. **Session Start**: Server queries QuizQuestions ordered by `position`
3. **Shuffle**: Python's `random.shuffle()` creates new question order
4. **Session Storage**: Randomized order stored in memory for the session
5. **Question Progression**: `GameSession.current_q_index` advances through shuffled list
6. **Answer Tracking**: Each answer records the original `question_id` for analytics

### Key Benefits

- **Fair Assessment**: Different question orders reduce cheating potential
- **Fresh Experience**: Students can't memorize question sequences
- **Consistent Analytics**: Results tracked by original question IDs
- **Flexible Design**: Instructors can toggle randomization per quiz

### Technical Implementation

```python
# When starting a new game session
async def start_session(quiz_id: int):
    quiz = await get_quiz(quiz_id)
    questions = await get_quiz_questions(quiz_id)  # Ordered by position
    
    if quiz.randomize_order:
        random.shuffle(questions)  # In-place shuffle
    
    session = await create_game_session(
        quiz_id=quiz_id,
        question_order=[q.id for q in questions]  # Store shuffled order
    )
    
    return session
```

---

# 7. GAME MECHANICS

## 7.1 Quiz Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              QUIZ LIFECYCLE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   SETUP              WAITING            ACTIVE              FINISHED        │
│     │                   │                  │                    │           │
│     ▼                   ▼                  ▼                    ▼           │
│  ┌──────┐          ┌──────────┐       ┌──────────┐        ┌──────────┐     │
│  │Create│          │ Students │       │ Question │        │  Final   │     │
│  │ Quiz │────────▶ │   Join   │─────▶ │   Loop   │──────▶ │ Results  │     │
│  └──────┘          └──────────┘       └──────────┘        └──────────┘     │
│                                             │                               │
│                                             ▼                               │
│                                    ┌─────────────────┐                      │
│                                    │  For each Q:    │                      │
│                                    │  1. Show Q      │                      │
│                                    │  2. Timer runs  │                      │
│                                    │  3. Eliminate   │                      │
│                                    │  4. Collect A's │                      │
│                                    │  5. Reveal ans  │                      │
│                                    │  6. Show scores │                      │
│                                    │  7. WAIT for    │                      │
│                                    │     instructor  │                      │
│                                    │  8. Next Q      │                      │
│                                    └─────────────────┘                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 7.2 Single Question Timeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  QUESTION TIMELINE (Example: 12-second question)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  TIME:    0s        3s         6s         9s         12s                    │
│           │         │          │          │          │                      │
│           ▼         ▼          ▼          ▼          ▼                      │
│           ├─────────┼──────────┼──────────┼──────────┤                      │
│           │         │          │          │          │                      │
│  POINTS:  1000 ───────────────────────────────────▶ 100                     │
│           (decreasing continuously every ~100ms)                            │
│                                                                             │
│  CHOICES: [A][B][C][D]        [B][C][D]         [B][D]                      │
│           4 available         3 available       2 available                 │
│                     │                │                                      │
│                     ▼                ▼                                      │
│                 Eliminate        Eliminate                                  │
│                    A                C                                       │
│                 (wrong)          (wrong)                                    │
│                                                                             │
│  EVENTS:  Question        33%            66%                 Time           │
│           Starts          mark           mark                Expires               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 7.3 Scoring System

### Continuous Score Decay Formula

```
points = max_points - (elapsed_ms / total_ms) × (max_points - min_points)
```

### Configuration

| Parameter | Value |
|-----------|-------|
| Maximum Points | 1000 |
| Minimum Points | 100 |
| Decay Rate | Continuous (calculated per millisecond) |

### Example Score Table (10-second question)

| Response Time | Points Earned |
|---------------|---------------|
| 0.0 seconds | 1000 |
| 1.0 seconds | 910 |
| 2.0 seconds | 820 |
| 3.0 seconds | 730 |
| 4.0 seconds | 640 |
| 5.0 seconds | 550 |
| 6.0 seconds | 460 |
| 7.0 seconds | 370 |
| 8.0 seconds | 280 |
| 9.0 seconds | 190 |
| 10.0 seconds | 100 |

### Scoring Rules

- **Correct answer** → Earn points based on response time
- **Wrong answer** → 0 points
- **No answer** → 0 points
- **Ties** → Extremely rare due to millisecond precision

## 7.4 Answer Elimination

| Time Mark | Action | Choices Remaining |
|-----------|--------|-------------------|
| 0% | Question appears | 4 (A, B, C, D) |
| 33% | Eliminate 1 wrong answer | 3 |
| 66% | Eliminate 1 wrong answer | 2 |
| 100% | Time expires | 2 (student must choose) |
| Post | Correct answer revealed | Instructor advances |

**Rules:**
- Only **incorrect** answers are eliminated (never the correct one)
- Elimination order is **randomized** each question
- Students who haven't answered yet see disabled choices
- Students who already answered are unaffected
- **Quiz always ends with 2 choices** — student must earn final points by selecting correctly
- **Correct answer is revealed** when timer expires
- **Instructor manually advances** to the next question (no auto-advance)

## 7.5 Per-Question Time Limits

| Setting | Value |
|---------|-------|
| Default | 10 seconds |
| Minimum | 5 seconds |
| Maximum | 30 seconds |
| Configured | Per question in the pool |

---

# 8. USER INTERFACES

## 8.1 Student Screens

### Screen 1: Join Page

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                                                                             │
│                               🎮 COGNIT                                     │
│                                                                             │
│                          Join the Quiz                                      │
│                                                                             │
│                     ┌─────────────────────────────┐                         │
│                     │  Enter your name            │                         │
│                     └─────────────────────────────┘                         │
│                                                                             │
│                          [ Join Game ]                                      │
│                                                                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Screen 2: Waiting Room

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                               🎮 COGNIT                                     │
│                                                                             │
│                     Welcome, Johnny! ✓                                      │
│                                                                             │
│                     ┌─────────────────────────────┐                         │
│                     │                             │                         │
│                     │   ⏳ Waiting for quiz       │                         │
│                     │      to start...            │                         │
│                     │                             │                         │
│                     │   12 players joined         │                         │
│                     │                             │                         │
│                     └─────────────────────────────┘                         │
│                                                                             │
│                     Players: Johnny, Sarah, Mike, Emma, ...                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Screen 3: Active Question (All Choices Available)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Question 3 of 10                                     ⏱️ 8s     💰 640 pts  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                     ┌─────────────────────────────┐                         │
│                     │                             │                         │
│                     │      [ IMAGE HERE ]         │                         │
│                     │    (if question has one)    │                         │
│                     └─────────────────────────────┘                         │
│                                                                             │
│          What element is shown in this periodic table section?              │
│                                                                             │
│   ┌───────────────────────────────┐   ┌───────────────────────────────┐    │
│   │                               │   │                               │    │
│   │         A) Hydrogen           │   │         B) Helium             │    │
│   │                               │   │                               │    │
│   └───────────────────────────────┘   └───────────────────────────────┘    │
│                                                                             │
│   ┌───────────────────────────────┐   ┌───────────────────────────────┐    │
│   │                               │   │                               │    │
│   │         C) Lithium            │   │         D) Carbon             │    │
│   │                               │   │                               │    │
│   └───────────────────────────────┘   └───────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Screen 4: Choices Being Eliminated

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Question 3 of 10                                     ⏱️ 4s     💰 320 pts  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                     ┌─────────────────────────────┐                         │
│                     │      [ IMAGE HERE ]         │                         │
│                     └─────────────────────────────┘                         │
│                                                                             │
│          What element is shown in this periodic table section?              │
│                                                                             │
│   ┌───────────────────────────────┐   ┌───────────────────────────────┐    │
│   │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │   │                               │    │
│   │ ░░░░░░░░ ELIMINATED ░░░░░░░░ │   │         B) Helium             │    │
│   │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │   │                               │    │
│   └───────────────────────────────┘   └───────────────────────────────┘    │
│                                                                             │
│   ┌───────────────────────────────┐   ┌───────────────────────────────┐    │
│   │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │   │                               │    │
│   │ ░░░░░░░░ ELIMINATED ░░░░░░░░ │   │         D) Carbon             │    │
│   │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │   │                               │    │
│   └───────────────────────────────┘   └───────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Screen 5: Answer Submitted (Locked In)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Question 3 of 10                                     ⏱️ 3s     💰 280 pts  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                     ┌─────────────────────────────┐                         │
│                     │      [ IMAGE HERE ]         │                         │
│                     └─────────────────────────────┘                         │
│                                                                             │
│          What element is shown in this periodic table section?              │
│                                                                             │
│   ┌───────────────────────────────┐   ╔═══════════════════════════════╗    │
│   │ ░░░░░░░░ ELIMINATED ░░░░░░░░ │   ║   ✓ YOUR ANSWER               ║    │
│   └───────────────────────────────┘   ║         B) Helium             ║    │
│                                       ╚═══════════════════════════════╝    │
│   ┌───────────────────────────────┐   ┌───────────────────────────────┐    │
│   │ ░░░░░░░░ ELIMINATED ░░░░░░░░ │   │         D) Carbon             │    │
│   └───────────────────────────────┘   └───────────────────────────────┘    │
│                                                                             │
│                      ⏳ Waiting for time to expire...                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Screen 6: Answer Revealed — Correct

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Question 3 of 10                                              RESULTS      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                          ✅ CORRECT!                                        │
│                                                                             │
│                         +730 points                                         │
│                                                                             │
│   ┌───────────────────────────────┐   ╔═══════════════════════════════╗    │
│   │         A) Hydrogen           │   ║   ✓ CORRECT ANSWER            ║    │
│   └───────────────────────────────┘   ║         B) Helium             ║    │
│                                       ╚═══════════════════════════════╝    │
│   ┌───────────────────────────────┐   ┌───────────────────────────────┐    │
│   │         C) Lithium            │   │         D) Carbon             │    │
│   └───────────────────────────────┘   └───────────────────────────────┘    │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │   Your Score: 2,450 pts                         Rank: 3rd / 24      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│                  ⏳ Waiting for instructor to continue...                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Screen 7: Answer Revealed — Incorrect

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Question 3 of 10                                              RESULTS      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                          ❌ INCORRECT                                       │
│                                                                             │
│                          +0 points                                          │
│                                                                             │
│   ┌───────────────────────────────┐   ╔═══════════════════════════════╗    │
│   │         A) Hydrogen           │   ║   ✓ CORRECT ANSWER            ║    │
│   └───────────────────────────────┘   ║         B) Helium             ║    │
│                                       ╚═══════════════════════════════╝    │
│   ┌───────────────────────────────┐   ┌───────────────────────────────┐    │
│   │   ✗ YOUR ANSWER               │   │         D) Carbon             │    │
│   │         C) Lithium            │   │                               │    │
│   └───────────────────────────────┘   └───────────────────────────────┘    │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │   Your Score: 1,700 pts                         Rank: 8th / 24      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│                  ⏳ Waiting for instructor to continue...                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Screen 8: Final Results

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                          🏆 QUIZ COMPLETE! 🏆                               │
│                                                                             │
│                          Your Final Score                                   │
│                            6,250 pts                                        │
│                                                                             │
│                          🥉 3rd Place 🥉                                    │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │   LEADERBOARD                                                       │  │
│   ├─────────────────────────────────────────────────────────────────────┤  │
│   │   🥇  1. Sarah              7,500 pts                               │  │
│   │   🥈  2. Mike               6,750 pts                               │  │
│   │   🥉  3. Johnny (You)       6,250 pts                               │  │
│   │       4. Emma               5,500 pts                               │  │
│   │       5. Alex               5,250 pts                               │  │
│   │       ...                                                           │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│                    Correct: 7/10    Accuracy: 70%                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8.2 Instructor Display Window (Projector)

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                                                              ⏱️ 8s            │
│                                                           ████████░░░░░░░░░░░  │
│                                                                                │
│    Question 3 of 10                                           640 points       │
│                                                                                │
│   ┌──────────────────────────────────────────────────────────────────────────┐ │
│   │                                                                          │ │
│   │    What element is shown in this periodic table section?                 │ │
│   │                                                                          │ │
│   └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│                        ┌──────────────────────────┐                            │
│                        │                          │                            │
│                        │      [ IMAGE HERE ]      │                            │
│                        │                          │                            │
│                        └──────────────────────────┘                            │
│                                                                                │
│    ┌───────────────────────────┐      ┌───────────────────────────┐           │
│    │      A) Hydrogen          │      │      B) Helium            │           │
│    └───────────────────────────┘      └───────────────────────────┘           │
│                                                                                │
│    ┌───────────────────────────┐      ┌───────────────────────────┐           │
│    │  ░░░░ ELIMINATED ░░░░░░░░ │      │      D) Carbon            │           │
│    └───────────────────────────┘      └───────────────────────────┘           │
│                                                                                │
│    Answers: 18/24 students                                                     │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 8.3 Instructor Admin Window

### Question Editor

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Cognit - Question Editor                                        [_][□][X]  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Question Text:                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ What element is shown in this periodic table section?               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Image (optional):                                                          │
│  ┌─────────────────────────┐                                                │
│  │                         │   [ Browse... ]   [ Remove ]                   │
│  │   📷 periodic.png       │                                                │
│  │                         │                                                │
│  └─────────────────────────┘                                                │
│                                                                             │
│  Time Limit:    ◀────────●──────▶    10 seconds                             │
│                 5s                15s                                       │
│                                                                             │
│  Answer Choices:                                                            │
│  A: [ Hydrogen          ]      B: [ Helium            ]                     │
│  C: [ Lithium           ]      D: [ Carbon            ]                     │
│                                                                             │
│  Correct Answer:  ( ) A   (•) B   ( ) C   ( ) D                             │
│                                                                             │
│  Category: [ Chemistry        ▼ ]                                           │
│                                                                             │
│                        [ Cancel ]   [ Save Question ]                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Quiz Control Panel

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Cognit - Quiz Control                                           [_][□][X]  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Quiz: Chemistry Chapter 5                          Status: ACTIVE          │
│  Question: 3 of 10                                  Players: 24             │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Current Question:                                                  │   │
│  │  "What element is shown in this periodic table section?"            │   │
│  │                                                                     │   │
│  │  Time Remaining: 8s          Answers Received: 18/24                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Controls:                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   ▶ START   │  │  ⏸ PAUSE   │  │  ⏭ SKIP    │  │  ⏹ END     │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                                             │
│  Live Leaderboard:                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  1. Sarah          2,180 pts                                        │   │
│  │  2. Mike           2,050 pts                                        │   │
│  │  3. Johnny         1,720 pts                                        │   │
│  │  4. Emma           1,680 pts                                        │   │
│  │  5. Alex           1,540 pts                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  [ Open Display Window ]                              [ Export Results ]    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# 9. WEBSOCKET EVENTS

## 9.1 Event Reference

| Event | Direction | Payload |
|-------|-----------|---------|
| `player_join` | Student → Server | `{name: string}` |
| `player_joined` | Server → All | `{player_id, name, player_count}` |
| `player_left` | Server → All | `{player_id, name, player_count}` |
| `game_start` | Server → All | `{quiz_name, question_count}` |
| `question_start` | Server → All | `{index, text, image_url, choices, time_seconds, max_points}` |
| `points_update` | Server → All | `{current_points}` (sent every 100ms) |
| `choice_eliminated` | Server → All | `{choice, remaining_choices}` |
| `submit_answer` | Student → Server | `{choice, elapsed_ms}` |
| `answer_confirmed` | Server → Student | `{choice, locked: true}` |
| `answer_count` | Server → Instructor | `{answered, total}` |
| `question_end` | Server → All | `{correct_choice, player_scores[]}` |
| `game_end` | Server → All | `{final_rankings[], stats}` |

## 9.2 Event Flow Diagram

```
INSTRUCTOR              SERVER                 STUDENTS (all)
    │                      │                        │
    │── select_quiz ──────▶│                        │
    │                      │                        │
    │                      │◀──── player_join ──────│
    │◀─ player_joined ─────│───── player_joined ───▶│
    │                      │                        │
    │── start_game ───────▶│                        │
    │                      │───── game_start ──────▶│
    │                      │                        │
    │                      │                        │
    │  ╔════════════════════════════════════════╗  │
    │  ║  REPEAT FOR EACH QUESTION              ║  │
    │  ╠════════════════════════════════════════╣  │
    │  ║                   │                    ║  │
    │  ║   │── next_q ────▶│                    ║  │
    │  ║   │               │── question_start ─▶│  │
    │  ║   │               │                    ║  │
    │  ║   │               │   [Timer runs]     ║  │
    │  ║   │               │── points_update ──▶│  │
    │  ║   │               │── choice_elim ────▶│  │
    │  ║   │               │                    ║  │
    │  ║   │               │◀── submit_answer ──│  │
    │  ║   │◀─ answer_cnt ─│── answer_confirm ─▶│  │
    │  ║   │               │                    ║  │
    │  ║   │── reveal ────▶│                    ║  │
    │  ║   │               │── question_end ───▶│  │
    │  ║   │               │                    ║  │
    │  ╚════════════════════════════════════════╝  │
    │                      │                        │
    │── end_game ─────────▶│                        │
    │                      │────── game_end ───────▶│
    │                      │                        │
```

---

# 10. PROJECT STRUCTURE

```
Cognit/
│
├── server/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Settings (port, DB path, etc.)
│   ├── database.py                # Async SQLAlchemy setup
│   ├── models.py                  # ORM models (Cognit Core)
│   ├── schemas.py                 # Pydantic request/response models
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── topics.py              # CRUD for topics
│   │   ├── questions.py           # CRUD for questions
│   │   ├── quizzes.py             # CRUD for quizzes
│   │   ├── sessions.py            # Session management
│   │   └── results.py             # Results tracking & analytics
│   │
│   ├── websocket/
│   │   ├── __init__.py
│   │   ├── manager.py             # WebSocket connection manager
│   │   └── base_handler.py        # Base game handler interface
│   │
│   └── games/                     # GAME MODULES (extensible)
│       ├── __init__.py
│       ├── base.py                # Abstract base game class
│       │
│       └── pointdrop/             # PointDrop game module
│           ├── __init__.py
│           ├── engine.py          # PointDrop game state machine
│           ├── scoring.py         # Continuous decay scoring
│           ├── elimination.py     # Answer elimination logic
│           └── handlers.py        # PointDrop WebSocket handlers
│
├── instructor/
│   ├── __init__.py
│   ├── main.py                    # PyQt6 app entry point
│   ├── api_client.py              # HTTP client to server
│   │
│   ├── core/                      # Cognit Core UI
│   │   ├── __init__.py
│   │   ├── topic_manager.py       # Topic CRUD
│   │   ├── question_pool.py       # Question pool management
│   │   ├── quiz_builder.py        # Quiz assembly
│   │   └── results_viewer.py      # Session results & analytics
│   │
│   └── games/                     # Game-specific UI
│       └── pointdrop/
│           ├── __init__.py
│           ├── control_panel.py   # Live PointDrop control
│           └── display_window.py  # Fullscreen projector view
│
├── static/                        # Student web UI
│   ├── index.html                 # Game selection / join page
│   │
│   └── pointdrop/                 # PointDrop student UI
│       ├── game.html              # PointDrop game page
│       ├── css/
│       │   └── styles.css         # PointDrop styles
│       └── js/
│           └── game.js            # WebSocket + game UI
│
├── media/                         # Uploaded files
│   └── questions/                 # Question images
│       ├── q_001.png
│       └── ...
│
├── data/
│   └── cognit.db                  # SQLite database
│
├── requirements.txt               # Python dependencies
├── run_server.py                  # Launch uvicorn server
├── run_instructor.py              # Launch PyQt6 instructor app
└── README.md                      # Project documentation
```

---

# 11. IMAGE HANDLING

## 11.1 Supported Formats

| Format | Extension |
|--------|-----------|
| PNG | .png |
| JPEG | .jpg, .jpeg |
| GIF | .gif |
| WebP | .webp |

## 11.2 Constraints

| Constraint | Value |
|------------|-------|
| Maximum file size | 5 MB |
| Maximum dimensions | 1920 × 1080 (optional resize) |
| Storage location | `media/questions/` |
| Naming convention | `q_{question_id}_{timestamp}.{ext}` |

## 11.3 Question Types

| Type | text | image_filename |
|------|------|----------------|
| Text only | Filled | NULL |
| Image only | Empty | Filled |
| Text + Image | Filled | Filled |

---

# 12. BUILD ORDER

| Phase | Component | Task | Description |
|-------|-----------|------|-------------|
| 1 | Setup | Project Setup | Create folder structure, requirements.txt |
| 2 | Core | Database Models | SQLAlchemy models for Cognit Core |
| 3 | Core | REST API | Topics, Questions, Quizzes, Results endpoints |
| 4 | Core | Instructor UI | PyQt6 topic/question/quiz management |
| 5 | Core | Results Tracker | Session logging and analytics |
| 6 | PointDrop | Game Engine | Scoring, elimination, state machine |
| 7 | PointDrop | WebSocket | Connection manager, PointDrop handlers |
| 8 | PointDrop | Student UI | HTML/CSS/JS join and game pages |
| 9 | PointDrop | Instructor UI | Control panel + display window |
| 10 | All | Integration | Connect all components, test flow |
| 11 | All | Polish | Error handling, edge cases, UX improvements |

---

# 13. SUMMARY

**Cognit** is a modular educational assessment platform featuring:

**Cognit Core:**
- **Question Pool Management** — Organized by topics with full CRUD
- **Quiz Builder** — Assemble assessments from the question pool
- **Results Tracking** — Store and analyze all session outcomes
- **Extensible Architecture** — Add new game modules without modifying the core

**PointDrop Game Module:**
- **Game show mechanics** — Progressive elimination + continuous scoring
- **Real-time competition** — All students answer simultaneously
- **Dual display** — Control panel + fullscreen projector window
- **Per-question time limits** — 5-30 seconds configurable

**Technology:**
- **FastAPI backend** with native WebSocket support
- **SQLite database** for portable, file-based storage
- **PyQt6 instructor application** with modular UI
- **Browser-based student interface** accessible on any laptop

**Future Expansion:**
- Standard timed tests (no game mechanics)
- Team competition modes
- Tournament brackets
- Additional game types

---

*Document generated: January 12, 2026*
