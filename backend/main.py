import os
import shutil
import hashlib
import secrets
import time as _time
import asyncio
from collections import defaultdict
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Optional

from backend.schemas import (
    ParsedCV, JobSearchQuery, Job, ATSAnalysisRequest, 
    ATSAnalysisResult, TailorCVRequest, TailorCVResponse, 
    ApplyRequest, ApplyResponse, UserRegister, UserLogin, 
    UserResponse, AuthResponse
)
from pydantic import BaseModel
from backend.services.cv_parser import CVParser
from backend.services.ats_analyzer import ATSAnalyzer
from backend.services.job_scraper import JobScraper
from backend.services.auto_applier import AutoApplier
from backend.database import init_db, get_connection
from backend.services.providers.settings_service import get_all_settings, set_setting, invalidate_cache

# Ensure directories exist
os.makedirs("backend/data/uploads", exist_ok=True)
os.makedirs("backend/data/tailored", exist_ok=True)
os.makedirs("frontend", exist_ok=True)
os.makedirs("frontend/css", exist_ok=True)
os.makedirs("frontend/js", exist_ok=True)

app = FastAPI(title="JobSeeker Multi-Platform Assistant", version="1.0.0")

# CORS middleware -- restrict to explicit origins (configurable via env var)
_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:8001,http://127.0.0.1:8001").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Simple in-memory rate limiter (no extra dependency needed)
# ---------------------------------------------------------------------------
_rate_limit_store: dict = defaultdict(list)  # ip -> [timestamps]

def _check_rate_limit(client_ip: str, max_requests: int, window_seconds: int):
    """Raises 429 if client exceeds max_requests within window_seconds."""
    now = _time.time()
    timestamps = _rate_limit_store[client_ip]
    # Prune old entries
    _rate_limit_store[client_ip] = [t for t in timestamps if now - t < window_seconds]
    if len(_rate_limit_store[client_ip]) >= max_requests:
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Please wait and try again."
        )
    _rate_limit_store[client_ip].append(now)

@app.on_event("startup")
async def startup_event():
    try:
        init_db()
        print("Database initialized successfully.")
        # Cleanup expired sessions on startup
        _cleanup_expired_sessions()
    except Exception as e:
        print(f"FATAL: Database initialization failed: {e}")
        import sys
        sys.exit(1)

def _cleanup_expired_sessions():
    """Delete sessions inactive for more than 7 days."""
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM user_sessions WHERE last_activity < NOW() - INTERVAL 7 DAY")
                count = cursor.rowcount
            conn.commit()
            if count > 0:
                print(f"[Auth] Cleaned up {count} expired session(s).")
        finally:
            conn.close()
    except Exception as e:
        print(f"[Auth] Session cleanup failed: {e}")

# Helper Functions for Password Hashing and Auth Sessions
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return f"{salt.hex()}:{pwd_hash.hex()}"

def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, hash_hex = stored_hash.split(":")
        salt = bytes.fromhex(salt_hex)
        pwd_hash = bytes.fromhex(hash_hex)
        new_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return new_hash == pwd_hash
    except Exception:
        return False

async def get_current_user_id(authorization: Optional[str]) -> Optional[int]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ")[1]
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Only accept sessions active within the last 24 hours
            cursor.execute(
                "SELECT user_id FROM user_sessions WHERE token = %s AND last_activity >= NOW() - INTERVAL 24 HOUR",
                (token,)
            )
            row = cursor.fetchone()
            if row:
                cursor.execute("UPDATE user_sessions SET last_activity = CURRENT_TIMESTAMP WHERE token = %s", (token,))
                conn.commit()
                return row["user_id"]
    except Exception:
        return None
    finally:
        conn.close()
    return None

async def get_current_admin_id(authorization: Optional[str]) -> Optional[int]:
    user_id = await get_current_user_id(authorization)
    if not user_id:
        return None
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT is_admin FROM users WHERE id = %s", (user_id,))
            row = cursor.fetchone()
            if row and row["is_admin"] == 1:
                return user_id
    except Exception:
        return None
    finally:
        conn.close()
    return None

