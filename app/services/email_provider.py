import httpx
import logging
from app.config import settings

logger = logging.getLogger(__name__)


class MailchimpTransactional:
    BASE = "https://mandrillapp.com/api/1.0"

    def __init__(self):
        self.api_key = settings.mailchimp_api_key
        self.client = httpx.AsyncClient(base_url=self.BASE, timeout=30)

    async def send(self, *, to_email: str, to_name: str, subject: str,
                   html_body: str, text_body: str | None = None,
                   tags: list[str] | None = None,
                   metadata: dict | None = None) -> str | None:
        if not self.api_key:
            logger.warning("Mailchimp API key not configured — skipping send")
            return None

        payload = {
            "key": self.api_key,
            "message": {
                "html": html_body,
                "text": text_body or "",
                "subject": subject,
                "from_email": settings.email_from.split("<")[-1].rstrip(">") if "<" in settings.email_from else settings.email_from,
                "from_name": settings.email_from_name,
                "to": [{"email": to_email, "name": to_name, "type": "to"}],
                "track_opens": True,
                "track_clicks": True,
                "tags": tags or [],
                "metadata": metadata or {},
            },
            "async": False,
        }

        if settings.email_reply_to:
            payload["message"]["headers"] = {"Reply-To": settings.email_reply_to}

        try:
            r = await self.client.post("/messages/send", json=payload)
            r.raise_for_status()
            result = r.json()
            if isinstance(result, list) and len(result) > 0:
                msg_id = result[0].get("_id")
                status = result[0].get("status")
                if status == "rejected":
                    logger.warning("Email rejected: %s", result[0].get("reject_reason"))
                    return None
                return msg_id
            return None
        except Exception as e:
            logger.error("Mailchimp send failed: %s", e)
            return None

    async def add_webhook(self, url: str, events: list[str] | None = None) -> bool:
        events = events or ["send", "open", "click", "hard_bounce", "soft_bounce", "spam"]
        try:
            r = await self.client.post("/webhooks/add", json={
                "key": self.api_key,
                "url": url,
                "description": "Marketing Agent Webhook",
                "events": events,
            })
            r.raise_for_status()
            return True
        except Exception as e:
            logger.error("Mailchimp webhook add failed: %s", e)
            return False

    async def close(self):
        await self.client.aclose()
