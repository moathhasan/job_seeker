# JobSeeker: AI Multi-Platform Auto-Apply & ATS Resume Optimizer

**JobSeeker** is a robust, full-stack job search assistant and ATS (Applicant Tracking System) resume optimization platform. It aggregates live job listings in parallel from over 13 platforms, calculates real-time ATS match scores against your CV, and generates tailored resumes with downloadable PDFs.

---

## 🚀 Key Features

* **Multi-Platform Scraper**: Searches and consolidates jobs in parallel across **13+ sources** (including Himalayas, LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google Jobs, Greenhouse, Lever, Ashby, and SmartRecruiters).
* **ATS Scoring Engine**: Deeply analyzes job descriptions against your CV, extracting matched and missing skills with an actionable resume optimization checklist.
* **Resume Tailoring & PDF Export**: Automatically injects missing keywords, restructures your CV formatting using a modern layout, and generates premium downloadable PDF resumes using ReportLab.
* **Simulated Auto-Apply**: Animated application runner that auto-fills details and simulates submitting applications for "Easy Apply" roles.
* **Secure Admin Dashboard**: Access analytics, manage user sessions, inspect job cache health, and securely configure API credentials (Adzuna, Jooble, JSearch/RapidAPI, etc.) stored in your MySQL database.
* **Premium UI/UX**: Responsive glassmorphism interface styled with a custom CSS design system, dark mode theme, smooth animations, and comprehensive accessibility features (focus states, screen-reader ARIA tags).

---

## 🛠️ Technology Stack

* **Backend**: Python 3.10+, FastAPI, PyMySQL, DBUtils (connection pooling), ReportLab (PDF generation)
* **Frontend**: Vanilla HTML5, CSS3 (Custom Variables & flexbox/grid), Vanilla JavaScript (No frameworks/compilers)
* **Database**: MySQL (Only, configured with UTF8MB4 for full Unicode support)

---

## ⚙️ Getting Started

### Prerequisites
* Python 3.10 or higher
* MySQL Server running on `localhost:3306`

### 1. Installation
Clone the repository and install the dependencies:
```bash
git clone https://github.com/moathhasan/job_seeker.git
cd job_seeker
pip install -r requirements.txt
```

### 2. Configure Database & Environment
Set your MySQL root password using environment variables before running the application:
```powershell
# PowerShell (Windows)
$env:MYSQL_PASSWORD="your_mysql_password"

# Bash (Linux/macOS)
export MYSQL_PASSWORD="your_mysql_password"
```

### 3. Run the App
Start the Uvicorn FastAPI server:
```bash
python run.py
```

The application will be available at:
* **Candidate Portal**: [http://127.0.0.1:8001](http://127.0.0.1:8001)
* **Admin Dashboard**: [http://127.0.0.1:8001/admin.html](http://127.0.0.1:8001/admin.html)
  * *Default admin credentials*: `admin` / `admin123`

---

## 🔒 Configuration

You can configure API keys to unlock advanced job engines (Adzuna, Jooble, and JSearch) for international and deep country-specific searches:
1. Log in to the **Admin Dashboard** (`/admin.html`).
2. Go to the **API Settings** tab.
3. Configure your API keys. Saved credentials are encrypted and stored in your MySQL database.
