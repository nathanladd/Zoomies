import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.config import MEDIA_DIR, ALLOWED_IMAGE_EXTENSIONS, MAX_IMAGE_SIZE
from server.database import get_db
from server.models import Question
from server.schemas import QuestionCreate, QuestionUpdate, QuestionRead

router = APIRouter(prefix="/api/questions", tags=["questions"])


def _question_to_read(q: Question) -> QuestionRead:
    return QuestionRead(
        id=q.id, topic_id=q.topic_id, question_type=q.question_type,
        text=q.text, image_filename=q.image_filename,
        correct_answer=q.correct_answer, wrong_answer_1=q.wrong_answer_1,
        wrong_answer_2=q.wrong_answer_2, wrong_answer_3=q.wrong_answer_3,
        time_seconds=q.time_seconds, created_at=q.created_at,
        topic_name=q.topic.name if q.topic else None,
    )


@router.get("", response_model=list[QuestionRead])
async def list_questions(
    topic_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Question).order_by(Question.id.desc())
    if topic_id is not None:
        stmt = stmt.where(Question.topic_id == topic_id)
    result = await db.execute(stmt)
    return [_question_to_read(q) for q in result.scalars().all()]


@router.get("/{question_id}", response_model=QuestionRead)
async def get_question(question_id: int, db: AsyncSession = Depends(get_db)):
    q = await db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "Question not found")
    return _question_to_read(q)


@router.post("", response_model=QuestionRead, status_code=201)
async def create_question(body: QuestionCreate, db: AsyncSession = Depends(get_db)):
    q = Question(
        topic_id=body.topic_id,
        question_type=body.question_type,
        text=body.text,
        correct_answer=body.correct_answer,
        wrong_answer_1=body.wrong_answer_1,
        wrong_answer_2=body.wrong_answer_2,
        wrong_answer_3=body.wrong_answer_3,
        time_seconds=body.time_seconds,
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return _question_to_read(q)


@router.put("/{question_id}", response_model=QuestionRead)
async def update_question(
    question_id: int, body: QuestionUpdate, db: AsyncSession = Depends(get_db),
):
    q = await db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "Question not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(q, field, value)
    await db.commit()
    await db.refresh(q)
    return _question_to_read(q)


@router.delete("/{question_id}", status_code=204)
async def delete_question(question_id: int, db: AsyncSession = Depends(get_db)):
    q = await db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "Question not found")
    if q.image_filename:
        img_path = MEDIA_DIR / q.image_filename
        if img_path.exists():
            img_path.unlink()
    await db.delete(q)
    await db.commit()


@router.post("/{question_id}/image", response_model=QuestionRead)
async def upload_image(
    question_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    q = await db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "Question not found")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(400, f"Unsupported image type: {ext}")

    data = await file.read()
    if len(data) > MAX_IMAGE_SIZE:
        raise HTTPException(400, "Image exceeds 5 MB limit")

    if q.image_filename:
        old = MEDIA_DIR / q.image_filename
        if old.exists():
            old.unlink()

    filename = f"q_{question_id}_{int(time.time())}{ext}"
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    (MEDIA_DIR / filename).write_bytes(data)

    q.image_filename = filename
    await db.commit()
    await db.refresh(q)
    return _question_to_read(q)


@router.delete("/{question_id}/image", status_code=204)
async def delete_image(question_id: int, db: AsyncSession = Depends(get_db)):
    q = await db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "Question not found")
    if q.image_filename:
        img_path = MEDIA_DIR / q.image_filename
        if img_path.exists():
            img_path.unlink()
        q.image_filename = None
        await db.commit()
