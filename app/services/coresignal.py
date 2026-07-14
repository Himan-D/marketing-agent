import httpx
from app.config import settings

CORESIGNAL_BASE = "https://api.coresignal.com/cdapi/v2"


class CoreSignalClient:
    def __init__(self):
        self.api_key = settings.coresignal_api_key
        self.headers = {
            "accept": "application/json",
            "apikey": self.api_key,
            "Content-Type": "application/json",
        }

    async def search_people(self, *, titles: list[str] | None = None,
                             industries: list[str] | None = None,
                             locations: list[str] | None = None,
                             company_names: list[str] | None = None,
                             limit: int = 20) -> list[dict]:
        must_clauses = []

        if titles:
            must_clauses.append({
                "terms": {"active_experience_title": [t.lower() for t in titles]}
            })
        if industries:
            must_clauses.append({
                "terms": {"company_industry": [i.lower() for i in industries]}
            })
        if locations:
            must_clauses.append({
                "terms": {"company_hq_country": locations}
            })
        if company_names:
            must_clauses.append({
                "terms": {"company_name": company_names}
            })

        if not must_clauses:
            return []

        query = {"query": {"bool": {"must": must_clauses}}, "size": limit}

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{CORESIGNAL_BASE}/employee_base/search/es_dsl",
                headers=self.headers,
                json=query,
                timeout=30,
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            hits = data.get("hits", {}).get("hits", [])
            results = []
            for hit in hits:
                src = hit.get("_source", {})
                results.append({
                    "first_name": (src.get("full_name") or "").split(" ")[0],
                    "last_name": " ".join((src.get("full_name") or "").split(" ")[1:]),
                    "full_name": src.get("full_name"),
                    "title": src.get("active_experience_title"),
                    "company": src.get("company_name"),
                    "industry": src.get("company_industry"),
                    "location": src.get("company_hq_full_address") or src.get("company_hq_country"),
                    "linkedin_url": src.get("profile_url") or src.get("linkedin_url"),
                    "employee_id": src.get("id"),
                    "source": "coresignal",
                })
            return results

    async def search_agentic(self, prompt: str, limit: int = 20) -> list[dict]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{CORESIGNAL_BASE}/agentic_search/fast",
                headers=self.headers,
                json={"prompt": prompt, "return_data": True, "limit": limit, "entity": "employee"},
                timeout=30,
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = []
            for item in data if isinstance(data, list) else data.get("data", []):
                results.append({
                    "first_name": (item.get("full_name") or "").split(" ")[0],
                    "last_name": " ".join((item.get("full_name") or "").split(" ")[1:]),
                    "full_name": item.get("full_name"),
                    "title": item.get("active_experience_title") or item.get("title"),
                    "company": item.get("company_name"),
                    "industry": item.get("company_industry"),
                    "location": item.get("company_hq_full_address") or item.get("company_hq_country"),
                    "linkedin_url": item.get("profile_url") or item.get("linkedin_url"),
                    "employee_id": item.get("id"),
                    "source": "coresignal_agentic",
                })
            return results

    async def enrich_person(self, linkedin_url: str) -> dict | None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{CORESIGNAL_BASE}/employee_base/collect/{linkedin_url}",
                headers=self.headers,
                timeout=30,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            return {
                "first_name": (data.get("full_name") or "").split(" ")[0],
                "last_name": " ".join((data.get("full_name") or "").split(" ")[1:]),
                "full_name": data.get("full_name"),
                "title": data.get("active_experience_title") or data.get("title"),
                "company": data.get("company_name"),
                "industry": data.get("company_industry"),
                "location": data.get("company_hq_full_address") or data.get("company_hq_country"),
                "email": data.get("email"),
                "phone": data.get("phone"),
                "linkedin_url": data.get("profile_url"),
                "employee_id": data.get("id"),
                "source": "coresignal_enrich",
            }
