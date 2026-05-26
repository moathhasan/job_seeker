"""
Apify cloud scraping provider.
Key: APIFY_TOKEN (stored in api_settings table)
Create account at: https://apify.com
"""
import requests
from typing import List, Dict, Any

from .base_provider import JobProvider
from .settings_service import get_setting


class ApifyProvider(JobProvider):
    name = "Apify"
    ACTOR_URL = "https://api.apify.com/v2/acts/curious_coder~indeed-scraper/run-sync-get-dataset-items"

    def search(self, title: str, location: str, keywords: str = "",
               work_type: str = "All", commitment: str = "All",
               limit: int = 20) -> List[Dict[str, Any]]:
        api_key = get_setting("APIFY_TOKEN")
        if not api_key:
            print("[ApifyProvider] Skipped - no APIFY_TOKEN configured.")
            return []
        try:
            search_term = " ".join(filter(None, [title, keywords])) or "Software Engineer"
            payload = {
                "position": search_term,
                "location": location or "Remote",
                "maxItems": min(limit, 25),
                "remote": work_type == "Remote",
            }
            resp = requests.post(
                self.ACTOR_URL,
                json=payload,
                params={"token": api_key},
                timeout=60,  # Apify actor runs can take time
            )
            resp.raise_for_status()
            jobs_raw = resp.json()
            if not isinstance(jobs_raw, list):
                return []
            results = []
            for jd in jobs_raw[:limit]:
                desc = self.clean_html(jd.get("description") or "")
                loc = jd.get("location") or location or "Remote"
                is_remote = jd.get("remote", False)
                wt = self.map_work_type(loc, is_remote)
                if work_type != "All" and wt.lower() != work_type.lower():
                    continue
                apply_url = jd.get("externalApplyLink") or jd.get("url") or "#"
                job = {
                    "id": self.make_job_id(apply_url),
                    "title": jd.get("positionName") or jd.get("title") or "Untitled",
                    "company": jd.get("company") or "Unknown",
                    "location": loc,
                    "work_type": wt,
                    "commitment": self.map_commitment(jd.get("jobType") or ""),
                    "platform": "Apify (Indeed)",
                    "description": desc or "View full job description.",
                    "apply_url": apply_url,
                    "easy_apply": False,
                    "posted_date": self.format_date(jd.get("postedAt")),
                    "source_url": apply_url,
                }
                results.append(job)
            return results
        except Exception as e:
            print(f"[ApifyProvider] Error: {e}")
            return []
