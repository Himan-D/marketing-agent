import logging
from dataclasses import dataclass
from app.services.apollo import ApolloClient, ApolloPerson
from app.services.apify import ApifyScraper
from app.services.coresignal import CoreSignalClient

logger = logging.getLogger(__name__)


@dataclass
class ResearchedLead:
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
    source: str = "apollo"


class Researcher:
    def __init__(self):
        from app.config import settings as _s
        self.apollo = ApolloClient() if _s.apollo_api_key else None
        self.apify = ApifyScraper() if _s.apify_api_token else None
        self.coresignal = CoreSignalClient() if _s.coresignal_api_key else None

    async def search(self, *, titles: list[str] | None = None,
                     industries: list[str] | None = None,
                     locations: list[str] | None = None,
                     seniorities: list[str] | None = None,
                     company_domains: list[str] | None = None,
                     limit: int = 100) -> list[ResearchedLead]:
        found: dict[str, ResearchedLead] = {}

        if self.apollo:
            try:
                apollo_people = await self.apollo.search_people(
                    titles=titles, industries=industries, locations=locations,
                    seniorities=seniorities, company_domains=company_domains, limit=limit,
                )
                for p in apollo_people:
                    key = p.email or f"{p.first_name}{p.last_name}{p.company}"
                    if key and key not in found:
                        found[key] = self._from_apollo(p)
                logger.info("Apollo returned %d leads", len(apollo_people))
            except Exception as e:
                logger.error("Apollo search failed: %s", e)

        if self.apify:
            try:
                apify_leads = await self.apify.search_linkedin_profiles(
                    titles=titles, locations=locations, limit=limit,
                )
                for p in apify_leads:
                    key = f"{p['first_name']}{p['last_name']}{p['company']}"
                    if key not in found:
                        found[key] = self._from_apify(p)
                logger.info("Apify returned %d leads", len(apify_leads))
            except Exception as e:
                logger.error("Apify search failed: %s", e)

        if self.coresignal:
            try:
                prompt_parts = []
                if titles: prompt_parts.append(f"titles: {', '.join(titles)}")
                if industries: prompt_parts.append(f"industries: {', '.join(industries)}")
                if locations: prompt_parts.append(f"locations: {', '.join(locations)}")
                prompt = "Find employees matching " + "; ".join(prompt_parts)
                cs_leads = await self.coresignal.search_agentic(prompt=prompt, limit=limit)
                for p in cs_leads:
                    key = f"{p['first_name']}{p['last_name']}{p['company']}"
                    if key not in found:
                        found[key] = self._from_coresignal(p)
                logger.info("CoreSignal returned %d leads", len(cs_leads))
            except Exception as e:
                logger.error("CoreSignal search failed: %s", e)

        return list(found.values())[:limit]

    async def search_by_companies(self, company_urls: list[str],
                                  job_title: str | None = None,
                                  per_company: int = 25) -> list[ResearchedLead]:
        leads: list[ResearchedLead] = []
        if self.apify:
            try:
                results = await self.apify.get_company_employees(
                    company_linkedin_urls=company_urls, job_title=job_title, per_company=per_company,
                )
                for r in results:
                    leads.append(self._from_apify(r))
            except Exception as e:
                logger.error("Apify employee search failed: %s", e)
        return leads

    async def enrich(self, leads: list[ResearchedLead]) -> list[ResearchedLead]:
        enriched = []
        apify_urls = [l.linkedin_url for l in leads if l.linkedin_url]

        email_map: dict[str, str] = {}
        if self.apify and apify_urls:
            try:
                email_results = await self.apify.enrich_with_email(apify_urls)
                for r in email_results:
                    if r.get("email"):
                        email_map[r["linkedin_url"]] = r["email"]
            except Exception as e:
                logger.error("Apify enrichment failed: %s", e)

        if self.coresignal and apify_urls:
            try:
                for url in apify_urls:
                    if url in email_map:
                        continue
                    person = await self.coresignal.enrich_person(url)
                    if person and person.get("email"):
                        email_map[url] = person["email"]
            except Exception as e:
                logger.error("CoreSignal enrichment failed: %s", e)

        for lead in leads:
            if lead.linkedin_url in email_map and not lead.email:
                lead.email = email_map[lead.linkedin_url]
            lead.source = f"{lead.source}+enriched"
            enriched.append(lead)

        return enriched

    def _from_coresignal(self, p: dict) -> ResearchedLead:
        return ResearchedLead(
            first_name=p.get("first_name", ""), last_name=p.get("last_name", ""),
            title=p.get("title"), company=p.get("company"),
            industry=p.get("industry"), location=p.get("location"),
            linkedin_url=p.get("linkedin_url"),
            source=p.get("source", "coresignal"),
        )

    def _from_apollo(self, p: ApolloPerson) -> ResearchedLead:
        return ResearchedLead(
            first_name=p.first_name, last_name=p.last_name, email=p.email,
            title=p.title, company=p.company, company_domain=p.company_domain,
            industry=p.industry, location=p.location,
            linkedin_url=p.linkedin_url, phone=p.phone, about=p.about,
            source="apollo",
        )

    def _from_apify(self, p: dict) -> ResearchedLead:
        return ResearchedLead(
            first_name=p.get("first_name", ""), last_name=p.get("last_name", ""),
            email=p.get("email"), title=p.get("title"),
            company=p.get("company"), location=p.get("location"),
            linkedin_url=p.get("linkedin_url"), about=p.get("about"),
            source=p.get("source", "apify"),
        )

    async def close(self):
        if self.apollo:
            await self.apollo.close()
