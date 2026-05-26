"""
JSearch (RapidAPI) provider.
Key: JSEARCH_API_KEY (stored in api_settings table)
Subscribe (free tier) at: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
"""
import requests
from typing import List, Dict, Any

from .base_provider import JobProvider
from .settings_service import get_setting


class JSearchProvider(JobProvider):
    name = "JSearch"
    BASE_URL = "https://jsearch.p.rapidapi.com/search"

    def search(self, title: str, location: str, keywords: str = "",
               work_type: str = "All", commitment: str = "All",
               limit: int = 20) -> List[Dict[str, Any]]:
        api_key = get_setting("JSEARCH_API_KEY")
        if not api_key:
            print("[JSearchProvider] Skipped - no API key configured.")
            return []
        try:
            what = " ".join(filter(None, [title, keywords])) or "Software Engineer"
            query = f"{what} in {location}" if location else what
            if work_type == "Remote":
                query += " remote"

            headers = {
                "X-RapidAPI-Key": api_key,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
            }
            params = {
                "query": query,
                "num_pages": "1",
                "page": "1",
            }
            if work_type == "Remote":
                params["remote_jobs_only"] = "true"

            resp = requests.get(self.BASE_URL, headers=headers, params=params, timeout=12)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for jd in (data.get("data") or [])[:limit]:
                desc = self.clean_html(jd.get("job_description") or "")
                loc_parts = [p for p in [
                    jd.get("job_city"), jd.get("job_state"), jd.get("job_country")
                ] if p]
                loc = ", ".join(loc_parts) or location or "Remote"
                is_remote = jd.get("job_is_remote", False)
                wt = self.map_work_type(loc, is_remote)
                if work_type != "All" and wt.lower() != work_type.lower():
                    continue
                commitment_str = self.map_commitment(jd.get("job_employment_type") or "")
                if commitment != "All" and commitment_str.lower() != commitment.lower():
                    continue
                apply_url = jd.get("job_apply_link") or jd.get("job_google_link") or "#"
                job = {
                    "id": self.make_job_id(jd.get("job_id") or apply_url),
                    "title": jd.get("job_title") or "Untitled",
                    "company": jd.get("employer_name") or "Unknown",
                    "location": loc,
                    "work_type": wt,
                    "commitment": commitment_str,
                    "platform": "JSearch",
                    "description": desc or "No description available.",
                    "apply_url": apply_url,
                    "easy_apply": jd.get("job_apply_is_direct", False),
                    "posted_date": self.format_date(jd.get("job_posted_at_datetime_utc")),
                    "source_url": apply_url,
                }
                results.append(job)
            return results
        except Exception as e:
            print(f"[JSearchProvider] Error: {e}")
            return []
