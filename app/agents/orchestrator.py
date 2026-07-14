import logging
import time
from uuid import UUID
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db import Campaign, Lead, EmailLog, InteractionLog
from app.agents.researcher import Researcher
from app.agents.scraper import Scraper
from app.agents.emailer import Emailer
from app.agents.funnel import FunnelManager
from app.services.twenty_crm import TwentyCRM
from app.services.llm import LLMService
from app.core.email_strategy import classify_lead

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.researcher = Researcher()
        self.scraper = Scraper()
        self.emailer = Emailer()
        self.funnel = FunnelManager()
        self.twenty = TwentyCRM()
        self.llm = LLMService()

    async def run_research(self, campaign_id: UUID) -> int:
        result = await self.db.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        if not campaign:
            return 0

        start = time.time()
        criteria = campaign.criteria
        leads = await self.researcher.search(
            titles=criteria.get("titles"),
            industries=criteria.get("industries"),
            locations=criteria.get("locations"),
            seniorities=criteria.get("seniorities"),
            company_domains=criteria.get("company_domains"),
            limit=criteria.get("max_leads", 100),
        )

        await self._log(campaign_id=campaign_id, agent="researcher", action="search",
                        input_data={"criteria": criteria, "count": len(leads)},
                        duration_ms=int((time.time() - start) * 1000))

        for lead in leads:
            company_id = await self.twenty.ensure_company(
                lead.company, lead.company_domain,
            )
            person_id = await self.twenty.create_person(
                first_name=lead.first_name, last_name=lead.last_name,
                email=lead.email or "", title=lead.title or "",
                company_id=company_id,
                linkedin_url=lead.linkedin_url,
                about=lead.about, phone=lead.phone,
            )
            opp_id = None
            if person_id:
                opp_name = f"{lead.first_name} {lead.last_name} - {lead.company or 'Unknown'}"
                opp_id = await self.twenty.create_opportunity(
                    name=opp_name, person_id=person_id,
                    company_id=company_id, stage="LEAD",
                )

            category = classify_lead(
                company=lead.company or "",
                industry=lead.industry or "",
                title=lead.title or "",
                company_domain=lead.company_domain or "",
                about=lead.about or "",
            )

            if person_id:
                await self.twenty.update_person_category(person_id, category)

            db_lead = Lead(
                campaign_id=campaign_id,
                category=category,
                first_name=lead.first_name, last_name=lead.last_name,
                email=lead.email, title=lead.title,
                company=lead.company, company_domain=lead.company_domain,
                industry=lead.industry, location=lead.location,
                linkedin_url=lead.linkedin_url, phone=lead.phone,
                about=lead.about, source=lead.source,
                stage="LEAD",
                twenty_person_id=person_id,
                twenty_company_id=company_id,
                twenty_opportunity_id=opp_id,
            )
            self.db.add(db_lead)

        campaign.leads_found = len(leads)
        await self.db.commit()
        return len(leads)

    async def queue_emails(self, campaign_id: UUID) -> int:
        result = await self.db.execute(
            select(Lead).where(
                Lead.campaign_id == campaign_id,
                Lead.email.isnot(None),
                Lead.email != "",
            )
        )
        leads = result.scalars().all()
        queued = 0

        for lead in leads:
            log = EmailLog(
                lead_id=lead.id,
                campaign_id=campaign_id,
                status="queued",
            )
            self.db.add(log)
            queued += 1

        result = await self.db.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        if campaign:
            campaign.emails_sent = queued
        await self.db.commit()
        return queued

    async def process_email(self, lead_id: UUID, log_id: UUID) -> bool:
        result = await self.db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()
        if not lead:
            return False

        r2 = await self.db.execute(select(EmailLog).where(EmailLog.id == log_id))
        log = r2.scalar_one_or_none()
        if not log:
            return False

        subject, body = await self.emailer.compose(
            db=self.db, lead_id=lead.id, campaign_id=lead.campaign_id,
            first_name=lead.first_name or "",
            last_name=lead.last_name or "",
            title=lead.title or "",
            company=lead.company or "",
            industry=lead.industry or "",
            about=lead.about or "",
            category=lead.category or "",
        )

        start = time.time()
        msg_id = await self.emailer.send(
            to_email=lead.email,
            to_name=f"{lead.first_name} {lead.last_name}".strip(),
            subject=subject, body=body,
            campaign_id=str(lead.campaign_id),
            lead_id=str(lead.id),
        )

        if msg_id:
            log.status = "sent"
            log.subject = subject
            log.body = body
            log.message_id = msg_id
            log.mailchimp_id = msg_id
            log.sent_at = datetime.utcnow()
            lead.stage = "CONTACTED"
            if lead.twenty_opportunity_id:
                await self.twenty.update_opportunity_stage(
                    lead.twenty_opportunity_id, "CONTACTED",
                )
            await self._log(lead_id=lead.id, campaign_id=lead.campaign_id,
                            agent="emailer", action="send",
                            input_data={"subject": subject, "email": lead.email},
                            output_data={"message_id": msg_id, "status": "sent"},
                            duration_ms=int((time.time() - start) * 1000))
        else:
            log.status = "failed"
            await self._log(lead_id=lead.id, campaign_id=lead.campaign_id,
                            agent="emailer", action="send",
                            input_data={"subject": subject, "email": lead.email},
                            output_data={"status": "failed"},
                            status="failed")

        await self.db.commit()
        return bool(msg_id)

    async def handle_tracking_event(self, event: str, message_id: str,
                                    lead_id: str | None = None,
                                    url: str | None = None) -> None:
        if lead_id:
            result = await self.db.execute(select(Lead).where(Lead.id == lead_id))
        else:
            result = await self.db.execute(
                select(Lead).join(EmailLog).where(EmailLog.message_id == message_id)
            )
        lead = result.scalar_one_or_none()
        if not lead:
            return

        now = datetime.utcnow()
        stage_before = lead.stage

        if event == "open":
            lead.engagement_opened = True
            lead.opened_at = lead.opened_at or now
            lead.stage = "OPENED"
            if lead.twenty_opportunity_id:
                await self.twenty.add_note(lead.twenty_opportunity_id, "Email opened")
                await self.twenty.update_opportunity_stage(lead.twenty_opportunity_id, "OPENED")

        elif event == "click":
            lead.engagement_clicked = True
            lead.clicked_at = lead.clicked_at or now
            lead.stage = "REPLIED"
            if lead.twenty_opportunity_id:
                note = f"Clicked: {url or 'unknown link'}"
                await self.twenty.add_note(lead.twenty_opportunity_id, note)
                await self.twenty.update_opportunity_stage(lead.twenty_opportunity_id, "REPLIED")

        elif event == "hard_bounce":
            lead.stage = "CLOSED_LOST"

        await self._log(lead_id=lead.id, campaign_id=lead.campaign_id,
                        agent="funnel", action="stage_change",
                        input_data={"from": stage_before, "to": lead.stage, "event": event})

        await self.db.commit()

    async def _log(self, *, lead_id=None, campaign_id=None,
                   agent: str, action: str,
                   input_data: dict | None = None,
                   output_data: dict | None = None,
                   status: str = "success",
                   duration_ms: int | None = None):
        log = InteractionLog(
            lead_id=lead_id, campaign_id=campaign_id,
            agent_name=agent, action=action,
            input_data=input_data, output_data=output_data,
            status=status, duration_ms=duration_ms,
        )
        self.db.add(log)
        try:
            await self.db.flush()
        except Exception as e:
            logger.warning("Failed to save interaction log: %s", e)

    async def close(self):
        await self.researcher.close()
        await self.twenty.close()
