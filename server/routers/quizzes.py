from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from server.auth import require_auth
from server.database import get_db
from server.models import Quiz, QuizQuestion, Question
from server.schemas import (
    QuizCreate, QuizUpdate, QuizRead, QuizDetailRead,
    QuizQuestionAdd, QuizQuestionReorder, QuizQuestionRead, QuestionRead,
)

router = APIRouter(prefix="/api/quizzes", tags=["quizzes"], dependencies=[Depends(require_auth)])


def _qq_to_read(qq: QuizQuestion) -> QuizQuestionRead:
    q = qq.question
    qr = QuestionRead(
        id=q.id, topic_id=q.topic_id, question_type=q.question_type,
        text=q.text, image_filename=q.image_filename,
        correct_answer=q.correct_answer, wrong_answer_1=q.wrong_answer_1,
        wrong_answer_2=q.wrong_answer_2, wrong_answer_3=q.wrong_answer_3,
        time_seconds=q.time_seconds,
        randomize_answers=q.randomize_answers,
        correct_index=q.correct_index,
        created_at=q.created_at,
        topic_name=q.topic.name if q.topic else None,
    ) if q else None
    return QuizQuestionRead(id=qq.id, question_id=qq.question_id, position=qq.position, question=qr)


@router.get("", response_model=list[QuizRead])
async def list_quizzes(db: AsyncSession = Depends(get_db)):
    stmt = select(Quiz).order_by(Quiz.id.desc())
    result = await db.execute(stmt)
    quizzes = result.scalars().all()
    out: list[QuizRead] = []
    for qz in quizzes:
        cnt = (await db.execute(
            select(func.count()).where(QuizQuestion.quiz_id == qz.id)
        )).scalar() or 0
        out.append(QuizRead(
            id=qz.id, name=qz.name, description=qz.description,
            randomize_order=qz.randomize_order, created_at=qz.created_at,
            question_count=cnt,
        ))
    return out


@router.get("/{quiz_id}", response_model=QuizDetailRead)
async def get_quiz(quiz_id: int, db: AsyncSession = Depends(get_db)):
    qz = await db.get(Quiz, quiz_id)
    if not qz:
        raise HTTPException(404, "Quiz not found")
    qq_stmt = select(QuizQuestion).where(QuizQuestion.quiz_id == quiz_id).order_by(QuizQuestion.position)
    qq_result = await db.execute(qq_stmt)
    qqs = qq_result.scalars().all()
    return QuizDetailRead(
        id=qz.id, name=qz.name, description=qz.description,
        randomize_order=qz.randomize_order, created_at=qz.created_at,
        question_count=len(qqs),
        questions=[_qq_to_read(qq) for qq in qqs],
    )


@router.post("", response_model=QuizRead, status_code=201)
async def create_quiz(body: QuizCreate, db: AsyncSession = Depends(get_db)):
    qz = Quiz(name=body.name, description=body.description, randomize_order=body.randomize_order)
    db.add(qz)
    await db.commit()
    await db.refresh(qz)
    return QuizRead(
        id=qz.id, name=qz.name, description=qz.description,
        randomize_order=qz.randomize_order, created_at=qz.created_at,
        question_count=0,
    )


@router.put("/{quiz_id}", response_model=QuizRead)
async def update_quiz(quiz_id: int, body: QuizUpdate, db: AsyncSession = Depends(get_db)):
    qz = await db.get(Quiz, quiz_id)
    if not qz:
        raise HTTPException(404, "Quiz not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(qz, field, value)
    await db.commit()
    await db.refresh(qz)
    cnt = (await db.execute(
        select(func.count()).where(QuizQuestion.quiz_id == qz.id)
    )).scalar() or 0
    return QuizRead(
        id=qz.id, name=qz.name, description=qz.description,
        randomize_order=qz.randomize_order, created_at=qz.created_at,
        question_count=cnt,
    )


@router.delete("/{quiz_id}", status_code=204)
async def delete_quiz(quiz_id: int, db: AsyncSession = Depends(get_db)):
    qz = await db.get(Quiz, quiz_id)
    if not qz:
        raise HTTPException(404, "Quiz not found")
    await db.delete(qz)
    await db.commit()


@router.post("/{quiz_id}/questions", response_model=QuizQuestionRead, status_code=201)
async def add_question_to_quiz(
    quiz_id: int, body: QuizQuestionAdd, db: AsyncSession = Depends(get_db),
):
    qz = await db.get(Quiz, quiz_id)
    if not qz:
        raise HTTPException(404, "Quiz not found")
    q = await db.get(Question, body.question_id)
    if not q:
        raise HTTPException(404, "Question not found")

    if body.position is not None:
        position = body.position
    else:
        max_pos = (await db.execute(
            select(func.max(QuizQuestion.position)).where(QuizQuestion.quiz_id == quiz_id)
        )).scalar() or 0
        position = max_pos + 1

    qq = QuizQuestion(quiz_id=quiz_id, question_id=body.question_id, position=position)
    db.add(qq)
    await db.commit()
    await db.refresh(qq)
    return _qq_to_read(qq)


@router.put("/{quiz_id}/questions/reorder", response_model=list[QuizQuestionRead])
async def reorder_questions(
    quiz_id: int, body: QuizQuestionReorder, db: AsyncSession = Depends(get_db),
):
    qz = await db.get(Quiz, quiz_id)
    if not qz:
        raise HTTPException(404, "Quiz not found")

    qq_stmt = select(QuizQuestion).where(QuizQuestion.quiz_id == quiz_id)
    result = await db.execute(qq_stmt)
    existing = {qq.question_id: qq for qq in result.scalars().all()}

    for pos, qid in enumerate(body.question_ids, start=1):
        if qid in existing:
            existing[qid].position = pos

    await db.commit()

    qq_stmt = select(QuizQuestion).where(QuizQuestion.quiz_id == quiz_id).order_by(QuizQuestion.position)
    result = await db.execute(qq_stmt)
    return [_qq_to_read(qq) for qq in result.scalars().all()]


@router.delete("/{quiz_id}/questions/{question_id}", status_code=204)
async def remove_question_from_quiz(
    quiz_id: int, question_id: int, db: AsyncSession = Depends(get_db),
):
    stmt = select(QuizQuestion).where(
        QuizQuestion.quiz_id == quiz_id,
        QuizQuestion.question_id == question_id,
    )
    result = await db.execute(stmt)
    qq = result.scalar()
    if not qq:
        raise HTTPException(404, "Question not in this quiz")
    await db.delete(qq)
    await db.commit()
