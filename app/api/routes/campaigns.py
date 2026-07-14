from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.models.db import Campaign
from app.models.schemas import CampaignCreate, CampaignResponse
from app.agents.orchestrator import Orchestrator

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(body: CampaignCreate, db: AsyncSession = Depends(get_db)):
    campaign = Campaign(
        name=body.name,
        criteria=body.criteria,
        target_leads=body.target_leads,
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.get("", response_model=list[CampaignResponse])
async def list_campaigns(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).order_by(Campaign.created_at.desc()))
    return result.scalars().all()


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    return campaign


@router.post("/{campaign_id}/start", response_model=dict)
async def start_campaign(campaign_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if campaign.status != "draft":
        raise HTTPException(400, f"Campaign already {campaign.status}")

    campaign.status = "running"
    from datetime import datetime
    campaign.started_at = datetime.utcnow()
    await db.commit()

    orchestrator = Orchestrator(db)
    try:
        found = await orchestrator.run_research(campaign_id)
        queued = await orchestrator.queue_emails(campaign_id)
    finally:
        await orchestrator.close()

    return {"campaign_id": str(campaign_id), "leads_found": found, "emails_queued": queued}


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(campaign_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    await db.delete(campaign)
    await db.commit()
