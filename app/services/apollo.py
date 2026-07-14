import httpx
from dataclasses import dataclass, field
from app.config import settings


@dataclass
class ApolloPerson:
    first_name: str
    last_name: str
    email: str | None = None
    title: str | None = None
    company: str | None = None
    company_domain: str | None = None
    industry: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    phone: str | None = None
    about: str | None = None
    photo_url: str | None = None


class ApolloClient:
    BASE = "https://api.apollo.io/api/v1"

    def __init__(self):
        self.headers = {
            "X-Api-Key": settings.apollo_api_key,
            "Content-Type": "application/json",
        }
        self.client = httpx.AsyncClient(base_url=self.BASE, headers=self.headers, timeout=30)

    async def search_people(self, *, titles: list[str] | None = None,
                            industries: list[str] | None = None,
                            locations: list[str] | None = None,
                            seniorities: list[str] | None = None,
                            company_domains: list[str] | None = None,
                            limit: int = 50) -> list[ApolloPerson]:
        params = {"per_page": min(limit, 100)}
        if titles:
            params["person_titles"] = titles
        if industries:
            params["organization_industry_tag_ids"] = industries
        if locations:
            params["person_locations"] = locations
        if seniorities:
            params["person_seniorities"] = seniorities
        if company_domains:
            params["q_organization_domains_list"] = company_domains

        try:
            r = await self.client.post("/mixed_people/api_search", json=params)
            r.raise_for_status()
            data = r.json()
        except Exception:
            return []

        people = []
        for p in data.get("people", []):
            org = p.get("organization", {}) or {}
            name = p.get("name", "") or ""
            parts = name.split(" ", 1)
            people.append(ApolloPerson(
                first_name=parts[0] if parts else "",
                last_name=parts[1] if len(parts) > 1 else "",
                email=p.get("email"),
                title=p.get("title"),
                company=org.get("name"),
                company_domain=org.get("domain"),
                industry=org.get("industry"),
                location=p.get("location"),
                linkedin_url=p.get("linkedin_url"),
                phone=p.get("phone"),
                about=p.get("about"),
                photo_url=p.get("photo_url"),
            ))
        return people

    async def enrich_person(self, email: str | None = None,
                            first_name: str | None = None,
                            last_name: str | None = None,
                            domain: str | None = None) -> ApolloPerson | None:
        params = {}
        if email:
            params["email"] = email
        if first_name:
            params["first_name"] = first_name
        if last_name:
            params["last_name"] = last_name
        if domain:
            params["domain"] = domain
        if not params:
            return None

        try:
            r = await self.client.post("/people/match", json=params)
            r.raise_for_status()
            p = r.json().get("person", {})
            if not p:
                return None
            org = p.get("organization", {}) or {}
            name = p.get("name", "") or ""
            parts = name.split(" ", 1)
            return ApolloPerson(
                first_name=parts[0] if parts else "",
                last_name=parts[1] if len(parts) > 1 else "",
                email=p.get("email"),
                title=p.get("title"),
                company=org.get("name"),
                company_domain=org.get("domain"),
                industry=org.get("industry"),
                location=p.get("location"),
                linkedin_url=p.get("linkedin_url"),
                phone=p.get("phone"),
                about=p.get("about"),
            )
        except Exception:
            return None

    async def close(self):
        await self.client.aclose()