# AUTH ENDPOINTS
@app.post("/api/auth/register", response_model=AuthResponse)
async def register(req: UserRegister, request: Request):
    _check_rate_limit(request.client.host, max_requests=5, window_seconds=60)
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s", (req.username, req.email))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Username or Email already registered")
            
            pwd_hash = hash_password(req.password)
            cursor.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
                (req.username, req.email, pwd_hash)
            )
            user_id = cursor.lastrowid
            
            # Create user profile placeholder
            cursor.execute(
                "INSERT INTO user_profiles (user_id, fullname, email, phone, cv_text, cv_filename) VALUES (%s, %s, %s, %s, %s, %s)",
                (user_id, req.username, req.email, "", "", "")
            )
            
            # Generate Session Token
            token = secrets.token_hex(32)
            cursor.execute("INSERT INTO user_sessions (token, user_id) VALUES (%s, %s)", (token, user_id))
            
            conn.commit()
            return AuthResponse(
                token=token,
                user=UserResponse(id=user_id, username=req.username, email=req.email)
            )
    finally:
        conn.close()

@app.post("/api/auth/login", response_model=AuthResponse)
async def login(req: UserLogin, request: Request):
    _check_rate_limit(request.client.host, max_requests=5, window_seconds=60)
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE username = %s", (req.username,))
            row = cursor.fetchone()
            if not row or not verify_password(req.password, row["password_hash"]):
                raise HTTPException(status_code=401, detail="Invalid username or password")
            
            user_id = row["id"]
            token = secrets.token_hex(32)
            cursor.execute("INSERT INTO user_sessions (token, user_id) VALUES (%s, %s)", (token, user_id))
            conn.commit()
            
            return AuthResponse(
                token=token,
                user=UserResponse(id=user_id, username=row["username"], email=row["email"])
            )
    finally:
        conn.close()

@app.post("/api/auth/logout")
async def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM user_sessions WHERE token = %s", (token,))
            conn.commit()
        finally:
            conn.close()
    return {"message": "Logged out successfully"}

