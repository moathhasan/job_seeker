"""
Adzuna Jobs API provider.
Keys: ADZUNA_APP_ID, ADZUNA_APP_KEY (stored in api_settings table)
Free tier: https://developer.adzuna.com/
"""
import requests
from typing import List, Dict, Any

from .base_provider import JobProvider
from .settings_service import get_setting


class AdzunaProvider(JobProvider):
    name = "Adzuna"
    BASE_URL = "https://api.adzuna.com/v1/api/jobs"

    def search(self, title: str, location: str, keywords: str = "",
               work_type: str = "All", commitment: str = "All",
               limit: int = 20) -> List[Dict[str, Any]]:
        app_id = get_setting("ADZUNA_APP_ID")
        app_key = get_setting("ADZUNA_APP_KEY")
        if not app_id or not app_key:
            print("[AdzunaProvider] Skipped - no API credentials configured.")
            return []
        try:
            # Detect country from location
            country = self._detect_country(location)
            what = " ".join(filter(None, [title, keywords])) or "Software Engineer"
            params = {
                "app_id": app_id,
                "app_key": app_key,
                "what": what,
                "results_per_page": min(limit, 50),
                "content-type": "application/json",
            }
            if location and "remote" not in location.lower():
                params["where"] = location
            if work_type == "Remote":
                params["what"] = what + " remote"

            url = f"{self.BASE_URL}/{country}/search/1"
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for jd in data.get("results", []):
                desc = self.clean_html(jd.get("description") or "")
                loc = jd.get("location", {}).get("display_name") or location or "Remote"
                wt = self.map_work_type(loc, "remote" in (title + " " + keywords).lower())
                if work_type != "All" and wt.lower() != work_type.lower():
                    continue
                commitment_str = self.map_commitment(jd.get("contract_time") or "")
                if commitment != "All" and commitment_str.lower() != commitment.lower():
                    continue
                apply_url = jd.get("redirect_url") or jd.get("apply_url") or "#"
                job = {
                    "id": self.make_job_id(jd.get("id") or apply_url),
                    "title": jd.get("title") or "Untitled",
                    "company": jd.get("company", {}).get("display_name") or "Unknown",
                    "location": loc,
                    "work_type": wt,
                    "commitment": commitment_str,
                    "platform": "Adzuna",
                    "description": desc or "No description available.",
                    "apply_url": apply_url,
                    "easy_apply": False,
                    "posted_date": self.format_date(jd.get("created")),
                    "source_url": apply_url,
                }
                results.append(job)
            return results
        except Exception as e:
            print(f"[AdzunaProvider] Error: {e}")
            return []

    @staticmethod
    def _detect_country(location: str) -> str:
        loc = (location or "").lower()
        mapping = {
            "uk": "gb", "united kingdom": "gb", "london": "gb", "england": "gb",
            "australia": "au", "sydney": "au", "melbourne": "au",
            "canada": "ca", "toronto": "ca", "vancouver": "ca",
            "germany": "de", "berlin": "de", "munich": "de",
            "france": "fr", "paris": "fr",
            "india": "in", "bangalore": "in", "mumbai": "in",
            "singapore": "sg",
            "netherlands": "nl", "amsterdam": "nl",
            "new zealand": "nz",
            "south africa": "za",
            "brazil": "br",
            "poland": "pl",
            "russia": "ru",
        }
        for key, code in mapping.items():
            if key in loc:
                return code
        return "us"  # default to USA
