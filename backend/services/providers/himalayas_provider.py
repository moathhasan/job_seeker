"""
Himalayas.app free API provider.
No API key needed. Returns real remote jobs.
"""
import json
import urllib.request
import urllib.parse
from typing import List, Dict, Any

from .base_provider import JobProvider


class HimalayasProvider(JobProvider):
    name = "Himalayas"
    BASE_URL = "https://himalayas.app/jobs/api/search"

    def search(self, title: str, location: str, keywords: str = "",
               work_type: str = "All", commitment: str = "All",
               limit: int = 20) -> List[Dict[str, Any]]:
        try:
            q_parts = [p for p in [title, keywords] if p]
            q_str = " ".join(q_parts) if q_parts else "Software Engineer"
            url = f"{self.BASE_URL}?q={urllib.parse.quote(q_str)}&limit={min(limit, 50)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            jobs_raw = data.get("jobs", [])
            results = []
            for jd in jobs_raw:
                loc_restrictions = jd.get("locationRestrictions") or []
                loc = ", ".join(loc_restrictions) if loc_restrictions else "Remote"
                desc = self.clean_html(jd.get("description") or "")
                if not desc:
                    desc = jd.get("excerpt") or "No description available."
                commitment_str = self.map_commitment(jd.get("employmentType") or "")
                if commitment != "All" and commitment_str.lower() != commitment.lower():
                    continue
                wt = self.map_work_type(loc, not bool(loc_restrictions))
                if work_type != "All" and wt.lower() != work_type.lower():
                    continue
                guid = jd.get("guid") or f"{jd.get('title','')}{jd.get('companyName','')}"
                job = {
                    "id": self.make_job_id(guid),
                    "title": jd.get("title") or "Untitled",
                    "company": jd.get("companyName") or "Unknown",
                    "location": loc,
                    "work_type": wt,
                    "commitment": commitment_str,
                    "platform": "Himalayas",
                    "description": desc,
                    "apply_url": jd.get("applicationLink") or "#",
                    "easy_apply": False,
                    "posted_date": self.format_date(jd.get("pubDate")),
                    "source_url": jd.get("applicationLink") or "",
                }
                results.append(job)
            return results
        except Exception as e:
            print(f"[HimalayasProvider] Error: {e}")
            return []
