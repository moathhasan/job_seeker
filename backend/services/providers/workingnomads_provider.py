"""
Working Nomads — public REST API.
No API key needed. Remote jobs aggregator.
"""
import requests
from typing import List, Dict, Any

from .base_provider import JobProvider


class WorkingNomadsProvider(JobProvider):
    name = "Working Nomads"
    BASE_URL = "https://www.workingnomads.com/api/exposed_jobs/"

    def search(self, title: str, location: str, keywords: str = "",
               work_type: str = "All", commitment: str = "All",
               limit: int = 20) -> List[Dict[str, Any]]:
        if work_type == "On-site":
            return []
        try:
            params = {}
            if title:
                params["tag"] = title.replace(" ", "-").lower()
            resp = requests.get(self.BASE_URL, params=params, timeout=10,
                                headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            jobs_raw = resp.json()
            if not isinstance(jobs_raw, list):
                jobs_raw = jobs_raw.get("results", []) if isinstance(jobs_raw, dict) else []
            search_terms = [t.lower() for t in filter(None, [title, keywords])]
            results = []
            for jd in jobs_raw:
                if len(results) >= limit:
                    break
                job_title = (jd.get("title") or "").lower()
                if search_terms and not any(t in job_title for t in search_terms):
                    continue
                desc = self.clean_html(jd.get("description") or "")
                apply_url = jd.get("url") or "#"
                company = jd.get("company_name") or jd.get("company") or "Unknown"
                commitment_str = self.map_commitment(jd.get("job_type") or "")
                if commitment != "All" and commitment_str.lower() != commitment.lower():
                    continue
                job = {
                    "id": self.make_job_id(apply_url),
                    "title": jd.get("title") or "Untitled",
                    "company": company,
                    "location": "Remote",
                    "work_type": "Remote",
                    "commitment": commitment_str,
                    "platform": "Working Nomads",
                    "description": desc or "View full job description on Working Nomads.",
                    "apply_url": apply_url,
                    "easy_apply": False,
                    "posted_date": self.format_date(jd.get("pub_date") or jd.get("created")),
                    "source_url": apply_url,
                }
                results.append(job)
            return results
        except Exception as e:
            print(f"[WorkingNomadsProvider] Error: {e}")
            return []
