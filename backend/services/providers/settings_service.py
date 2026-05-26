"""
Settings Service — reads API keys from the `api_settings` MySQL table.
Results are cached in-memory for CACHE_TTL seconds so we don't
hit the DB on every job search request.
Thread-safe: all cache access is protected by a Lock.
"""
import time
import threading
from typing import Dict, Optional

CACHE_TTL = 300  # 5 minutes

_cache: Dict[str, str] = {}
_cache_loaded_at: float = 0.0
_cache_lock = threading.Lock()


def _load_settings() -> Dict[str, str]:
    global _cache, _cache_loaded_at
    now = time.time()
    with _cache_lock:
        if now - _cache_loaded_at < CACHE_TTL and _cache:
            return dict(_cache)  # return a copy
    # Load outside the lock to avoid holding it during I/O
    try:
        from backend.database import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT setting_key, setting_value FROM api_settings")
                rows = cur.fetchall()
                new_cache = {r["setting_key"]: r["setting_value"] for r in rows}
                with _cache_lock:
                    _cache = new_cache
                    _cache_loaded_at = now
        finally:
            conn.close()
    except Exception as e:
        print(f"[SettingsService] Could not load settings from DB: {e}")
    with _cache_lock:
        return dict(_cache)


def get_setting(key: str, default: str = "") -> str:
    """Return a setting value by key; fall back to env var, then default."""
    import os
    settings = _load_settings()
    val = settings.get(key, "").strip()
    if not val:
        val = os.getenv(key, default).strip()
    return val


def set_setting(key: str, value: str, description: str = "") -> bool:
    """Upsert a setting in the DB and invalidate the cache."""
    global _cache_loaded_at
    try:
        from backend.database import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO api_settings (setting_key, setting_value, description)
                       VALUES (%s, %s, %s)
                       ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value),
                                                description   = VALUES(description)""",
                    (key, value, description)
                )
            conn.commit()
            with _cache_lock:
                _cache_loaded_at = 0.0  # invalidate
            return True
        finally:
            conn.close()
    except Exception as e:
        print(f"[SettingsService] Could not save setting '{key}': {e}")
        return False


def get_all_settings() -> Dict[str, dict]:
    """Return all settings with their metadata (no plaintext values)."""
    try:
        from backend.database import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT setting_key, setting_value, description, updated_at FROM api_settings ORDER BY setting_key"
                )
                rows = cur.fetchall()
                result = {}
                for r in rows:
                    val = r["setting_value"] or ""
                    result[r["setting_key"]] = {
                        "description": r["description"],
                        "updated_at": str(r["updated_at"]) if r["updated_at"] else None,
                        "has_value": bool(val.strip()),
                        # Mask secret keys -- show only first 4 chars, never the full value
                        "masked_value": (val[:4] + "****") if len(val) > 4 else ("****" if val else "")
                    }
                return result
        finally:
            conn.close()
    except Exception as e:
        print(f"[SettingsService] Could not get all settings: {e}")
        return {}


def invalidate_cache():
    global _cache_loaded_at
    with _cache_lock:
        _cache_loaded_at = 0.0
