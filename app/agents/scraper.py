import logging
from app.services.apify import ApifyScraper
from app.config import settings

logger = logging.getLogger(__name__)


class Scraper:
    def __init__(self):
        self.apify = ApifyScraper() if settings.apify_api_token else None

    async def scrape_company_website(self, domain: str) -> dict:
        if not self.apify:
            return {}
        try:
            run = self.apify.client.actor("usdof/website-content-crawler").call(run_input={
                "startUrls": [{"url": f"https://{domain}"}],
                "maxCrawlPages": 5,
            })
            pages = []
            for item in self.apify.client.dataset(run["defaultDatasetId"]).iterate_items():
                pages.append({
                    "url": item.get("url"),
                    "text": item.get("text", "")[:2000],
                })
            return {"domain": domain, "pages": pages}
        except Exception as e:
            logger.warning("Website scrape failed for %s: %s", domain, e)
            return {"domain": domain, "pages": []}

    async def find_decision_makers(self, company_domain: str,
                                   department: str | None = None) -> list[dict]:
        if not self.apify:
            return []
        try:
            run = self.apify.client.actor("afanasenko/linkedin-profile-api-scraper").call(run_input={
                "operationMode": "searchLead",
                "searchLeadCompanyUrls": [f"https://{company_domain}"],
                "searchLeadJobTitle": department or "",
                "searchLeadCount": 20,
            })
            results = []
            for item in self.apify.client.dataset(run["defaultDatasetId"]).iterate_items():
                results.append({
                    "first_name": item.get("first_name", ""),
                    "last_name": item.get("last_name", ""),
                    "title": item.get("title", ""),
                    "linkedin_url": item.get("linkedin_url", ""),
                })
            return results
        except Exception as e:
            logger.warning("Decision maker search failed for %s: %s", company_domain, e)
            return []
