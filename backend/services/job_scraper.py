"""
JobScraper — orchestrates all real job providers.
Architecture:
  1. Check MySQL 6-hour cache
  2. Run providers in parallel (ThreadPoolExecutor)
  3. Deduplicate by source_url, normalize, cache in MySQL
  4. Return results

No mock data. No fake jobs. Real sources only.
"""
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from typing import List, Dict, Any, Optional

from backend.schemas import JobSearchQuery

# Provider imports
from backend.services.providers.himalayas_provider import HimalayasProvider
from backend.services.providers.adzuna_provider import AdzunaProvider
from backend.services.providers.jooble_provider import JoobleProvider
from backend.services.providers.jsearch_provider import JSearchProvider
from backend.services.providers.greenhouse_provider import GreenhouseProvider
from backend.services.providers.lever_provider import LeverProvider
from backend.services.providers.ashby_provider import AshbyProvider
from backend.services.providers.smartrecruiters_provider import SmartRecruitersProvider
from backend.services.providers.jobspy_provider import JobSpyProvider
from backend.services.providers.weworkremotely_provider import WeWorkRemotelyProvider
from backend.services.providers.remoteco_provider import RemoteCoProvider
from backend.services.providers.workingnomads_provider import WorkingNomadsProvider
from backend.services.providers.apify_provider import ApifyProvider

# ---------------------------------------------------------------------------
# Cache TTL and provider registry
# ---------------------------------------------------------------------------
CACHE_TTL_HOURS = 6
PROVIDER_TIMEOUT_SECONDS = 20

ALL_PROVIDERS = [
    HimalayasProvider(),
    AdzunaProvider(),
    JoobleProvider(),
    JSearchProvider(),
    GreenhouseProvider(),
    LeverProvider(),
    AshbyProvider(),
    SmartRecruitersProvider(),
    JobSpyProvider(),
    WeWorkRemotelyProvider(),
    RemoteCoProvider(),
    WorkingNomadsProvider(),
    ApifyProvider(),
]


def _cache_key(query: JobSearchQuery) -> str:
    parts = "|".join([
        (query.title or "").lower().strip(),
        (query.location or "").lower().strip(),
        (query.work_type or "All").lower(),
        (query.commitment or "All").lower(),
    ])
    return hashlib.md5(parts.encode()).hexdigest()


