import logging
from datetime import datetime
from jinja2 import Template
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.llm import LLMService
from app.services.email_provider import MailchimpTransactional
from app.services.email_brevo import BrevoEmailService
from app.config import settings

logger = logging.getLogger(__name__)

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; padding: 20px; max-width: 600px;">
{{ body_html }}
</body>
</html>"""


class Emailer:
    def __init__(self):
        self.llm = LLMService()
        self.mailchimp = MailchimpTransactional() if settings.email_provider == "mailchimp" else None
        self.brevo = BrevoEmailService() if settings.email_provider == "brevo" else None
        self._hourly_sent: dict[str, int] = {}
        self._daily_sent: dict[str, int] = {}

    async def compose(self, *, db: AsyncSession | None = None,
                      lead_id=None, campaign_id=None,
                      first_name: str = "", last_name: str = "",
                      title: str = "", company: str = "",
                      industry: str = "", about: str = "",
                      company_description: str = "") -> tuple[str, str]:
        return await self.llm.compose_email(
            db=db, lead_id=lead_id, campaign_id=campaign_id,
            first_name=first_name, last_name=last_name,
            title=title, company=company, industry=industry,
            about=about, company_description=company_description,
        )

    async def send(self, *, to_email: str, to_name: str, subject: str,
                   body: str, campaign_id: str, lead_id: str) -> str | None:
        if not self._check_limits():
            logger.warning("Rate limit exceeded — skipping send")
            return None

        html_body = Template(HTML_TEMPLATE).render(body_html=body.replace("\n", "<br>"))

        msg_id = None
        if self.brevo:
            result = await self.brevo.send_email(
                to_email=to_email, to_name=to_name,
                subject=subject, html_body=html_body,
            )
            if result.get("success"):
                msg_id = result.get("message_id")
        elif self.mailchimp:
            msg_id = await self.mailchimp.send(
                to_email=to_email, to_name=to_name, subject=subject,
                html_body=html_body, text_body=body,
                tags=[f"campaign:{campaign_id}"],
                metadata={"lead_id": lead_id, "campaign_id": campaign_id},
            )

        if msg_id:
            self._track_send()
        return msg_id

    def _check_limits(self) -> bool:
        now = datetime.utcnow()
        hour_key = now.strftime("%Y-%m-%dT%H")
        day_key = now.strftime("%Y-%m-%d")

        if self._hourly_sent.get(hour_key, 0) >= settings.email_max_per_hour:
            return False
        if self._daily_sent.get(day_key, 0) >= settings.email_daily_cap:
            return False
        return True

    def _track_send(self):
        now = datetime.utcnow()
        hour_key = now.strftime("%Y-%m-%dT%H")
        day_key = now.strftime("%Y-%m-%d")
        self._hourly_sent[hour_key] = self._hourly_sent.get(hour_key, 0) + 1
        self._daily_sent[day_key] = self._daily_sent.get(day_key, 0) + 1
