import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.auth import require_auth
from server.config import MEDIA_DIR, ALLOWED_IMAGE_EXTENSIONS, MAX_IMAGE_SIZE
from server.database import get_db
from server.models import Question, QuestionAnswerStat
from server.schemas import QuestionCreate, QuestionUpdate, QuestionRead

router = APIRouter(prefix="/api/questions", tags=["questions"], dependencies=[Depends(require_auth)])


def _question_to_read(q: Question) -> QuestionRead:
    return QuestionRead(
        id=q.id, topic_id=q.topic_id, question_type=q.question_type,
        text=q.text, image_filename=q.image_filename,
        correct_answer=q.correct_answer, wrong_answer_1=q.wrong_answer_1,
        wrong_answer_2=q.wrong_answer_2, wrong_answer_3=q.wrong_answer_3,
        time_seconds=q.time_seconds, randomize_answers=q.randomize_answers,
        correct_index=q.correct_index,
        created_at=q.created_at,
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


NO_RESPONSE_KEY = "__no_response__"


@router.get("/stats/summary")
async def list_question_stats_summary(db: AsyncSession = Depends(get_db)):
    """Aggregate miss-rate summary for every question.

    For each question returns total responses (including non-responses) and
    the number of "misses" — players who picked any non-correct answer or
    failed to pick at all. Used by the instructor's question pool to sort
    questions by how often they trip students up.
    """
    rows = (await db.execute(select(QuestionAnswerStat))).scalars().all()
    by_qid: dict[int, dict[str, int]] = {}
    for r in rows:
        bucket = by_qid.setdefault(r.question_id, {})
        bucket[r.answer_text] = bucket.get(r.answer_text, 0) + int(r.times_chosen or 0)

    questions = (await db.execute(select(Question.id, Question.correct_answer))).all()
    summary = []
    for qid, correct in questions:
        bucket = by_qid.get(qid, {})
        non_responses = int(bucket.get(NO_RESPONSE_KEY, 0) or 0)
        responses = sum(v for k, v in bucket.items() if k != NO_RESPONSE_KEY)
        total = responses + non_responses
        correct_count = int(bucket.get(correct or "", 0) or 0)
        miss_count = total - correct_count
        miss_rate = (miss_count * 100.0 / total) if total else 0.0
        summary.append({
            "question_id": qid,
            "total": total,
            "correct_count": correct_count,
            "miss_count": miss_count,
            "miss_rate": miss_rate,
        })
    return summary


@router.get("/{question_id}", response_model=QuestionRead)
async def get_question(question_id: int, db: AsyncSession = Depends(get_db)):
    q = await db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "Question not found")
    return _question_to_read(q)


@router.get("/{question_id}/stats")
async def get_question_stats(question_id: int, db: AsyncSession = Depends(get_db)):
    """Cumulative answer-pick tally + percentages for a single question.

    The total includes players who saw the question but never picked any
    choice (recorded under the ``NO_RESPONSE_KEY`` sentinel). Per-choice
    percentages are computed against this grand total so non-responses are
    correctly reflected as a missing share."""
    q = await db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "Question not found")

    rows = (await db.execute(
        select(QuestionAnswerStat).where(QuestionAnswerStat.question_id == question_id)
    )).scalars().all()

    raw = {r.answer_text: r.times_chosen for r in rows}
    non_responses = int(raw.pop(NO_RESPONSE_KEY, 0) or 0)
    counts = raw
    total_responses = sum(counts.values())
    total = total_responses + non_responses
    percentages = {
        text: (count * 100.0 / total) if total else 0.0
        for text, count in counts.items()
    }
    non_response_pct = (non_responses * 100.0 / total) if total else 0.0
    return {
        "question_id": question_id,
        "total": total,
        "total_responses": total_responses,
        "non_responses": non_responses,
        "non_response_percentage": non_response_pct,
        "counts": counts,
        "percentages": percentages,
    }


@router.delete("/{question_id}/stats", status_code=204)
async def reset_question_stats(question_id: int, db: AsyncSession = Depends(get_db)):
    """Clear the cumulative tally for a single question."""
    q = await db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "Question not found")
    rows = (await db.execute(
        select(QuestionAnswerStat).where(QuestionAnswerStat.question_id == question_id)
    )).scalars().all()
    for r in rows:
        await db.delete(r)
    await db.commit()


@router.post("", response_model=QuestionRead, status_code=201)
async def create_question(body: QuestionCreate, db: AsyncSession = Depends(get_db)):
    randomize = body.randomize_answers
    if randomize is None:
        # Sensible per-type default: MC randomizes, true/false and tech A/B do not.
        randomize = body.question_type == "multiple_choice"
    q = Question(
        topic_id=body.topic_id,
        question_type=body.question_type,
        text=body.text,
        correct_answer=body.correct_answer,
        wrong_answer_1=body.wrong_answer_1,
        wrong_answer_2=body.wrong_answer_2,
        wrong_answer_3=body.wrong_answer_3,
        time_seconds=body.time_seconds,
        randomize_answers=randomize,
        correct_index=body.correct_index,
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