@app.get("/api/auth/me")
async def get_me(authorization: Optional[str] = Header(None)):
    user_id = await get_current_user_id(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT username, email, is_admin FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            cursor.execute("SELECT * FROM user_profiles WHERE user_id = %s", (user_id,))
            profile = cursor.fetchone()
            
            cv_text = profile["cv_text"] if profile else ""
            parsed_cv = None
            if cv_text:
                try:
                    parsed_cv = CVParser.parse_cv(cv_text.encode("utf-8", errors="ignore"), "cv.txt")
                except Exception as e:
                    print(f"Error parsing saved CV on the fly: {e}")
                    
            return {
                "id": user_id,
                "username": user["username"],
                "email": user["email"],
                "is_admin": user["is_admin"],
                "fullname": profile["fullname"] if profile else user["username"],
                "profile_email": profile["email"] if profile else user["email"],
                "phone": profile["phone"] if profile else "",
                "cv_text": cv_text,
                "cv_filename": profile["cv_filename"] if profile else "",
                "parsed_cv": parsed_cv
            }
    finally:
        conn.close()

# API Endpoints
MAX_CV_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_CV_EXTENSIONS = {".pdf", ".docx", ".txt"}

@app.post("/api/upload-cv", response_model=ParsedCV)
async def upload_cv(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    try:
        # Validate filename and extension
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_CV_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Allowed: PDF, DOCX, TXT")

        # Read with size limit
        file_bytes = await file.read()
        if len(file_bytes) > MAX_CV_SIZE:
            raise HTTPException(status_code=413, detail="File too large. Maximum size is 10 MB.")
        if len(file_bytes) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        parsed_cv = CVParser.parse_cv(file_bytes, file.filename)
        
        # Save uploaded file - prevent path traversal, use unique name
        import uuid as _uuid
        safe_filename = f"{_uuid.uuid4().hex}{ext}"
        save_path = f"backend/data/uploads/{safe_filename}"
        with open(save_path, "wb") as buffer:
            buffer.write(file_bytes)
            
        # If user is logged in, save details to database
        user_id = await get_current_user_id(authorization)
        if user_id:
            conn = get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO user_profiles (user_id, fullname, email, phone, cv_text, cv_filename)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            fullname = VALUES(fullname),
                            email = VALUES(email),
                            phone = VALUES(phone),
                            cv_text = VALUES(cv_text),
                            cv_filename = VALUES(cv_filename)
                    """, (user_id, parsed_cv.get("name") or "", parsed_cv.get("email") or "", parsed_cv.get("phone") or "", parsed_cv.get("raw_text") or "", file.filename))
                conn.commit()
            finally:
                conn.close()
                
        return parsed_cv
    except HTTPException:
        raise
    except Exception as e:
        print(f"[UploadCV] Error: {e}")
        raise HTTPException(status_code=400, detail="Failed to parse CV. Please upload a valid PDF, DOCX, or TXT file.")

class UserProfileUpdate(BaseModel):
    fullname: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

@app.post("/api/update-profile")
async def update_profile(profile: UserProfileUpdate, authorization: Optional[str] = Header(None)):
    user_id = await get_current_user_id(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE user_profiles 
                SET fullname = COALESCE(%s, fullname),
                    email = COALESCE(%s, email),
                    phone = COALESCE(%s, phone)
                WHERE user_id = %s
            """, (profile.fullname, profile.email, profile.phone, user_id))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    from fastapi import Response
    return Response(status_code=204)

# Use regular 'def' (not async) so FastAPI runs it in a threadpool,
# preventing the sync JobScraper/ATSAnalyzer from blocking the event loop.
@app.post("/api/search-jobs", response_model=List[Job])
def search_jobs(query: JobSearchQuery, request: Request, authorization: Optional[str] = Header(None)):
    _check_rate_limit(request.client.host, max_requests=30, window_seconds=60)
    # Query logged at INFO level (no PII);
    print(f"[SearchJobs] title='{query.title}' location='{query.location}' work_type='{query.work_type}'")
    try:
        cv_text = query.cv_text
        if not cv_text and authorization:
            # Sync wrapper for the async helper (we're in a threadpool already)
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in a sync def called from FastAPI's threadpool
                    # Can't use await, so do a direct DB lookup
                    token = authorization.split(" ")[1] if authorization and authorization.startswith("Bearer ") else None
                    if token:
                        conn = get_connection()
                        try:
                            with conn.cursor() as cursor:
                                cursor.execute(
                                    "SELECT p.cv_text FROM user_sessions s "
                                    "JOIN user_profiles p ON s.user_id = p.user_id "
                                    "WHERE s.token = %s AND s.last_activity >= NOW() - INTERVAL 24 HOUR",
                                    (token,)
                                )
                                row = cursor.fetchone()
                                if row:
                                    cv_text = row["cv_text"]
                        finally:
                            conn.close()
            except Exception:
                pass
                    
        jobs = JobScraper.search_jobs(query)
        
        # If user has a CV loaded, pre-calculate ATS alignment scores on-the-fly!
        if cv_text:
            for job in jobs:
                analysis = ATSAnalyzer.analyze_ats(cv_text, job["description"])
                job["ats_score"] = analysis["score"]
                
        # Sort jobs by ATS score (highest first) if available, otherwise keep default
        if cv_text:
            jobs.sort(key=lambda x: x.get("ats_score", 0), reverse=True)
            
        return jobs
    except HTTPException:
        raise
    except Exception as e:
        print(f"[SearchJobs] Error: {e}")
        raise HTTPException(status_code=500, detail="Job search failed. Please try again.")

@app.post("/api/analyze-ats", response_model=ATSAnalysisResult)
def analyze_ats(request_body: ATSAnalysisRequest, request: Request, authorization: Optional[str] = Header(None)):
    _check_rate_limit(request.client.host, max_requests=20, window_seconds=60)
    try:
        analysis = ATSAnalyzer.analyze_ats(request_body.cv_text, request_body.job_description)
        return analysis
    except Exception as e:
        print(f"[ATS] Error: {e}")
        raise HTTPException(status_code=500, detail="ATS analysis failed. Please try again.")

@app.post("/api/tailor-cv", response_model=TailorCVResponse)
def tailor_cv(request_body: TailorCVRequest, request: Request, authorization: Optional[str] = Header(None)):
    _check_rate_limit(request.client.host, max_requests=5, window_seconds=60)
    # Require authentication for CV tailoring (generates files on disk)
    token = authorization.split(" ")[1] if authorization and authorization.startswith("Bearer ") else None
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required to tailor CVs.")
    try:
        tailored_text, download_url = ATSAnalyzer.tailor_cv(
            cv_text=request_body.cv_text,
            job_description=request_body.job_description,
            job_title=request_body.job_title,
            company_name=request_body.company_name,
            missing_skills=request_body.missing_skills
        )
        return TailorCVResponse(tailored_text=tailored_text, download_url=download_url)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TailorCV] Error: {e}")
        raise HTTPException(status_code=400, detail="CV tailoring failed. Please try again.")

