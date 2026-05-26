"""
python-jobspy provider — scrapes LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google Jobs.
No API key required. Uses rotating browser headers to avoid blocks.
"""
from typing import List, Dict, Any
import traceback

from .base_provider import JobProvider


class JobSpyProvider(JobProvider):
    name = "JobSpy"

    def search(self, title: str, location: str, keywords: str = "",
               work_type: str = "All", commitment: str = "All",
               limit: int = 20) -> List[Dict[str, Any]]:
        try:
            from jobspy import scrape_jobs
            import pandas as pd
        except ImportError:
            print("[JobSpyProvider] python-jobspy not installed. Run: pip install python-jobspy")
            return []
        try:
            search_term = " ".join(filter(None, [title, keywords])) or "Software Engineer"
            is_remote = work_type == "Remote" or (location or "").lower() == "remote"
            if is_remote:
                search_term += " remote"

            # Supported countries set
            VALID_COUNTRIES = {
                "argentina", "australia", "austria", "bahrain", "bangladesh", "belgium", "bulgaria", 
                "brazil", "canada", "chile", "china", "colombia", "costa rica", "croatia", "cyprus", 
                "czech republic", "czechia", "denmark", "ecuador", "egypt", "estonia", "finland", 
                "france", "germany", "greece", "hong kong", "hungary", "india", "indonesia", "ireland", 
                "israel", "italy", "japan", "kuwait", "latvia", "lithuania", "luxembourg", "malaysia", 
                "malta", "mexico", "morocco", "netherlands", "new zealand", "nigeria", "norway", "oman", 
                "pakistan", "panama", "peru", "philippines", "poland", "portugal", "qatar", "romania", 
                "saudi arabia", "singapore", "slovakia", "slovenia", "south africa", "south korea", 
                "spain", "sweden", "switzerland", "taiwan", "thailand", "turkey", "türkiye", "ukraine", 
                "united arab emirates", "uk", "united kingdom", "usa", "us", "united states", 
                "uruguay", "venezuela", "vietnam", "worldwide"
            }
            
            COUNTRY_MAP = {
                "us": "united states",
                "usa": "united states",
                "uk": "united kingdom",
                "gb": "united kingdom",
                "uae": "united arab emirates",
                "ca": "canada",
                "au": "australia",
                "in": "india",
                "nz": "new zealand",
                "za": "south africa",
                "de": "germany",
                "fr": "france",
            }
            
            country_indeed = "USA"
            if location and not is_remote:
                parts = [p.strip() for p in location.split(",")]
                potential_country = parts[-1].strip().lower()
                
                # Check country code mapping
                mapped = COUNTRY_MAP.get(potential_country)
                if mapped:
                    potential_country = mapped
                
                if potential_country in VALID_COUNTRIES:
                    country_indeed = potential_country
                else:
                    print(f"[JobSpyProvider] Country '{potential_country}' is not supported by python-jobspy. Skipping JobSpy provider to prevent crashes.")
                    return []

            sites = ["indeed", "linkedin", "glassdoor", "zip_recruiter", "google"]
            df = scrape_jobs(
                site_name=sites,
                search_term=search_term,
                location=location if not is_remote else "",
                results_wanted=min(limit, 20),
                country_indeed=country_indeed,
                is_remote=is_remote,
                hours_old=72,
            )
            if df is None or df.empty:
                return []
            results = []
            for _, row in df.iterrows():
                if len(results) >= limit:
                    break
                # Skip rows with missing critical data
                job_title = str(row.get("title") or "")
                if not job_title or job_title == "nan":
                    continue
                company = str(row.get("company") or "Unknown")
                loc = str(row.get("location") or location or "Remote")
                desc = str(row.get("description") or "")
                apply_url = str(row.get("job_url") or row.get("apply_url") or "#")
                site = str(row.get("site") or "LinkedIn")
                platform_map = {
                    "linkedin": "LinkedIn", "indeed": "Indeed",
                    "glassdoor": "Glassdoor", "zip_recruiter": "ZipRecruiter",
                    "google": "Google Jobs",
                }
                platform = platform_map.get(site.lower(), site.title())
                wt = self.map_work_type(loc, is_remote or "remote" in loc.lower())
                if work_type != "All" and wt.lower() != work_type.lower():
                    continue
                job_type_raw = str(row.get("job_type") or "")
                commitment_str = self.map_commitment(job_type_raw)
                if commitment != "All" and commitment_str.lower() != commitment.lower():
                    continue
                date_posted = row.get("date_posted")
                job = {
                    "id": self.make_job_id(apply_url + job_title),
                    "title": job_title,
                    "company": company if company != "nan" else "Unknown",
                    "location": loc if loc != "nan" else (location or "Remote"),
                    "work_type": wt,
                    "commitment": commitment_str,
                    "platform": platform,
                    "description": desc if desc != "nan" and desc else "View full job description.",
                    "apply_url": apply_url if apply_url != "nan" else "#",
                    "easy_apply": bool(row.get("is_easy_apply", False)),
                    "posted_date": self.format_date(date_posted),
                    "source_url": apply_url,
                }
                results.append(job)
            return results
        except Exception as e:
            print(f"[JobSpyProvider] Error: {e}")
            traceback.print_exc()
            return []
