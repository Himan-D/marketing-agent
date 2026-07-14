import logging
from brevo import AsyncBrevo
from brevo.transactional_emails import (
    SendTransacEmailRequestSender,
    SendTransacEmailRequestToItem,
)
from app.config import settings

logger = logging.getLogger(__name__)


class BrevoEmailService:
    def __init__(self):
        self.client = AsyncBrevo(api_key=settings.brevo_api_key)
        self.from_email, self.from_name = self._parse_from(settings.email_from)

    @staticmethod
    def _parse_from(from_str: str) -> tuple[str, str]:
        if "<" in from_str and ">" in from_str:
            name = from_str.split("<")[0].strip()
            email = from_str.split("<")[1].split(">")[0].strip()
            return email, name
        return from_str, settings.email_from_name

    async def send_email(self, *, to_email: str, to_name: str,
                          subject: str, html_body: str,
                          track_opens: bool = True,
                          track_clicks: bool = True) -> dict:
        try:
            resp = await self.client.transactional_emails.send_transac_email(
                sender=SendTransacEmailRequestSender(
                    email=self.from_email,
                    name=self.from_name,
                ),
                to=[
                    SendTransacEmailRequestToItem(
                        email=to_email,
                        name=to_name,
                    )
                ],
                subject=subject,
                html_content=html_body,
                params={
                    "trackOpens": str(track_opens).lower(),
                    "trackClicks": str(track_clicks).lower(),
                },
            )
            message_id = getattr(resp, "message_id", "") or ""
            logger.info("Brevo email sent to %s: messageId=%s", to_email, message_id)
            return {
                "success": True,
                "provider": "brevo",
                "message_id": message_id,
                "to": to_email,
            }
        except Exception as e:
            logger.error("Brevo send failed to %s: %s", to_email, e)
            return {"success": False, "provider": "brevo", "error": str(e), "to": to_email}

    async def send_batch(self, messages: list[dict]) -> list[dict]:
        results = []
        for msg in messages:
            result = await self.send_email(
                to_email=msg["to_email"],
                to_name=msg.get("to_name", ""),
                subject=msg["subject"],
                html_body=msg["html_body"],
                track_opens=msg.get("track_opens", True),
                track_clicks=msg.get("track_clicks", True),
            )
            results.append(result)
        return results
