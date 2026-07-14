import logging
from apify_client import ApifyClient
from app.config import settings

logger = logging.getLogger(__name__)

ACTOR_PROFILE_SEARCH = "harvestapi~linkedin-profile-search"


class ApifyScraper:
    def __init__(self):
        self.token = settings.apify_api_token
        self.client = ApifyClient(self.token)

    @staticmethod
    def _parse_positions(item: dict) -> tuple[str | None, str | None]:
        positions = item.get("currentPositions") or item.get("positions") or []
        if positions:
            pos = positions[0]
            return pos.get("title"), pos.get("companyName")
        return item.get("headline"), None

    @staticmethod
    def _parse_location(item: dict) -> str:
        loc = item.get("location") or {}
        if isinstance(loc, dict):
            return loc.get("linkedinText") or loc.get("text") or ""
        return str(loc)

    async def search_linkedin_profiles(self, *, titles: list[str] | None = None,
                                       locations: list[str] | None = None,
                                       limit: int = 50) -> list[dict]:
        title_str = ", ".join(titles) if titles else ""
        query_parts = [title_str] if title_str else []
        query = " ".join(query_parts) or "executive"

        run_input = {
            "searchQuery": query,
            "maxItems": limit,
            "takePages": min(limit // 25 + 1, 4),
        }
        if titles:
            run_input["currentJobTitles"] = titles
        if locations:
            run_input["locations"] = locations

        logger.info("Apify search: %s", run_input)
        run = self.client.actor(ACTOR_PROFILE_SEARCH).call(run_input=run_input)
        results = []
        for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
            title, company = self._parse_positions(item)
            results.append({
                "first_name": item.get("firstName") or "",
                "last_name": item.get("lastName") or "",
                "title": title or item.get("headline", ""),
                "company": company or "",
                "headline": item.get("headline", ""),
                "location": self._parse_location(item),
                "linkedin_url": item.get("linkedinUrl", ""),
                "about": item.get("summary", "") or item.get("about", ""),
                "photo": item.get("pictureUrl") or item.get("photo", ""),
                "source": "apify_linkedin",
            })
        logger.info("Apify returned %d profiles", len(results))
        return results

    async def get_company_employees(self, *, company_linkedin_urls: list[str],
                                    job_title: str | None = None,
                                    per_company: int = 25) -> list[dict]:
        results_list = []
        for company_url in company_linkedin_urls:
            run_input = {
                "searchQuery": job_title or "",
                "currentCompanyUrls": [company_url],
                "maxItems": per_company,
                "takePages": max(per_company // 25, 1),
            }
            if job_title:
                run_input["currentJobTitles"] = [job_title]

            try:
                run = self.client.actor(ACTOR_PROFILE_SEARCH).call(run_input=run_input)
                for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                    title, company = self._parse_positions(item)
                    results_list.append({
                        "first_name": item.get("firstName") or "",
                        "last_name": item.get("lastName") or "",
                        "title": title or item.get("headline", ""),
                        "company": company or "",
                        "location": self._parse_location(item),
                        "linkedin_url": item.get("linkedinUrl", ""),
                        "about": item.get("summary", "") or item.get("about", ""),
                        "source": "apify_employees",
                    })
            except Exception as e:
                logger.error("Apify employee search failed for %s: %s", company_url, e)
        return results_list

    async def enrich_with_email(self, linkedin_urls: list[str]) -> list[dict]:
        # harvestapi actor doesn't natively return emails
        # Requires a separate email enrichment actor
        # For now, returns empty results
        logger.info("Email enrichment via Apify requires separate actor")
        return []
