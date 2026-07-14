from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.models.db import InteractionLog
from app.models.schemas import InteractionLogResponse

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


@router.get("", response_model=list[InteractionLogResponse])
async def get_interactions(lead_id: UUID | None = Query(None),
                            campaign_id: UUID | None = Query(None),
                            agent: str | None = Query(None),
                            action: str | None = Query(None),
                            limit: int = Query(50),
                            db: AsyncSession = Depends(get_db)):
    query = select(InteractionLog).order_by(desc(InteractionLog.created_at)).limit(limit)
    if lead_id:
        query = query.where(InteractionLog.lead_id == lead_id)
    if campaign_id:
        query = query.where(InteractionLog.campaign_id == campaign_id)
    if agent:
        query = query.where(InteractionLog.agent_name == agent)
    if action:
        query = query.where(InteractionLog.action == action)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/stats", response_model=dict)
async def get_memory_stats(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func
    result = await db.execute(
        select(
            InteractionLog.agent_name,
            InteractionLog.action,
            func.count(InteractionLog.id),
        ).group_by(InteractionLog.agent_name, InteractionLog.action)
    )
    rows = result.all()
    stats = {}
    for agent, action, count in rows:
        if agent not in stats:
            stats[agent] = {}
        stats[agent][action] = count
    return {"interactions": stats}
