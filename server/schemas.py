from datetime import datetime

from pydantic import BaseModel, Field

from server.constants import TIME_DEFAULT, TIME_MIN, TIME_MAX


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
    time_seconds: int = Field(default=TIME_DEFAULT, ge=TIME_MIN, le=TIME_MAX)
    randomize_answers: bool | None = None
    correct_index: int = Field(default=0, ge=0, le=3)

class QuestionUpdate(BaseModel):
    topic_id: int | None = None
    question_type: str | None = None
    text: str | None = None
    correct_answer: str | None = None
    wrong_answer_1: str | None = None
    wrong_answer_2: str | None = None
    wrong_answer_3: str | None = None
    time_seconds: int | None = Field(default=None, ge=TIME_MIN, le=TIME_MAX)
    randomize_answers: bool | None = None
    correct_index: int | None = Field(default=None, ge=0, le=3)

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
    randomize_answers: bool = True
    correct_index: int = 0
    created_at: datetime
    topic_name: str | None = None

    model_config = {"from_attributes": True}


# ── Note ───────────────────────────────────────────────────────────────────────

class NoteUpsert(BaseModel):
    discussion: str | None = None
    citations: str | None = None

class NoteRead(BaseModel):
    id: int
    question_id: int
    discussion: str | None
    citations: str | None
    created_at: datetime
    updated_at: datetime

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
    join_code: str | None = None
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
