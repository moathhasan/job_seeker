"""
SmartRecruiters public Posting API — no auth required.
Company list: SMARTRECRUITERS_COMPANIES setting (comma-separated company identifiers)
"""
import requests
from typing import List, Dict, Any

from .base_provider import JobProvider
from .settings_service import get_setting

DEFAULT_COMPANIES = (
    "spotify,philips,bosch,lidl,delivery-hero,talabat,"
    "wire,adyen,booking,trivago,zalando,n26,"
    "hellofresh,personio,celonis,contentful,sumup"
)


class SmartRecruitersProvider(JobProvider):
    name = "SmartRecruiters"
    BASE_URL = "https://api.smartrecruiters.com/v1/companies/{co}/postings"

    def search(self, title: str, location: str, keywords: str = "",
               work_type: str = "All", commitment: str = "All",
               limit: int = 20) -> List[Dict[str, Any]]:
        companies_str = get_setting("SMARTRECRUITERS_COMPANIES", DEFAULT_COMPANIES)
        companies = [c.strip() for c in companies_str.split(",") if c.strip()]
        search_terms = [t.lower() for t in filter(None, [title, keywords])]
        results = []
        for co in companies:
            if len(results) >= limit:
                break
            try:
                params = {"limit": 100}
                if title:
                    params["q"] = title
                url = self.BASE_URL.format(co=co)
                resp = requests.get(url, params=params, timeout=8)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                for jd in data.get("content", []):
                    if len(results) >= limit:
                        break
                    job_title = (jd.get("name") or "").lower()
                    if search_terms and not any(t in job_title for t in search_terms):
                        continue
                    loc_obj = jd.get("location") or {}
                    loc_parts = [p for p in [
                        loc_obj.get("city"), loc_obj.get("region"), loc_obj.get("country")
                    ] if p]
                    loc = ", ".join(loc_parts) or location or "Remote"
                    is_remote = loc_obj.get("remote", False)
                    wt = self.map_work_type(loc, is_remote)
                    if work_type != "All" and wt.lower() != work_type.lower():
                        continue
                    commitment_str = self.map_commitment(jd.get("typeOfEmployment", {}).get("label") or "")
                    if commitment != "All" and commitment_str.lower() != commitment.lower():
                        continue
                    apply_url = jd.get("ref") or f"https://careers.smartrecruiters.com/{co}/{jd.get('id','')}"
                    desc = jd.get("jobAd", {}).get("sections", {}).get("jobDescription", {}).get("text") or ""
                    desc = self.clean_html(desc)
                    job = {
                        "id": self.make_job_id(str(jd.get("id") or apply_url)),
                        "title": jd.get("name") or "Untitled",
                        "company": jd.get("company", {}).get("name") or co.replace("-", " ").title(),
                        "location": loc,
                        "work_type": wt,
                        "commitment": commitment_str,
                        "platform": "SmartRecruiters",
                        "description": desc or "View full job description on SmartRecruiters.",
                        "apply_url": apply_url,
                        "easy_apply": False,
                        "posted_date": self.format_date(jd.get("releasedDate")),
                        "source_url": apply_url,
                    }
                    results.append(job)
            except Exception as e:
                print(f"[SmartRecruitersProvider] Error for {co}: {e}")
                continue
        return results