@app.post("/api/apply", response_model=ApplyResponse)
def apply(request_body: ApplyRequest, request: Request, authorization: Optional[str] = Header(None)):
    _check_rate_limit(request.client.host, max_requests=10, window_seconds=60)
    # Require authentication for job applications
    token = authorization.split(" ")[1] if authorization and authorization.startswith("Bearer ") else None
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required to apply for jobs.")
    try:
        result = AutoApplier.apply_to_job(
            job_id=request_body.job_id,
            candidate_name=request_body.full_name,
            candidate_email=request_body.email,
            candidate_phone=request_body.phone or "",
            cv_text=request_body.cv_text
        )
        return ApplyResponse(
            success=result["success"],
            status=result["status"],
            message=result["message"],
            apply_url=result["apply_url"]
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Apply] Error: {e}")
        raise HTTPException(status_code=500, detail="Application failed. Please try again.")

# ADMIN ENDPOINTS
@app.post("/api/admin/login", response_model=AuthResponse)
async def admin_login(req: UserLogin, request: Request):
    _check_rate_limit(request.client.host, max_requests=3, window_seconds=60)
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE username = %s AND is_admin = 1", (req.username,))
            row = cursor.fetchone()
            if not row or not verify_password(req.password, row["password_hash"]):
                raise HTTPException(status_code=401, detail="Invalid admin username or password")
            
            user_id = row["id"]
            token = secrets.token_hex(32)
            cursor.execute("INSERT INTO user_sessions (token, user_id) VALUES (%s, %s)", (token, user_id))
            conn.commit()
            
            return AuthResponse(
                token=token,
                user=UserResponse(id=user_id, username=row["username"], email=row["email"])
            )
    finally:
        conn.close()

@app.get("/api/admin/stats")
async def admin_stats(authorization: Optional[str] = Header(None)):
    admin_id = await get_current_admin_id(authorization)
    if not admin_id:
        raise HTTPException(status_code=401, detail="Unauthorized admin access")
    
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Total Registered Users
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_admin = 0")
            total_users = cursor.fetchone()["count"]
            
            # 2. Logged In Users (Active Sessions for non-admins)
            cursor.execute("""
                SELECT COUNT(DISTINCT s.user_id) as count 
                FROM user_sessions s
                JOIN users u ON s.user_id = u.id
                WHERE u.is_admin = 0
            """)
            logged_in_users = cursor.fetchone()["count"]
            
            # 3. Active Users (sessions with activity in last 15 minutes)
            cursor.execute("""
                SELECT COUNT(DISTINCT s.user_id) as count 
                FROM user_sessions s
                JOIN users u ON s.user_id = u.id
                WHERE u.is_admin = 0 AND s.last_activity >= NOW() - INTERVAL 15 MINUTE
            """)
            active_users = cursor.fetchone()["count"]
            
            # 4. User List (all non-admin users)
            cursor.execute("""
                SELECT u.id, u.username, u.email, u.created_at,
                       (SELECT MAX(s.last_activity) FROM user_sessions s WHERE s.user_id = u.id) as last_seen,
                       (SELECT COUNT(*) FROM user_sessions s WHERE s.user_id = u.id) as session_count
                FROM users u
                WHERE u.is_admin = 0
                ORDER BY u.created_at DESC
            """)
            users_list = cursor.fetchall()
            
            for u in users_list:
                if u["created_at"]:
                    u["created_at"] = u["created_at"].isoformat() if hasattr(u["created_at"], "isoformat") else str(u["created_at"])
                if u["last_seen"]:
                    u["last_seen"] = u["last_seen"].isoformat() if hasattr(u["last_seen"], "isoformat") else str(u["last_seen"])
                    
            # 5. Live Sessions List
            cursor.execute("""
                SELECT s.token, s.user_id, u.username, u.email, s.created_at, s.last_activity
                FROM user_sessions s
                JOIN users u ON s.user_id = u.id
                WHERE u.is_admin = 0
                ORDER BY s.last_activity DESC
            """)
            sessions_list = []
            for s in cursor.fetchall():
                masked_token = f"{s['token'][:8]}...{s['token'][-4:]}" if len(s['token']) > 12 else "***"
                sessions_list.append({
                    "token": masked_token,
                    "user_id": s["user_id"],
                    "username": s["username"],
                    "created_at": str(s["created_at"]),
                    "last_activity": str(s["last_activity"])
                })
            
            return {
                "total_users": total_users,
                "logged_in_users": logged_in_users,
                "active_users": active_users,
                "users": users_list,
                "sessions": sessions_list
            }
    finally:
        conn.close()

