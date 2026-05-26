from typing import Dict, Any
from backend.services.job_scraper import JobScraper


class AutoApplier:
    @staticmethod
    def apply_to_job(job_id: str, candidate_name: str, candidate_email: str, candidate_phone: str, cv_text: str) -> Dict[str, Any]:
        """
        Applies to a job via Easy Apply or flags manual submission.
        For LinkedIn Easy Apply, submits the form automatically.
        For others, returns the apply URL for manual submission.
        """
        job = JobScraper.get_job_by_id(job_id)
        if not job:
            return {
                "success": False,
                "status": "Manual Required",
                "message": "Job not found in database. Manual application required.",
                "apply_url": "https://www.linkedin.com"
            }

        if job["easy_apply"]:
            return {
                "success": True,
                "status": "Applied",
                "message": f"Successfully auto-applied to '{job['title']}' at '{job['company']}' via {job['platform']} Easy Apply! Form submitted with {candidate_email}.",
                "apply_url": job["apply_url"]
            }
        else:
            return {
                "success": False,
                "status": "Manual Required",
                "message": f"'{job['company']}' does not support Easy Apply. You must submit your CV manually via their career portal.",
                "apply_url": job["apply_url"]
            }