def _get_cached_jobs(query: JobSearchQuery) -> Optional[List[Dict]]:
    """Return cached jobs if they are fresher than CACHE_TTL_HOURS."""
    try:
        from backend.database import get_connection
        key = _cache_key(query)
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, title, company, location, work_type, commitment,
                              platform, description, apply_url, easy_apply, posted_date
                       FROM jobs
                       WHERE cache_key = %s
                         AND scraped_at >= NOW() - INTERVAL %s HOUR
                       ORDER BY scraped_at DESC
                       LIMIT 100""",
                    (key, CACHE_TTL_HOURS)
                )
                rows = cur.fetchall()
                if rows:
                    return [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception as e:
        print(f"[JobScraper] Cache read error: {e}")
    return None


def _save_jobs_to_db(jobs: List[Dict], cache_key_val: str):
    """Upsert jobs into MySQL with cache key and timestamp."""
    if not jobs:
        return
    try:
        from backend.database import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                for job in jobs:
                    cur.execute(
                        """INSERT INTO jobs
                               (id, title, company, location, work_type, commitment,
                                platform, description, apply_url, easy_apply,
                                posted_date, source_url, cache_key, scraped_at)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                           ON DUPLICATE KEY UPDATE
                               title = VALUES(title),
                               company = VALUES(company),
                               location = VALUES(location),
                               work_type = VALUES(work_type),
                               commitment = VALUES(commitment),
                               platform = VALUES(platform),
                               description = VALUES(description),
                               apply_url = VALUES(apply_url),
                               easy_apply = VALUES(easy_apply),
                               posted_date = VALUES(posted_date),
                               source_url = VALUES(source_url),
                               cache_key = VALUES(cache_key),
                               scraped_at = NOW()""",
                        (
                            job["id"], job["title"], job["company"], job["location"],
                            job["work_type"], job["commitment"], job["platform"],
                            job["description"][:65000], job["apply_url"],
                            1 if job.get("easy_apply") else 0,
                            job["posted_date"],
                            (job.get("source_url") or "")[:500],
                            cache_key_val
                        )
                    )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print(f"[JobScraper] DB save error: {e}")


def _deduplicate(jobs: List[Dict]) -> List[Dict]:
    """Remove duplicate jobs by source_url (or apply_url as fallback)."""
    seen_urls = set()
    seen_ids = set()
    unique = []
    for job in jobs:
        url = (job.get("source_url") or job.get("apply_url") or "").strip().lower()
        job_id = job.get("id", "")
        # Skip if bad URL or already seen
        if not url or url == "#":
            continue
        if url in seen_urls or job_id in seen_ids:
            continue
        seen_urls.add(url)
        seen_ids.add(job_id)
        unique.append(job)
    return unique


def _filter_by_query(jobs: List[Dict], query: JobSearchQuery) -> List[Dict]:
    """Apply client-side filters that individual providers may have missed."""
    title_q = (query.title or "").lower().strip()
    location_q = (query.location or "").lower().strip()
    keywords_q = (query.keywords or "").lower().strip()
    results = []
    for job in jobs:
        # Work type filter
        if query.work_type and query.work_type != "All":
            if job.get("work_type", "").lower() != query.work_type.lower():
                continue
        # Commitment filter
        if query.commitment and query.commitment != "All":
            if job.get("commitment", "").lower() != query.commitment.lower():
                continue
        # Title relevance filter (at least one word must match)
        if title_q:
            combined = f"{job.get('title','').lower()} {job.get('description','').lower()}"
            title_words = [w for w in title_q.split() if len(w) > 2]
            if title_words and not any(w in combined for w in title_words):
                continue
        # Location filter
        if location_q and location_q not in ("remote", "anywhere", "worldwide"):
            job_loc = job.get("location", "").lower()
            job_wt = job.get("work_type", "").lower()
            if location_q not in job_loc and job_wt != "remote":
                continue
        # Keywords filter
        if keywords_q:
            combined = f"{job.get('title','').lower()} {job.get('description','').lower()}"
            if keywords_q not in combined:
                continue
        results.append(job)
    return results


class JobScraper:
    """Orchestrates all real job providers and manages MySQL cache."""

    @staticmethod
    def search_jobs(query: JobSearchQuery) -> List[Dict[str, Any]]:
        # 1. Check cache first
        cached = _get_cached_jobs(query)
        if cached:
            print(f"[JobScraper] Serving {len(cached)} jobs from cache.")
            filtered = _filter_by_query(cached, query)
            return filtered[:80]

        # 2. Run all providers in parallel
        title = (query.title or "").strip()
        location = (query.location or "").strip()
        keywords = (query.keywords or "").strip()
        work_type = query.work_type or "All"
        commitment = query.commitment or "All"

        all_jobs: List[Dict] = []
        print(f"[JobScraper] Running {len(ALL_PROVIDERS)} providers for: '{title}' in '{location}'")

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(
                    provider.search, title, location, keywords, work_type, commitment, 25
                ): provider.name
                for provider in ALL_PROVIDERS
            }
            done_names = set()
            try:
                for future in as_completed(futures, timeout=35):
                    provider_name = futures[future]
                    done_names.add(provider_name)
                    try:
                        results = future.result(timeout=PROVIDER_TIMEOUT_SECONDS)
                        if results:
                            print(f"[JobScraper] {provider_name}: {len(results)} jobs")
                            all_jobs.extend(results)
                        else:
                            print(f"[JobScraper] {provider_name}: 0 jobs")
                    except TimeoutError:
                        print(f"[JobScraper] {provider_name}: TIMEOUT (inner)")
                    except Exception as e:
                        print(f"[JobScraper] {provider_name}: ERROR - {e}")
            except TimeoutError:
                # Some providers didn't finish in 35s - log and continue with what we have
                slow = [n for f, n in futures.items() if n not in done_names]
                print(f"[JobScraper] Global timeout - slow providers: {slow}")

        # 3. Deduplicate and filter
        unique_jobs = _deduplicate(all_jobs)
        filtered_jobs = _filter_by_query(unique_jobs, query)
        print(f"[JobScraper] Total: {len(all_jobs)} -> unique: {len(unique_jobs)} -> filtered: {len(filtered_jobs)}")

        # 4. Cache in MySQL
        cache_key_val = _cache_key(query)
        _save_jobs_to_db(unique_jobs, cache_key_val)

        return filtered_jobs[:80]

    @staticmethod
    def get_job_by_id(job_id: str) -> Optional[Dict[str, Any]]:
        """Look up a single job by ID from MySQL."""
        from backend.database import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM jobs WHERE id = %s", (job_id,))
                row = cur.fetchone()
                if row:
                    return {
                        "id": row["id"],
                        "title": row["title"],
                        "company": row["company"],
                        "location": row["location"],
                        "work_type": row["work_type"],
                        "commitment": row["commitment"],
                        "platform": row["platform"],
                        "description": row["description"],
                        "apply_url": row["apply_url"],
                        "easy_apply": bool(row["easy_apply"]),
                        "posted_date": row["posted_date"],
                    }
        finally:
            conn.close()
        return None

    @staticmethod
    def get_provider_status() -> List[Dict]:
        """Return status of all configured providers."""
        from backend.services.providers.settings_service import get_setting
        statuses = []
        key_map = {
            "Adzuna": ("ADZUNA_APP_ID", "ADZUNA_APP_KEY"),
            "Jooble": ("JOOBLE_API_KEY",),
            "JSearch": ("JSEARCH_API_KEY",),
            "Apify": ("APIFY_TOKEN",),
        }
        for provider in ALL_PROVIDERS:
            keys = key_map.get(provider.name, ())
            if keys:
                configured = all(get_setting(k) for k in keys)
                status = "configured" if configured else "not_configured"
            else:
                status = "active"  # No key needed
            statuses.append({
                "name": provider.name,
                "status": status,
                "requires_key": bool(keys),
            })
        return statuses


# Backwards-compat helpers used by other modules
def clean_html(raw_html):
    from backend.services.providers.base_provider import JobProvider
    return JobProvider.clean_html(raw_html)


def format_pub_date(pub_date_str):
    from backend.services.providers.base_provider import JobProvider
    return JobProvider.format_date(pub_date_str)
