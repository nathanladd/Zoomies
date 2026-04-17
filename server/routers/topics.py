from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from server.database import get_db
from server.models import Topic, Question
from server.schemas import TopicCreate, TopicUpdate, TopicRead

router = APIRouter(prefix="/api/topics", tags=["topics"])


@router.get("", response_model=list[TopicRead])
async def list_topics(db: AsyncSession = Depends(get_db)):
    stmt = select(Topic).order_by(Topic.name)
    result = await db.execute(stmt)
    topics = result.scalars().all()

    out: list[TopicRead] = []
    for t in topics:
        count_stmt = select(func.count()).where(Question.topic_id == t.id)
        count = (await db.execute(count_stmt)).scalar() or 0
        out.append(TopicRead(
            id=t.id, name=t.name, description=t.description,
            created_at=t.created_at, question_count=count,
        ))
    return out


@router.get("/{topic_id}", response_model=TopicRead)
async def get_topic(topic_id: int, db: AsyncSession = Depends(get_db)):
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(404, "Topic not found")
    count_stmt = select(func.count()).where(Question.topic_id == topic.id)
    count = (await db.execute(count_stmt)).scalar() or 0
    return TopicRead(
        id=topic.id, name=topic.name, description=topic.description,
        created_at=topic.created_at, question_count=count,
    )


@router.post("", response_model=TopicRead, status_code=201)
async def create_topic(body: TopicCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Topic).where(Topic.name == body.name))
    if existing.scalar():
        raise HTTPException(409, "Topic with this name already exists")
    topic = Topic(name=body.name, description=body.description)
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    return TopicRead(
        id=topic.id, name=topic.name, description=topic.description,
        created_at=topic.created_at, question_count=0,
    )


@router.put("/{topic_id}", response_model=TopicRead)
async def update_topic(topic_id: int, body: TopicUpdate, db: AsyncSession = Depends(get_db)):
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(404, "Topic not found")
    if body.name is not None:
        topic.name = body.name
    if body.description is not None:
        topic.description = body.description
    await db.commit()
    await db.refresh(topic)
    count_stmt = select(func.count()).where(Question.topic_id == topic.id)
    count = (await db.execute(count_stmt)).scalar() or 0
    return TopicRead(
        id=topic.id, name=topic.name, description=topic.description,
        created_at=topic.created_at, question_count=count,
    )


@router.delete("/{topic_id}", status_code=204)
async def delete_topic(topic_id: int, db: AsyncSession = Depends(get_db)):
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(404, "Topic not found")
    count_stmt = select(func.count()).where(Question.topic_id == topic_id)
    count = (await db.execute(count_stmt)).scalar() or 0
    if count > 0:
        raise HTTPException(
            409,
            f"Topic still has {count} question(s). Reassign or delete them first.",
        )
    await db.delete(topic)
    await db.commit()
