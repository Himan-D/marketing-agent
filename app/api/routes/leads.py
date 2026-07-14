from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.models.db import Lead, EmailLog
from app.models.schemas import (
    LeadResponse, StageUpdate,
    TwentyTriggerEmail, TwentyEmailResult,
    EmailComposePreview,
)
from app.agents.orchestrator import Orchestrator
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["leads"])


# ── List all leads (no campaign required) ─────────────

@router.get("/leads", response_model=list[LeadResponse])
async def list_all_leads(
    stage: str | None = Query(None),
    company: str | None = Query(None),
    has_email: bool | None = Query(None),
    limit: int = Query(100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Lead)
    if stage:
        query = query.where(Lead.stage == stage.upper())
    if company:
        query = query.where(Lead.company.ilike(f"%{company}%"))
    if has_email is True:
        query = query.where(Lead.email.isnot(None), Lead.email != "")
    elif has_email is False:
        query = query.where((Lead.email.is_(None)) | (Lead.email == ""))
    query = query.order_by(Lead.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


# ── Campaign-scoped leads ─────────────────────────────

@router.get("/campaigns/{campaign_id}/leads", response_model=list[LeadResponse])
async def list_leads(campaign_id: UUID, stage: str | None = Query(None),
                     db: AsyncSession = Depends(get_db)):
    query = select(Lead).where(Lead.campaign_id == campaign_id)
    if stage:
        query = query.where(Lead.stage == stage.upper())
    query = query.order_by(Lead.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


# ── Single lead ───────────────────────────────────────

@router.get("/leads/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(404, "Lead not found")
    return lead


# ── Stage management ──────────────────────────────────

@router.patch("/leads/{lead_id}/stage", response_model=LeadResponse)
async def update_lead_stage(lead_id: UUID, body: StageUpdate,
                            db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(404, "Lead not found")
    lead.stage = body.stage.upper()
    await db.commit()
    await db.refresh(lead)
    return lead


# ── Compose preview (no send) ─────────────────────────

@router.post("/leads/{lead_id}/compose-preview", response_model=EmailComposePreview)
async def compose_preview(lead_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(404, "Lead not found")

    orch = Orchestrator(db)
    try:
        subject, body = await orch.emailer.compose(
            db=db, lead_id=lead.id, campaign_id=lead.campaign_id,
            first_name=lead.first_name or "",
            last_name=lead.last_name or "",
            title=lead.title or "",
            company=lead.company or "",
            industry=lead.industry or "",
            about=lead.about or "",
            category=lead.category or "",
        )
        return EmailComposePreview(
            lead_id=lead_id, subject=subject, body=body,
            recipient=lead.email,
        )
    finally:
        await orch.close()


# ── Send email to a lead ──────────────────────────────

@router.post("/leads/{lead_id}/send-email", response_model=dict)
async def send_lead_email(lead_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(404, "Lead not found")
    if not lead.email:
        raise HTTPException(400, "Lead has no email address")

    orch = Orchestrator(db)
    try:
        log = EmailLog(
            lead_id=lead.id,
            campaign_id=lead.campaign_id,
            status="queued",
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)

        success = await orch.process_email(lead.id, log.id)
        if not success:
            raise HTTPException(500, "Failed to send email")
        return {"lead_id": str(lead_id), "status": "sent"}
    finally:
        await orch.close()


# ── Trigger email FROM Twenty CRM ─────────────────────

@router.post("/twenty/trigger-email", response_model=TwentyEmailResult)
async def trigger_email_from_twenty(
    body: TwentyTriggerEmail, db: AsyncSession = Depends(get_db),
):
    """Trigger email by Twenty CRM person ID.

    Flow:
      1. Find lead in DB by twenty_person_id
      2. Compose email via LLM
      3. If send_immediately → send via Brevo
      4. Update Twenty CRM: mailStatus, emailSubject, note
    """
    result = await db.execute(
        select(Lead).where(Lead.twenty_person_id == body.person_id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        return TwentyEmailResult(
            person_id=body.person_id, status="error",
            error="No lead found for this Twenty person ID",
        )
    if not lead.email:
        return TwentyEmailResult(
            person_id=body.person_id, status="error",
            error="Lead has no email address",
        )

    orch = Orchestrator(db)
    try:
        # Set status to QUEUED in Twenty
        logger.info("trigger-email: set QUEUED status in Twenty")
        await orch.twenty.set_email_status(body.person_id, "QUEUED")
        logger.info("trigger-email: QUEUED done, composing (category=%s)", lead.category)

        # Compose
        subject, email_body = await orch.emailer.compose(
            db=db, lead_id=lead.id, campaign_id=lead.campaign_id,
            first_name=lead.first_name or "",
            last_name=lead.last_name or "",
            title=lead.title or "",
            company=lead.company or "",
            industry=lead.industry or "",
            about=lead.about or "",
            category=lead.category or "",
        )

        logger.info("trigger-email: compose done, subject=%s", subject)
        if body.preview_only:
            logger.info("trigger-email: returning preview")
            return TwentyEmailResult(
                person_id=body.person_id, lead_id=str(lead.id),
                status="preview", subject=subject,
                body_preview=email_body[:500],
            )

        if not body.send_immediately:
            logger.info("trigger-email: composed but not sending")
            return TwentyEmailResult(
                person_id=body.person_id, lead_id=str(lead.id),
                status="composed", subject=subject,
                body_preview=email_body[:500],
            )

        # Send via Brevo
        msg_id = await orch.emailer.send(
            to_email=lead.email,
            to_name=f"{lead.first_name} {lead.last_name}".strip(),
            subject=subject, body=email_body,
            campaign_id=str(lead.campaign_id) if lead.campaign_id else "",
            lead_id=str(lead.id),
        )

        if msg_id:
            # Update DB
            log = EmailLog(
                lead_id=lead.id,
                campaign_id=lead.campaign_id,
                subject=subject, body=email_body,
                message_id=msg_id, mailchimp_id=msg_id,
                status="sent",
            )
            db.add(log)
            lead.stage = "CONTACTED"
            await db.commit()

            # Update Twenty CRM
            import datetime as dt
            await orch.twenty.set_email_status(
                body.person_id, "SENT", subject=subject,
                sent_at=dt.datetime.utcnow().isoformat(),
            )
            await orch.twenty.create_note(
                person_id=body.person_id,
                title=f"Email sent: {subject}",
                body=email_body,
            )

            return TwentyEmailResult(
                person_id=body.person_id, lead_id=str(lead.id),
                status="sent", subject=subject,
                body_preview=email_body[:200],
                message_id=msg_id,
            )
        else:
            await orch.twenty.set_email_status(body.person_id, "FAILED")
            return TwentyEmailResult(
                person_id=body.person_id, lead_id=str(lead.id),
                status="failed",
                error="Brevo send returned no message ID",
            )
    finally:
        await orch.close()


# ── Delete lead ───────────────────────────────────────

@router.delete("/leads/{lead_id}", status_code=204)
async def delete_lead(lead_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(404, "Lead not found")
    await db.delete(lead)
    await db.commit()
