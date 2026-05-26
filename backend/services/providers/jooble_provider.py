"""
Jooble Jobs API provider.
Key: JOOBLE_API_KEY (stored in api_settings table)
Register free at: https://jooble.org/api/about
"""
import json
import requests
from typing import List, Dict, Any

from .base_provider import JobProvider
from .settings_service import get_setting


class JoobleProvider(JobProvider):
    name = "Jooble"

    def search(self, title: str, location: str, keywords: str = "",
               work_type: str = "All", commitment: str = "All",
               limit: int = 20) -> List[Dict[str, Any]]:
        api_key = get_setting("JOOBLE_API_KEY")
        if not api_key:
            print("[JoobleProvider] Skipped - no API key configured.")
            return []
        try:
            url = f"https://jooble.org/api/{api_key}"
            what = " ".join(filter(None, [title, keywords])) or "Software Engineer"
            payload = {
                "keywords": what,
                "location": location or "",
                "page": "1",
            }
            if work_type == "Remote":
                payload["keywords"] += " remote"

            resp = requests.post(
                url,
                data=json.dumps(payload),
                headers={"Content-type": "application/json"},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for jd in (data.get("jobs") or [])[:limit]:
                desc = self.clean_html(jd.get("snippet") or "")
                loc = jd.get("location") or location or "Remote"
                wt = self.map_work_type(loc, "remote" in (jd.get("type") or "").lower())
                if work_type != "All" and wt.lower() != work_type.lower():
                    continue
                commitment_str = self.map_commitment(jd.get("type") or "")
                if commitment != "All" and commitment_str.lower() != commitment.lower():
                    continue
                apply_url = jd.get("link") or "#"
                job = {
                    "id": self.make_job_id(apply_url),
                    "title": jd.get("title") or "Untitled",
                    "company": jd.get("company") or "Unknown",
                    "location": loc,
                    "work_type": wt,
                    "commitment": commitment_str,
                    "platform": "Jooble",
                    "description": desc or "No description available.",
                    "apply_url": apply_url,
                    "easy_apply": False,
                    "posted_date": self.format_date(jd.get("updated")),
                    "source_url": apply_url,
                }
                results.append(job)
            return results
        except Exception as e:
            print(f"[JoobleProvider] Error: {e}")
            return []
