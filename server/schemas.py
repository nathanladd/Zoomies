from datetime import datetime

from pydantic import BaseModel, Field


# ── Topic ──────────────────────────────────────────────────────────────────────

class TopicCreate(BaseModel):
    name: str
    description: str | None = None

class TopicUpdate(BaseModel):
    name: str | None = None
    description: str | None = None

class TopicRead(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: datetime
    question_count: int = 0

    model_config = {"from_attributes": True}


# ── Question ───────────────────────────────────────────────────────────────────

class QuestionCreate(BaseModel):
    topic_id: int | None = None
    question_type: str = "multiple_choice"
    text: str | None = None
    correct_answer: str
    wrong_answer_1: str
    wrong_answer_2: str | None = None
    wrong_answer_3: str | None = None
    time_seconds: int = Field(default=10, ge=5, le=30)

class QuestionUpdate(BaseModel):
    topic_id: int | None = None
    question_type: str | None = None
    text: str | None = None
    correct_answer: str | None = None
    wrong_answer_1: str | None = None
    wrong_answer_2: str | None = None
    wrong_answer_3: str | None = None
    time_seconds: int | None = Field(default=None, ge=5, le=30)

class QuestionRead(BaseModel):
    id: int
    topic_id: int | None
    question_type: str
    text: str | None
    image_filename: str | None
    correct_answer: str
    wrong_answer_1: str
    wrong_answer_2: str | None
    wrong_answer_3: str | None
    time_seconds: int
    created_at: datetime
    topic_name: str | None = None

    model_config = {"from_attributes": True}


# ── Quiz ───────────────────────────────────────────────────────────────────────

class QuizCreate(BaseModel):
    name: str
    description: str | None = None
    randomize_order: bool = False

class QuizUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    randomize_order: bool | None = None

class QuizQuestionAdd(BaseModel):
    question_id: int
    position: int | None = None

class QuizQuestionReorder(BaseModel):
    question_ids: list[int]

class QuizQuestionRead(BaseModel):
    id: int
    question_id: int
    position: int
    question: QuestionRead | None = None

    model_config = {"from_attributes": True}

class QuizRead(BaseModel):
    id: int
    name: str
    description: str | None
    randomize_order: bool
    created_at: datetime
    question_count: int = 0

    model_config = {"from_attributes": True}

class QuizDetailRead(QuizRead):
    questions: list[QuizQuestionRead] = []


# ── Game ─────────────────────────────────────────────────────────────────────────────────

class GameCreate(BaseModel):
    quiz_id: int

class GameRead(BaseModel):
    id: int
    quiz_id: int
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    player_count: int = 0
    quiz_name: str | None = None

    model_config = {"from_attributes": True}


# ── Player ─────────────────────────────────────────────────────────────────────

class PlayerRead(BaseModel):
    id: int
    game_id: int
    name: str
    total_score: int
    joined_at: datetime

    model_config = {"from_attributes": True}


# ── Admin (backup / restore) ───────────────────────────────────────────────────

class BackupResult(BaseModel):
    path: str
    size_bytes: int
    created_at: datetime

class RestoreRequest(BaseModel):
    path: str
