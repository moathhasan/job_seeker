"""
Remote.co — parses their public RSS feed.
No API key needed. Remote jobs only.
"""
import requests
from typing import List, Dict, Any

from .base_provider import JobProvider


class RemoteCoProvider(JobProvider):
    name = "Remote.co"
    RSS_URL = "https://remote.co/feed/"

    def search(self, title: str, location: str, keywords: str = "",
               work_type: str = "All", commitment: str = "All",
               limit: int = 20) -> List[Dict[str, Any]]:
        if work_type == "On-site":
            return []
        try:
            import feedparser
        except ImportError:
            print("[RemoteCoProvider] feedparser not installed.")
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
                desc = self.clean_html(entry.get("summary") or entry.get("content", [{}])[0].get("value", ""))
                apply_url = entry.get("link") or "#"
                # Try extracting company from author or category
                company = entry.get("author") or "Unknown"
                job = {
                    "id": self.make_job_id(apply_url),
                    "title": entry.get("title") or "Untitled",
                    "company": company,
                    "location": "Remote",
                    "work_type": "Remote",
                    "commitment": "Full-time",
                    "platform": "Remote.co",
                    "description": desc or "View full job description on Remote.co.",
                    "apply_url": apply_url,
                    "easy_apply": False,
                    "posted_date": self.format_date(entry.get("published")),
                    "source_url": apply_url,
                }
                results.append(job)
            return results
        except Exception as e:
            print(f"[RemoteCoProvider] Error: {e}")
            return []
