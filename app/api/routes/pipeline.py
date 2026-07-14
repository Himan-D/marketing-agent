from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.models.db import Lead, Campaign
from app.models.schemas import PipelineResponse, PipelineStage, LeadResponse
from app.agents.funnel import FunnelManager, STAGES

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])


@router.get("", response_model=PipelineResponse)
async def get_pipeline(campaign_id: UUID | None = Query(None),
                       db: AsyncSession = Depends(get_db)):
    query = select(Lead.stage, func.count(Lead.id)).group_by(Lead.stage)
    if campaign_id:
        query = query.where(Lead.campaign_id == campaign_id)

    result = await db.execute(query)
    counts = dict(result.all())

    stages = []
    for stage in STAGES:
        stages.append(PipelineStage(stage=stage, count=counts.get(stage, 0)))

    return PipelineResponse(stages=stages)


@router.get("/{stage}", response_model=PipelineStage)
async def get_stage_leads(stage: str, campaign_id: UUID | None = Query(None),
                          limit: int = Query(50),
                          db: AsyncSession = Depends(get_db)):
    stage = stage.upper()
    if stage not in STAGES:
        from fastapi import HTTPException
        raise HTTPException(400, f"Invalid stage. Must be one of: {', '.join(STAGES)}")

    query = select(Lead).where(Lead.stage == stage)
    if campaign_id:
        query = query.where(Lead.campaign_id == campaign_id)
    query = query.limit(limit)

    result = await db.execute(query)
    leads = result.scalars().all()

    return PipelineStage(stage=stage, count=len(leads), leads=[LeadResponse.model_validate(l) for l in leads])


@router.get("/stats/conversion", response_model=dict)
async def get_conversion_stats(db: AsyncSession = Depends(get_db)):
    total_leads = 0
    total_contacted = 0
    total_opened = 0
    total_replied = 0

    result = await db.execute(select(func.count(Lead.id)))
    total_leads = result.scalar() or 0

    result = await db.execute(select(func.count(Lead.id)).where(Lead.engagement_opened == True))
    total_opened = result.scalar() or 0

    result = await db.execute(select(func.count(Lead.id)).where(Lead.engagement_replied == True))
    total_replied = result.scalar() or 0

    return {
        "total_leads": total_leads,
        "total_opened": total_opened,
        "total_replied": total_replied,
        "open_rate": round(total_opened / total_leads * 100, 1) if total_leads else 0,
        "reply_rate": round(total_replied / total_leads * 100, 1) if total_leads else 0,
    }
