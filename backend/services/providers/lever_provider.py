"""
Lever public job board API — no auth required.
Queries companies in parallel for speed.
Company list: LEVER_COMPANIES setting (comma-separated slugs)
"""
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

from .base_provider import JobProvider
from .settings_service import get_setting

DEFAULT_COMPANIES = (
    "netflix,reddit,box,figma,scale,openai,anthropic,cohere,"
    "databricks,dbt-labs,prefect,temporal,planetscale,neon,"
    "supabase,render,fly,railway,turso,tinybird,prisma"
)

_MAX_COMPANIES_PER_SEARCH = 8


class LeverProvider(JobProvider):
    name = "Lever"
    BASE_URL = "https://api.lever.co/v0/postings/{slug}?mode=json"

    def _fetch_company(self, slug, search_terms, location, work_type, commitment, limit):
        """Fetch jobs for a single Lever company."""
        jobs = []
        try:
            url = self.BASE_URL.format(slug=slug)
            resp = requests.get(url, timeout=6)
            if resp.status_code != 200:
                return jobs
            postings = resp.json()
            if not isinstance(postings, list):
                return jobs
            for jd in postings:
                if len(jobs) >= limit:
                    break
                job_title = (jd.get("text") or "").lower()
                if search_terms and not any(t in job_title for t in search_terms):
                    continue
                categories = jd.get("categories") or {}
                loc = categories.get("location") or location or "Remote"
                commitment_raw = categories.get("commitment") or ""
                commitment_str = self.map_commitment(commitment_raw)
                if commitment != "All" and commitment_str.lower() != commitment.lower():
                    continue
                wt = self.map_work_type(loc)
                if work_type != "All" and wt.lower() != work_type.lower():
                    continue
                desc = jd.get("descriptionPlain") or ""
                if not desc:
                    lists = jd.get("lists") or []
                    parts = []
                    for lst in lists:
                        parts.append(lst.get("text", ""))
                        for item in lst.get("content", "").split("<li>"):
                            clean = self.clean_html(item)
                            if clean:
                                parts.append(f"• {clean}")
                    desc = "\n".join(parts)
                apply_url = jd.get("hostedUrl") or jd.get("applyUrl") or "#"
                # Lever uses millisecond timestamps — convert to seconds
                created_at = jd.get("createdAt")
                if isinstance(created_at, (int, float)) and created_at > 1e12:
                    created_at = created_at / 1000
                jobs.append({
                    "id": self.make_job_id(jd.get("id") or apply_url),
                    "title": jd.get("text") or "Untitled",
                    "company": slug.replace("-", " ").title(),
                    "location": loc,
                    "work_type": wt,
                    "commitment": commitment_str,
                    "platform": "Lever",
                    "description": desc or "View full job description on Lever.",
                    "apply_url": apply_url,
                    "easy_apply": False,
                    "posted_date": self.format_date(created_at),
                    "source_url": apply_url,
                })
        except Exception as e:
            print(f"[LeverProvider] Error for {slug}: {e}")
        return jobs

    def search(self, title: str, location: str, keywords: str = "",
               work_type: str = "All", commitment: str = "All",
               limit: int = 20) -> List[Dict[str, Any]]:
        companies_str = get_setting("LEVER_COMPANIES", DEFAULT_COMPANIES)
        companies = [c.strip() for c in companies_str.split(",") if c.strip()]
        companies = companies[:_MAX_COMPANIES_PER_SEARCH]
        search_terms = [t.lower() for t in filter(None, [title, keywords])]
        results = []

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {
                pool.submit(self._fetch_company, slug, search_terms, location, work_type, commitment, limit): slug
                for slug in companies
            }
            for future in as_completed(futures):
                if len(results) >= limit:
                    break
                jobs = future.result()
                remaining = limit - len(results)
                results.extend(jobs[:remaining])

        return results
