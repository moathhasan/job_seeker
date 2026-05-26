"""
Ashby public job board API — no auth required.
Queries companies in parallel for speed.
Company list: ASHBY_COMPANIES setting (comma-separated board names)
"""
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

from .base_provider import JobProvider
from .settings_service import get_setting

DEFAULT_COMPANIES = (
    "ashby,retool,ramp,brex,rippling,deel,lattice,mercury,"
    "benchling,verkada,clickhouse,dbt,airbyte,meltano,"
    "posthog,metabase,cal,liveblocks,clerk,resend,loops,trigger"
)

_MAX_COMPANIES_PER_SEARCH = 8


class AshbyProvider(JobProvider):
    name = "Ashby"
    BASE_URL = "https://api.ashbyhq.com/posting-api/job-board/{board}"

    def _fetch_company(self, board, search_terms, location, work_type, commitment, limit):
        """Fetch jobs for a single Ashby board."""
        jobs = []
        try:
            url = self.BASE_URL.format(board=board) + "?includeCompensation=true"
            resp = requests.get(url, timeout=6)
            if resp.status_code != 200:
                return jobs
            data = resp.json()
            for jd in data.get("jobPostings", []):
                if len(jobs) >= limit:
                    break
                job_title = (jd.get("title") or "").lower()
                if search_terms and not any(t in job_title for t in search_terms):
                    continue
                loc = jd.get("locationName") or location or "Remote"
                is_remote = jd.get("isRemote", False)
                wt = self.map_work_type(loc, is_remote)
                if work_type != "All" and wt.lower() != work_type.lower():
                    continue
                commitment_str = self.map_commitment(jd.get("employmentType") or "")
                if commitment != "All" and commitment_str.lower() != commitment.lower():
                    continue
                desc = self.clean_html(jd.get("descriptionHtml") or jd.get("descriptionSafe") or "")
                apply_url = jd.get("jobUrl") or "#"
                jobs.append({
                    "id": self.make_job_id(jd.get("id") or apply_url),
                    "title": jd.get("title") or "Untitled",
                    "company": jd.get("organizationName") or board.title(),
                    "location": loc,
                    "work_type": wt,
                    "commitment": commitment_str,
                    "platform": "Ashby",
                    "description": desc or "View full job description on Ashby.",
                    "apply_url": apply_url,
                    "easy_apply": False,
                    "posted_date": self.format_date(jd.get("publishedDate")),
                    "source_url": apply_url,
                })
        except Exception as e:
            print(f"[AshbyProvider] Error for {board}: {e}")
        return jobs

    def search(self, title: str, location: str, keywords: str = "",
               work_type: str = "All", commitment: str = "All",
               limit: int = 20) -> List[Dict[str, Any]]:
        companies_str = get_setting("ASHBY_COMPANIES", DEFAULT_COMPANIES)
        companies = [c.strip() for c in companies_str.split(",") if c.strip()]
        companies = companies[:_MAX_COMPANIES_PER_SEARCH]
        search_terms = [t.lower() for t in filter(None, [title, keywords])]
        results = []

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {
                pool.submit(self._fetch_company, board, search_terms, location, work_type, commitment, limit): board
                for board in companies
            }
            for future in as_completed(futures):
                if len(results) >= limit:
                    break
                jobs = future.result()
                remaining = limit - len(results)
                results.extend(jobs[:remaining])

        return results
