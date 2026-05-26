"""
Base class for all job providers.
Every provider must implement the `search` method.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import hashlib


class JobProvider(ABC):
    """Abstract base class for all job data providers."""

    name: str = "BaseProvider"

    @abstractmethod
    def search(self, title: str, location: str, keywords: str = "",
               work_type: str = "All", commitment: str = "All",
               limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search for jobs and return a list of normalized job dicts.
        Each dict must have all required Job schema fields.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    @staticmethod
    def make_job_id(unique_str: str) -> str:
        """Generate a stable, collision-resistant job ID from any unique string."""
        return "job-" + hashlib.md5(unique_str.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def clean_html(raw: str) -> str:
        """Strip HTML tags and normalize whitespace."""
        import re, html
        if not raw:
            return ""
        text = re.sub(r"<(?:p|div|br|li|h[1-6]|ul|ol)[^>]*>", "\n", raw, flags=re.I)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        return text.strip()

    @staticmethod
    def format_date(pub_date) -> str:
        """Convert a date/timestamp to human-readable relative string."""
        from datetime import datetime, timezone
        if not pub_date:
            return "Recently"
        try:
            if isinstance(pub_date, (int, float)):
                dt = datetime.fromtimestamp(pub_date)
            elif isinstance(pub_date, str):
                if "T" in pub_date:
                    dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                    dt = dt.replace(tzinfo=None)
                else:
                    parts = pub_date.strip().split()
                    if len(parts) >= 3:
                        return " ".join(parts[1:4])
                    return pub_date
            elif isinstance(pub_date, datetime):
                dt = pub_date.replace(tzinfo=None)
            else:
                return "Recently"
            diff = datetime.utcnow() - dt
            if diff.days == 0:
                h = diff.seconds // 3600
                return "Just now" if h == 0 else f"{h}h ago"
            elif diff.days == 1:
                return "Yesterday"
            elif diff.days < 7:
                return f"{diff.days} days ago"
            else:
                return dt.strftime("%b %d, %Y")
        except Exception:
            return "Recently"

    @staticmethod
    def map_commitment(raw: str) -> str:
        r = (raw or "").lower()
        if "part" in r:
            return "Part-time"
        if "contract" in r or "freelance" in r or "temporary" in r:
            return "Contract"
        if "intern" in r:
            return "Internship"
        return "Full-time"

    @staticmethod
    def map_work_type(location: str, remote_flag: bool = False) -> str:
        loc = (location or "").lower()
        if remote_flag or "remote" in loc:
            return "Remote"
        if "hybrid" in loc:
            return "Hybrid"
        return "On-site"
