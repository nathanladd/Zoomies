from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.auth import require_auth
from server.database import get_db
from server.models import Note, Question
from server.schemas import NoteRead, NoteUpsert

router = APIRouter(
    prefix="/api/questions",
    tags=["notes"],
    dependencies=[Depends(require_auth)],
)


@router.get("/{question_id}/note", response_model=NoteRead)
async def get_note(question_id: int, db: AsyncSession = Depends(get_db)):
    q = await db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "Question not found")
    if not q.note:
        raise HTTPException(404, "No note for this question")
    return q.note


@router.put("/{question_id}/note", response_model=NoteRead)
async def upsert_note(question_id: int, body: NoteUpsert, db: AsyncSession = Depends(get_db)):
    """Create or replace the note for a question."""
    q = await db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "Question not found")

    now = datetime.now(timezone.utc)
    if q.note:
        q.note.discussion = body.discussion
        q.note.citations = body.citations
        q.note.updated_at = now
    else:
        note = Note(
            question_id=question_id,
            discussion=body.discussion,
            citations=body.citations,
        )
        db.add(note)

    await db.commit()
    await db.refresh(q)
    return q.note
