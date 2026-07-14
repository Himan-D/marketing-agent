import httpx
import logging
from uuid import UUID
from dataclasses import dataclass
from app.config import settings

logger = logging.getLogger(__name__)

STAGES = [
    "LEAD", "CONTACTED", "OPENED", "REPLIED",
    "QUALIFIED", "PROPOSAL", "NEGOTIATION",
    "CLOSED_WON", "CLOSED_LOST",
]


@dataclass
class TwentyPerson:
    id: str
    name: dict | None = None
    emails: dict | None = None
    job_title: str | None = None


@dataclass
class TwentyCompany:
    id: str
    name: str | None = None


class TwentyCRM:
    def __init__(self):
        self.base = settings.twenty_base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {settings.twenty_api_key}",
            "Content-Type": "application/json",
        }
        self.client = httpx.AsyncClient(
            base_url=self.base, headers=self.headers, timeout=30,
        )

    async def _post(self, path: str, data: dict) -> dict:
        r = await self.client.post(path, json=data)
        r.raise_for_status()
        return r.json()

    async def _get(self, path: str) -> dict:
        r = await self.client.get(path)
        r.raise_for_status()
        return r.json()

    async def _patch(self, path: str, data: dict) -> dict:
        r = await self.client.patch(path, json=data)
        r.raise_for_status()
        return r.json()

    # ── People ──────────────────────────────────────────

    async def get_person(self, person_id: str) -> dict | None:
        try:
            resp = await self._get(f"/people/{person_id}")
            return resp.get("data", {}).get("person", resp.get("data", {}))
        except Exception:
            return None

    async def create_person(
        self, *, first_name: str, last_name: str, email: str,
        title: str = "", company_id: str | None = None,
        linkedin_url: str | None = None,
        about: str | None = None, phone: str | None = None,
    ) -> str | None:
        name = {}
        if first_name:
            name["firstName"] = first_name
        if last_name:
            name["lastName"] = last_name

        emails = {}
        if email:
            emails["primaryEmail"] = email

        payload = {
            "name": name or {"firstName": first_name or "Unknown"},
            "emails": emails,
            "jobTitle": title or "",
        }
        if company_id:
            payload["companyId"] = company_id
        if linkedin_url:
            payload["linkedinLink"] = {"primaryLinkUrl": linkedin_url}

        try:
            resp = await self._post("/people", payload)
            data = resp.get("data", {})
            if isinstance(data, dict):
                if "createPerson" in data:
                    return data["createPerson"].get("id")
                return data.get("id")
            return None
        except Exception as e:
            logger.debug("create_person failed: %s", e)
            return None

    async def update_person_fields(
        self, person_id: str, fields: dict,
    ) -> bool:
        """Update custom fields on a person."""
        try:
            await self._patch(f"/people/{person_id}", fields)
            return True
        except Exception as e:
            logger.warning("update_person_fields failed for %s: %s", person_id, e)
            return False

    async def set_email_status(
        self, person_id: str, status: str,
        subject: str | None = None,
        sent_at: str | None = None,
    ) -> bool:
        """Set mirrorfitStatus + mirrorfitSubject + mirrorfitSentAt fields."""
        updates = {"mirrorfitStatus": status}
        if subject:
            updates["mirrorfitSubject"] = subject
        if sent_at:
            updates["mirrorfitSentAt"] = sent_at
        return await self.update_person_fields(person_id, updates)

    # ── Companies ───────────────────────────────────────

    async def ensure_company(
        self, name: str, domain: str | None = None,
    ) -> str | None:
        if not name:
            return None
        try:
            resp = await self._post("/companies", {
                "name": name.strip(),
                "domain": domain or "",
            })
            data = resp.get("data", {})
            if isinstance(data, dict):
                if "createCompany" in data:
                    return data["createCompany"].get("id")
                return data.get("id")
            return None
        except Exception:
            return None

    # ── Opportunities ───────────────────────────────────

    async def create_opportunity(
        self, *, name: str, person_id: str,
        company_id: str | None = None, stage: str = "LEAD",
    ) -> str | None:
        try:
            resp = await self._post("/opportunities", {
                "name": name,
                "personId": person_id,
                "companyId": company_id or "",
                "stage": stage,
            })
            data = resp.get("data", {})
            if isinstance(data, dict):
                return data.get("id")
            return None
        except Exception:
            return None

    async def update_opportunity_stage(
        self, opportunity_id: str, stage: str,
    ) -> bool:
        try:
            await self._patch(f"/opportunities/{opportunity_id}", {"stage": stage})
            return True
        except Exception:
            return False

    # ── Notes ───────────────────────────────────────────

    async def create_note(
        self, *, person_id: str | None = None,
        opportunity_id: str | None = None,
        body: str, title: str | None = None,
    ) -> str | None:
        payload: dict = {"body": body}
        if title:
            payload["title"] = title
        if person_id:
            payload["personId"] = person_id
        if opportunity_id:
            payload["opportunityId"] = opportunity_id
        try:
            resp = await self._post("/notes", payload)
            data = resp.get("data", {})
            if isinstance(data, dict):
                return data.get("id")
            return None
        except Exception as e:
            logger.debug("create_note failed: %s", e)
            return None

    # ── Timeline Events (better than notes for tracking) ──

    async def create_timeline_event(
        self, *, person_id: str, name: str,
        properties: dict | None = None,
    ) -> str | None:
        """Create a timeline event on a person (shows in activity feed)."""
        payload = {
            "personId": person_id,
            "name": name,
        }
        if properties:
            payload["properties"] = properties
        try:
            resp = await self._post("/timeline-events", payload)
            data = resp.get("data", {})
            if isinstance(data, dict):
                return data.get("id")
            return None
        except Exception as e:
            logger.debug("timeline event failed: %s", e)
            return None

    async def update_person_category(self, person_id: str, category: str) -> bool:
        try:
            await self._patch(f"/people/{person_id}", {"leadCategory": category})
            return True
        except Exception as e:
            logger.debug("update_person_category failed for %s: %s", person_id, e)
            return False

    async def delete_person(self, person_id: str) -> bool:
        try:
            r = await self.client.delete(f"/people/{person_id}")
            r.raise_for_status()
            return True
        except Exception as e:
            logger.debug("delete_person failed for %s: %s", person_id, e)
            return False

    async def close(self):
        await self.client.aclose()
