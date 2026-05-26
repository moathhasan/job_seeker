"""
We Work Remotely — parses their public RSS feed.
No API key needed. Returns remote-only tech jobs.
"""
import requests
from typing import List, Dict, Any

from .base_provider import JobProvider


class WeWorkRemotelyProvider(JobProvider):
    name = "We Work Remotely"
    RSS_URL = "https://weworkremotely.com/remote-jobs.rss"

    def search(self, title: str, location: str, keywords: str = "",
               work_type: str = "All", commitment: str = "All",
               limit: int = 20) -> List[Dict[str, Any]]:
        # WWR is remote-only — skip if explicitly searching for on-site
        if work_type == "On-site":
            return []
        try:
            import feedparser
        except ImportError:
            print("[WeWorkRemotelyProvider] feedparser not installed. Run: pip install feedparser")
            return []
        try:
            resp = requests.get(self.RSS_URL, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            feed = feedparser.parse(resp.text)
            search_terms = [t.lower() for t in filter(None, [title, keywords])]
            results = []
            for entry in feed.entries:
                if len(results) >= limit:
                    break
                entry_title = (entry.get("title") or "").lower()
                if search_terms and not any(t in entry_title for t in search_terms):
                    continue
                # Parse "Company: Job Title" format from WWR
                raw_title = entry.get("title") or "Untitled"
                parts = raw_title.split(":", 1)
                company = parts[0].strip() if len(parts) > 1 else "Unknown"
                job_title = parts[1].strip() if len(parts) > 1 else raw_title
                desc = self.clean_html(entry.get("summary") or "")
                apply_url = entry.get("link") or "#"
                job = {
                    "id": self.make_job_id(apply_url),
                    "title": job_title,
                    "company": company,
                    "location": "Remote",
                    "work_type": "Remote",
                    "commitment": "Full-time",
                    "platform": "We Work Remotely",
                    "description": desc or "View full job description on We Work Remotely.",
                    "apply_url": apply_url,
                    "easy_apply": False,
                    "posted_date": self.format_date(entry.get("published")),
                    "source_url": apply_url,
                }
                results.append(job)
            return results
        except Exception as e:
            print(f"[WeWorkRemotelyProvider] Error: {e}")
            return []
