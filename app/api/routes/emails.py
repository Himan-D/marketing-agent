from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.models.db import EmailLog, Lead
from app.models.schemas import EmailSend

router = APIRouter(prefix="/api/v1/emails", tags=["emails"])


@router.get("/logs", response_model=list[dict])
async def get_email_logs(campaign_id: UUID | None = None,
                         lead_id: UUID | None = None,
                         limit: int = 100,
                         db: AsyncSession = Depends(get_db)):
    query = select(EmailLog).order_by(EmailLog.created_at.desc()).limit(limit)
    if campaign_id:
        query = query.where(EmailLog.campaign_id == campaign_id)
    if lead_id:
        query = query.where(EmailLog.lead_id == lead_id)

    result = await db.execute(query)
    logs = result.scalars().all()
    return [
        {
            "id": str(l.id),
            "lead_id": str(l.lead_id),
            "campaign_id": str(l.campaign_id),
            "subject": l.subject,
            "status": l.status,
            "opened_at": l.opened_at.isoformat() if l.opened_at else None,
            "clicked_at": l.clicked_at.isoformat() if l.clicked_at else None,
            "sent_at": l.sent_at.isoformat() if l.sent_at else None,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ]


@router.get("/stats", response_model=dict)
async def get_email_stats(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(func.count(EmailLog.id)))
    total = result.scalar() or 0

    result = await db.execute(select(func.count(EmailLog.id)).where(EmailLog.status == "sent"))
    sent = result.scalar() or 0

    result = await db.execute(select(func.count(EmailLog.id)).where(EmailLog.opened_at.isnot(None)))
    opened = result.scalar() or 0

    result = await db.execute(select(func.count(EmailLog.id)).where(EmailLog.clicked_at.isnot(None)))
    clicked = result.scalar() or 0

    return {
        "total": total,
        "sent": sent,
        "opened": opened,
        "clicked": clicked,
        "open_rate": round(opened / sent * 100, 1) if sent else 0,
        "click_rate": round(clicked / sent * 100, 1) if sent else 0,
    }
