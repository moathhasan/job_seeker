from pydantic import BaseModel, Field
from typing import List, Optional
import re


def _validate_email(v: str) -> str:
    """Basic email format validation."""
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, v):
        raise ValueError('Invalid email format')
    return v


class ParsedCV(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    job_title: Optional[str] = None
    skills: List[str] = []
    experience: List[str] = []
    education: List[str] = []
    raw_text: str = ""

class JobSearchQuery(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    location: Optional[str] = Field(None, max_length=200)
    work_type: Optional[str] = Field("All", max_length=20)
    commitment: Optional[str] = Field("All", max_length=30)
    platform: Optional[str] = Field("All", max_length=50)
    keywords: Optional[str] = Field(None, max_length=500)
    cv_text: Optional[str] = Field(None, max_length=200000)

class Job(BaseModel):
    id: str
    title: str = Field(max_length=500)
    company: str = Field(max_length=500)
    location: str = Field(max_length=1000)
    work_type: str  # Remote, Hybrid, On-site
    commitment: str  # Full-time, Part-time, Contract, Internship
    platform: str
    description: str = Field(max_length=100000)
    apply_url: str = Field(max_length=2048)
    easy_apply: bool
    posted_date: str
    ats_score: Optional[int] = None

class ATSAnalysisRequest(BaseModel):
    cv_text: str = Field(min_length=10, max_length=200000)
    job_description: str = Field(min_length=10, max_length=200000)

class ATSAnalysisResult(BaseModel):
    score: int
    matched_skills: List[str]
    missing_skills: List[str]
    recommendations: List[str]

class TailorCVRequest(BaseModel):
    cv_text: str = Field(min_length=10, max_length=200000)
    job_description: str = Field(min_length=10, max_length=200000)
    job_title: str = Field(min_length=1, max_length=200)
    company_name: str = Field(min_length=1, max_length=200)
    missing_skills: List[str] = Field(max_length=50)

class TailorCVResponse(BaseModel):
    tailored_text: str
    download_url: str

class ApplyRequest(BaseModel):
    job_id: str = Field(min_length=1, max_length=100)
    cv_text: str = Field(min_length=10, max_length=200000)
    full_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=5, max_length=100)
    phone: Optional[str] = Field(None, max_length=30)
    cover_letter: Optional[str] = Field(None, max_length=50000)

class ApplyResponse(BaseModel):
    success: bool
    status: str  # Applied, Pending, Manual Required
    message: str
    apply_url: Optional[str] = None

class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_]+$')
    email: str = Field(min_length=5, max_length=100)
    password: str = Field(min_length=8, max_length=128)

class UserLogin(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)

class UserResponse(BaseModel):
    id: int
    username: str
    email: str

class AuthResponse(BaseModel):
    token: str
    user: UserResponse