@app.post("/api/admin/revoke-session")
async def revoke_session(req: dict, authorization: Optional[str] = Header(None)):
    admin_id = await get_current_admin_id(authorization)
    if not admin_id:
        raise HTTPException(status_code=401, detail="Unauthorized admin access")
    
    token_to_revoke = req.get("token")
    if not token_to_revoke:
        raise HTTPException(status_code=400, detail="Token is required")
        
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM user_sessions WHERE token = %s", (token_to_revoke,))
            conn.commit()
            return {"success": True, "message": "Session revoked successfully"}
    finally:
        conn.close()


@app.get("/api/admin/settings")
async def get_admin_settings(authorization: Optional[str] = Header(None)):
    """Return all API settings (keys masked) for the admin dashboard."""
    admin_id = await get_current_admin_id(authorization)
    if not admin_id:
        raise HTTPException(status_code=401, detail="Unauthorized admin access")
    return get_all_settings()


@app.post("/api/admin/settings")
async def update_admin_settings(req: dict, authorization: Optional[str] = Header(None)):
    """Upsert one or more API settings. Expects {"settings": {"KEY": "value", ...}}"""
    admin_id = await get_current_admin_id(authorization)
    if not admin_id:
        raise HTTPException(status_code=401, detail="Unauthorized admin access")
    
    settings = req.get("settings", {})
    if not isinstance(settings, dict) or not settings:
        raise HTTPException(status_code=400, detail="'settings' dict is required")
    
    saved = []
    failed = []
    for key, value in settings.items():
        ok = set_setting(key, str(value))
        (saved if ok else failed).append(key)
    
    invalidate_cache()
    return {
        "success": True,
        "saved": saved,
        "failed": failed,
        "message": f"{len(saved)} setting(s) saved successfully."
    }


@app.get("/api/admin/provider-status")
async def get_provider_status(authorization: Optional[str] = Header(None)):
    """Return status of all job providers (configured vs not_configured)."""
    admin_id = await get_current_admin_id(authorization)
    if not admin_id:
        raise HTTPException(status_code=401, detail="Unauthorized admin access")
    return {"providers": JobScraper.get_provider_status()}


@app.post("/api/admin/clear-job-cache")
async def clear_job_cache(authorization: Optional[str] = Header(None)):
    """Clear all cached jobs from MySQL so next search fetches fresh data."""
    admin_id = await get_current_admin_id(authorization)
    if not admin_id:
        raise HTTPException(status_code=401, detail="Unauthorized admin access")
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM jobs")
            count = cursor.rowcount
        conn.commit()
        return {"success": True, "message": f"Cleared {count} cached job(s) from database."}
    finally:
        conn.close()

class NoCacheStaticFiles(StaticFiles):
    def is_not_modified(self, response_headers, request_headers) -> bool:
        return False
        
    async def get_response(self, path: str, scope):
        if path.endswith(".db"):
            raise HTTPException(status_code=403, detail="Forbidden: Cannot access database files")
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response

# Mount static downloads — ONLY tailored PDFs (uploads are NOT publicly accessible)
app.mount("/static/tailored", NoCacheStaticFiles(directory="backend/data/tailored"), name="static")

# Mount frontend files
app.mount("/", NoCacheStaticFiles(directory="frontend", html=True), name="frontend")
