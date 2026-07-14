from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.models.db import EmailLog, Lead, InteractionLog
from app.models.schemas import BrevoWebhookEvent
from app.agents.orchestrator import Orchestrator
from app.services.twenty_crm import TwentyCRM
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/brevo")
async def brevo_webhook(
    event: BrevoWebhookEvent | list[BrevoWebhookEvent],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Handle Brevo tracking webhooks.

    Brevo sends events for: delivered, opened, clicked, bounced, etc.
    We update the lead stage, EmailLog, and Twenty CRM custom fields.
    """
    events = event if isinstance(event, list) else [event]
    results = []

    for evt in events:
        result = await _process_brevo_event(evt, db)
        results.append(result)

    return {"processed": len(results), "results": results}


async def _process_brevo_event(evt: BrevoWebhookEvent, db: AsyncSession) -> dict:
    event_type = evt.event.lower()
    email = evt.email
    msg_id = str(evt.message_id) if evt.message_id else None

    # Find lead by email
    result = await db.execute(select(Lead).where(Lead.email == email))
    lead = result.scalar_one_or_none()
    if not lead:
        return {"email": email, "event": event_type, "status": "no_lead_found"}

    now = datetime.utcnow()
    stage_before = lead.stage
    new_stage = None
    twenty_status = None

    if event_type in ("delivered", "request"):
        new_stage = "CONTACTED"
    elif event_type == "opened":
        lead.engagement_opened = True
        lead.opened_at = lead.opened_at or now
        new_stage = "OPENED"
        twenty_status = "OPENED"
    elif event_type == "click":
        lead.engagement_clicked = True
        lead.clicked_at = lead.clicked_at or now
        new_stage = "OPENED"
        twenty_status = "CLICKED"
    elif event_type in ("reply", "replied"):
        lead.engagement_replied = True
        lead.replied_at = lead.replied_at or now
        new_stage = "REPLIED"
        twenty_status = "REPLIED"
    elif event_type in ("hard_bounce", "bounce", "error"):
        new_stage = "CLOSED_LOST"
        twenty_status = "BOUNCED"

    if new_stage:
        lead.stage = new_stage

    # Update EmailLog if we can find it
    if msg_id:
        log_result = await db.execute(
            select(EmailLog).where(EmailLog.message_id == msg_id)
        )
        log = log_result.scalar_one_or_none()
        if log:
            if event_type == "opened":
                log.opened_at = log.opened_at or now
                log.status = "opened"
            elif event_type == "click":
                log.clicked_at = log.clicked_at or now
                log.status = "clicked"
            elif event_type in ("hard_bounce", "bounce"):
                log.status = "bounced"
                log.bounce_type = "hard"

    # Log interaction
    interaction = InteractionLog(
        lead_id=lead.id,
        campaign_id=lead.campaign_id,
        agent_name="webhook",
        action="tracking_event",
        input_data={"event": event_type, "email": email, "message_id": msg_id},
        output_data={"stage_before": stage_before, "stage_after": new_stage},
        status="success",
    )
    db.add(interaction)
    await db.commit()

    # Update Twenty CRM custom fields
    if lead.twenty_person_id and twenty_status:
        twenty = TwentyCRM()
        try:
            await twenty.set_email_status(
                lead.twenty_person_id, twenty_status,
                sent_at=now.isoformat() if event_type == "delivered" else None,
            )

            if twenty_status in ("OPENED", "CLICKED", "REPLIED"):
                await twenty.create_note(
                    person_id=lead.twenty_person_id,
                    title=f"Email {event_type}",
                    body=f"Recipient {email} {event_type} the email at {now.isoformat()}",
                )
                # Increment open count
                await twenty.update_person_fields(
                    lead.twenty_person_id,
                    {"mirrorfitOpens": (lead.engagement_opened or 0) + 1},
                )
        finally:
            await twenty.close()

    return {
        "email": email,
        "event": event_type,
        "lead_id": str(lead.id),
        "stage_before": stage_before,
        "stage_after": new_stage,
        "twenty_updated": bool(lead.twenty_person_id and twenty_status),
    }


@router.post("/mailchimp")
async def mailchimp_webhook(request: Request):
    """Legacy Mailchimp webhook handler (not used with Brevo)."""
    return {"status": "mailchimp webhook received"}
