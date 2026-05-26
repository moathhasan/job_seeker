"""
Greenhouse Job Board API provider — public, no auth required.
Queries a configurable list of known companies in parallel.
Company list: GREENHOUSE_COMPANIES setting (comma-separated board tokens)
"""
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

from .base_provider import JobProvider
from .settings_service import get_setting

DEFAULT_COMPANIES = (
    "stripe,airbnb,notion,figma,linear,vercel,cloudflare,discord,"
    "shopify,dropbox,datadog,hashicorp,mongodb,elastic,confluent,"
    "okta,twilio,sendgrid,segment,brex,rippling,lattice,deel,"
    "gusto,carta,plaid,checkr,greenhouse,lever"
)

_MAX_COMPANIES_PER_SEARCH = 8  # Cap to avoid timeout; admin can reorder the list


class GreenhouseProvider(JobProvider):
    name = "Greenhouse"
    BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"

    def _fetch_company(self, token, search_terms, location, work_type, limit):
        """Fetch jobs for a single company. Returns a list of job dicts."""
        jobs = []
        try:
            url = self.BASE_URL.format(token=token) + "?content=true"
            resp = requests.get(url, timeout=6)
            if resp.status_code != 200:
                return jobs
            data = resp.json()
            for jd in data.get("jobs", []):
                if len(jobs) >= limit:
                    break
                job_title = (jd.get("title") or "").lower()
                if search_terms and not any(t in job_title for t in search_terms):
                    continue
                loc = jd.get("location", {}).get("name") or location or "Remote"
                if location and location.lower() != "remote":
                    if location.lower() not in loc.lower() and "remote" not in loc.lower():
                        continue
                wt = self.map_work_type(loc)
                if work_type != "All" and wt.lower() != work_type.lower():
                    continue
                desc = self.clean_html(jd.get("content") or "")
                apply_url = jd.get("absolute_url") or "#"
                jobs.append({
                    "id": self.make_job_id(str(jd.get("id") or apply_url)),
                    "title": jd.get("title") or "Untitled",
                    "company": token.capitalize(),
                    "location": loc,
                    "work_type": wt,
                    "commitment": "Full-time",
                    "platform": "Greenhouse",
                    "description": desc or "View full job description on Greenhouse.",
                    "apply_url": apply_url,
                    "easy_apply": False,
                    "posted_date": self.format_date(jd.get("updated_at")),
                    "source_url": apply_url,
                })
        except Exception as e:
            print(f"[GreenhouseProvider] Error for {token}: {e}")
        return jobs

    def search(self, title: str, location: str, keywords: str = "",
               work_type: str = "All", commitment: str = "All",
               limit: int = 20) -> List[Dict[str, Any]]:
        companies_str = get_setting("GREENHOUSE_COMPANIES", DEFAULT_COMPANIES)
        companies = [c.strip() for c in companies_str.split(",") if c.strip()]
        companies = companies[:_MAX_COMPANIES_PER_SEARCH]
        search_terms = [t.lower() for t in filter(None, [title, keywords])]
        results = []

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {
                pool.submit(self._fetch_company, token, search_terms, location, work_type, limit): token
                for token in companies
            }
            for future in as_completed(futures):
                if len(results) >= limit:
                    break
                jobs = future.result()
                remaining = limit - len(results)
                results.extend(jobs[:remaining])

        return results
