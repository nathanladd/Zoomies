from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    questions: Mapped[list["Question"]] = relationship(back_populates="topic", lazy="selectin")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    question_type: Mapped[str] = mapped_column(String, nullable=False, default="multiple_choice")
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    correct_answer: Mapped[str] = mapped_column(String, nullable=False)
    wrong_answer_1: Mapped[str] = mapped_column(String, nullable=False)
    wrong_answer_2: Mapped[str | None] = mapped_column(String, nullable=True)
    wrong_answer_3: Mapped[str | None] = mapped_column(String, nullable=True)
    time_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    randomize_answers: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Position (0-3 → A/B/C/D) of the correct answer when randomize_answers is False.
    # Only meaningful for multiple_choice. Ignored when randomize_answers is True.
    correct_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    topic: Mapped[Topic | None] = relationship(back_populates="questions", lazy="selectin")
    quiz_links: Mapped[list["QuizQuestion"]] = relationship(
        back_populates="question", lazy="selectin",
        cascade="all, delete-orphan", passive_deletes=True,
    )


class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    randomize_order: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    quiz_questions: Mapped[list["QuizQuestion"]] = relationship(
        back_populates="quiz", lazy="selectin", order_by="QuizQuestion.position",
        cascade="all, delete-orphan", passive_deletes=True,
    )
    games: Mapped[list["Game"]] = relationship(
        back_populates="quiz", lazy="selectin",
        cascade="all, delete-orphan", passive_deletes=True,
    )


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quiz_id: Mapped[int] = mapped_column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    quiz: Mapped[Quiz] = relationship(back_populates="quiz_questions", lazy="selectin")
    question: Mapped[Question] = relationship(back_populates="quiz_links", lazy="selectin")


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quiz_id: Mapped[int] = mapped_column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="waiting")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    quiz: Mapped[Quiz] = relationship(back_populates="games", lazy="selectin")
    players: Mapped[list["Player"]] = relationship(back_populates="game", lazy="selectin", cascade="all, delete-orphan")


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    total_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    game: Mapped[Game] = relationship(back_populates="players", lazy="selectin")
