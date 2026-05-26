// Application State & Auth Helper
let appState = {
    token: localStorage.getItem("jobseeker_token") || null,
    isGuest: false,
    currentCV: null,
    cvUploading: false,
    jobs: [],
    selectedJob: null,
    stats: {
        matches: 0,
        ats: 0,
        applied: 0,
        tailored: 0
    },
    profile: {
        fullname: "Job Seeker",
        email: "candidate@seeker.com",
        phone: "(555) 019-2834",
        scraperMode: "mock"
    },
    // Lock flags to prevent double-click / race conditions
    isSearching: false,
    isApplying: false,
    isTailoring: false
};
// XSS Protection Utilities
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}
function sanitizeHtml(html) {
    if (typeof DOMPurify !== 'undefined') return DOMPurify.sanitize(html || '');
    return escapeHtml(html);
}
function safeInitials(name) {
    if (!name || typeof name !== 'string') return 'JS';
    return name.trim().split(/\s+/).filter(Boolean).map(n => n[0]).join('').substring(0, 2).toUpperCase() || 'JS';
}

async function authFetch(url, options = {}) {
    if (!options.headers) {
        options.headers = {};
    }
    if (appState.token) {
        options.headers["Authorization"] = `Bearer ${appState.token}`;
    }
    return fetch(url, options);
}

// SVG Circle properties
const CIRCLE_RADIUS = 34;
const CIRCLE_CIRCUMFERENCE = 2 * Math.PI * CIRCLE_RADIUS; // ~213.6

// Helper to construct real platform search URLs for mock jobs
function getRealPlatformSearchUrl(job) {
    const title = job.title;
    const company = job.company;
    const location = job.location;
    const platform = job.platform.toLowerCase();
    const query = `${title} ${company}`;
    
    if (platform.includes("linkedin")) {
        return `https://www.linkedin.com/jobs/search/?keywords=${encodeURIComponent(query)}&location=${encodeURIComponent(location)}`;
    }
    if (platform.includes("indeed")) {
        return `https://www.indeed.com/jobs?q=${encodeURIComponent(query)}&l=${encodeURIComponent(location)}`;
    }
    if (platform.includes("google")) {
        return `https://www.google.com/search?q=${encodeURIComponent(query + " jobs " + location)}`;
    }
    if (platform.includes("ziprecruiter")) {
        return `https://www.ziprecruiter.com/candidate/search?search=${encodeURIComponent(query)}&location=${encodeURIComponent(location)}`;
    }
    if (platform.includes("monster")) {
        return `https://www.monster.com/jobs/search?q=${encodeURIComponent(title)}&where=${encodeURIComponent(location)}`;
    }
    if (platform.includes("careerbuilder")) {
        return `https://www.careerbuilder.com/jobs?keywords=${encodeURIComponent(query)}&location=${encodeURIComponent(location)}`;
    }
    if (platform.includes("we work remotely") || platform.includes("weworkremotely")) {
        return `https://weworkremotely.com/remote-jobs/search?term=${encodeURIComponent(query)}`;
    }
    if (platform.includes("flexjobs")) {
        return `https://www.flexjobs.com/search?search=${encodeURIComponent(query)}`;
    }
    if (platform.includes("remote.co")) {
        return `https://remote.co/?s=${encodeURIComponent(query)}`;
    }
    if (platform.includes("working nomads")) {
        return `https://www.workingnomads.com/jobs?search=${encodeURIComponent(title)}`;
    }
    if (platform.includes("dice")) {
        return `https://www.dice.com/jobs?q=${encodeURIComponent(query)}&countryCode=US&radius=30&radiusUnit=mi&page=1&pageSize=20&filters.employmentType=FULLTIME&language=en`;
    }
    if (platform.includes("upwork")) {
        return `https://www.upwork.com/nx/search/jobs/?q=${encodeURIComponent(query)}`;
    }
    if (platform.includes("fiverr")) {
        return `https://www.fiverr.com/search/gigs?query=${encodeURIComponent(query)}`;
    }
    if (platform.includes("toptal")) {
        return `https://www.toptal.com/talent/find?q=${encodeURIComponent(query)}`;
    }
    return `https://www.google.com/search?q=${encodeURIComponent(query + " " + location + " jobs")}`;
}

function getJobActionUrl(job) {
    const url = job.apply_url;
    if (!url) return getRealPlatformSearchUrl(job);
    const isPlaceholder = url.includes("linkedin.com/jobs/view/100") || 
                          url.includes("indeed.com/viewjob?jk=200") || 
                          url.includes("ziprecruiter.com/jobs/") || 
                          url.includes("careers.google.com/jobs/results/500") || 
                          url.includes("monster.com/job/") || 
                          url.includes("careerbuilder.com/job/") || 
                          url.includes("weworkremotely.com/jobs/") || 
                          url.includes("flexjobs.com/job/") || 
                          url.includes("remote.co/job/") || 
                          url.includes("workingnomads.com/jobs/") || 
                          url.includes("dice.com/job/") || 
                          url.includes("upwork.com/jobs/") || 
                          url.includes("fiverr.com/jobs/") || 
                          url.includes("toptal.com/jobs/");
                          
    if (isPlaceholder) {
        return getRealPlatformSearchUrl(job);
    }
    return url;
}

// DOM Elements
const navItems = document.querySelectorAll('.nav-item');
const sections = document.querySelectorAll('.page-section');
const headerTitle = document.getElementById('header-title');
const headerSubtitle = document.getElementById('header-subtitle');
const profileDisplayName = document.getElementById('profile-display-name');
const avatarLetters = document.getElementById('avatar-letters');

// CV Upload Elements
const cvDropzone = document.getElementById('cv-dropzone');
const cvFileInput = document.getElementById('cv-file-input');
const cvProfileBox = document.getElementById('cv-profile-box');
const cvName = document.getElementById('cv-name');
const cvContact = document.getElementById('cv-contact');
const cvSkillsList = document.getElementById('cv-skills-list');
const cvExperience = document.getElementById('cv-experience');
const cvEducation = document.getElementById('cv-education');

// Search Elements
const searchTitleInput = document.getElementById('search-title');
const searchLocationInput = document.getElementById('search-location');
const searchPlatformSelect = document.getElementById('search-platform');
const searchWorkStyleSelect = document.getElementById('search-work-type');
const searchCommitmentSelect = document.getElementById('search-commitment');
const searchBtn = document.getElementById('search-btn');
const jobsContainer = document.getElementById('jobs-container');

// Side Drawer Elements
const atsSidePanel = document.getElementById('ats-side-panel');
const closePanelBtn = document.getElementById('close-panel-btn');
const panelJobTitle = document.getElementById('panel-job-title');
const panelJobCompany = document.getElementById('panel-job-company');
const panelAtsScore = document.getElementById('panel-ats-score');
const panelAtsSummary = document.getElementById('panel-ats-summary');
const panelProgressCircle = document.getElementById('ats-progress-ring-circle');
const panelMatchedSkills = document.getElementById('panel-matched-skills');
const panelMissingSkills = document.getElementById('panel-missing-skills');
const panelRecommendations = document.getElementById('panel-recommendations');
const panelJobDescription = document.getElementById('panel-job-description');
const panelActionButtons = document.getElementById('panel-action-buttons');
const autoApplyBox = document.getElementById('auto-apply-box');
const autoApplySteps = document.getElementById('auto-apply-steps');

// CV Optimizer Elements
const optJobTitle = document.getElementById('opt-job-title');
const optJobMeta = document.getElementById('opt-job-meta');
const optOriginalText = document.getElementById('opt-original-text');
const optTailoredText = document.getElementById('opt-tailored-text');
const optDownloadBtn = document.getElementById('opt-download-btn');
const optBackBtn = document.getElementById('opt-back-btn');

// Settings Elements
const settingsFullname = document.getElementById('settings-fullname');
const settingsEmail = document.getElementById('settings-email');
const settingsPhone = document.getElementById('settings-phone');
const settingsScraper = document.getElementById('settings-scraper-api');
const saveSettingsBtn = document.getElementById('save-settings-btn');

// Toast Elements
const toastNotification = document.getElementById('toast-notification');
const toastIcon = document.getElementById('toast-icon');
const toastMessage = document.getElementById('toast-message');

// Initialize Progress Ring on Side Panel
if (panelProgressCircle) {
    panelProgressCircle.style.strokeDasharray = `${CIRCLE_CIRCUMFERENCE} ${CIRCLE_CIRCUMFERENCE}`;
    panelProgressCircle.style.strokeDashoffset = CIRCLE_CIRCUMFERENCE;
}

// ----------------------------------------------------
// Navigation Logic
// ----------------------------------------------------
navItems.forEach(item => {
    item.addEventListener('click', (e) => {
        const targetSectionId = item.getAttribute('data-target');
        
        if (appState.isGuest && targetSectionId === 'section-settings') {
            showToast("Access Locked: Please log in or register to view settings.", "warning");
            appState.token = null;
            checkAuth();
            return;
        }
        
        // Remove active class from all nav items and sections
        navItems.forEach(n => n.classList.remove('active'));
        sections.forEach(s => s.classList.remove('active'));
        
        // Set target as active
        item.classList.add('active');
        const targetSection = document.getElementById(targetSectionId);
        if (targetSection) targetSection.classList.add('active');
        
        // Update headers based on target section
        if (targetSectionId === 'section-dashboard') {
            headerTitle.textContent = "Dashboard";
            headerSubtitle.textContent = "Analyze your CV, search jobs, and auto-apply across platforms.";
        } else if (targetSectionId === 'section-optimizer') {
            headerTitle.textContent = "CV Tailor & Optimizer";
            headerSubtitle.textContent = "Improve alignment score by matching job description requirements.";
            
            // Populate original CV text if available
            if (appState.currentCV && appState.currentCV.raw_text) {
                optOriginalText.value = appState.currentCV.raw_text;
            } else {
                optOriginalText.value = "";
            }
            
            if (appState.selectedJob) {
                optJobTitle.textContent = `Tailoring CV: ${appState.selectedJob.title}`;
                optJobMeta.textContent = `${appState.selectedJob.company} | ${appState.selectedJob.location} | Current ATS Match Score: ${appState.selectedJob.ats_score || '0'}%`;
            } else {
                optJobTitle.textContent = "Optimize CV for Specific Job";
                optJobMeta.textContent = "Compare, inject missing keywords, and download targeted versions.";
                optTailoredText.value = "Please go to the Dashboard and click 'Tailor Resume' on a job listing to view tailored modifications.";
                optDownloadBtn.removeAttribute("href");
                optDownloadBtn.style.pointerEvents = "none";
                optDownloadBtn.style.opacity = "0.5";
            }
        } else if (targetSectionId === 'section-settings') {
            headerTitle.textContent = "Settings";
            headerSubtitle.textContent = "Configure candidate details and API integrations.";
        }
        
        // Close side drawer when navigating away from dashboard
        if (targetSectionId !== 'section-dashboard') {
            closeSidePanel();
        }
    });
});

optBackBtn.addEventListener('click', () => {
    // Navigate back to dashboard tab
    document.querySelector('[data-target="section-dashboard"]').click();
});

// ----------------------------------------------------
// CV Upload Handling
// ----------------------------------------------------
// Drag and drop events
cvDropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    if (appState.cvUploading) return;
    cvDropzone.classList.add('dragover');
});

cvDropzone.addEventListener('dragleave', () => {
    cvDropzone.classList.remove('dragover');
});

cvDropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    cvDropzone.classList.remove('dragover');
    if (appState.cvUploading) return;
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleCVUpload(files[0]);
    }
});

cvDropzone.addEventListener('click', () => {
    if (appState.cvUploading) return;
    cvFileInput.click();
});

cvFileInput.addEventListener('change', () => {
    if (cvFileInput.files.length > 0) {
        handleCVUpload(cvFileInput.files[0]);
    }
});

// Re-upload CV click event
const reuploadCvBtn = document.getElementById("reupload-cv-btn");
if (reuploadCvBtn) {
    reuploadCvBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (appState.cvUploading) return;
        cvProfileBox.style.display = "none";
        cvDropzone.style.display = "block";
        cvFileInput.click();
    });
}

function displayCVDetails(data) {
    cvName.textContent = data.name || "Extracted Name";
    cvContact.textContent = `${data.email || 'No email'} | ${data.phone || 'No phone'}`;
    
    // Display skills tags
    cvSkillsList.innerHTML = "";
    if (data.skills && data.skills.length > 0) {
        data.skills.forEach(skill => {
            const span = document.createElement("span");
            span.className = "tag";
            span.textContent = skill;
            cvSkillsList.appendChild(span);
        });
    } else {
        cvSkillsList.innerHTML = `<span class="tag">Loaded from Account</span>`;
    }

    // Display experience and education
    if (cvExperience) {
        cvExperience.innerHTML = formatExperienceHTML(data.experience);
    }
    if (cvEducation) {
        cvEducation.innerHTML = formatEducationHTML(data.education);
    }
    
    cvDropzone.style.display = "none";
    cvProfileBox.style.display = "flex";
}

async function handleCVUpload(file) {
    if (appState.cvUploading) return;
    
    const promptDiv = document.getElementById("cv-upload-prompt");
    const progressContainer = document.getElementById("cv-upload-progress-container");
    const progressBar = document.getElementById("cv-progress-bar");
    const progressPercent = document.getElementById("cv-progress-percent");
    const progressTitle = document.getElementById("cv-progress-title");
    
    appState.cvUploading = true;
    if (promptDiv) promptDiv.style.display = "none";
    if (progressContainer) progressContainer.style.display = "block";
    if (progressBar) progressBar.style.width = "0%";
    if (progressPercent) progressPercent.textContent = "0%";
    if (progressTitle) progressTitle.textContent = "Uploading CV...";
    
    showToast("Starting CV upload...", "info");

    const formData = new FormData();
    formData.append("file", file);

    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", "/api/upload-cv");
        
        if (appState.token) {
            xhr.setRequestHeader("Authorization", `Bearer ${appState.token}`);
        }

        // Track upload progress
        xhr.upload.addEventListener("progress", (e) => {
            if (e.lengthComputable) {
                const percent = Math.round((e.loaded / e.total) * 100);
                if (progressBar) progressBar.style.width = `${percent}%`;
                if (progressPercent) progressPercent.textContent = `${percent}%`;
                
                if (percent === 100) {
                    if (progressTitle) progressTitle.textContent = "Parsing CV & extracting skills...";
                }
            }
        });

        // Response handling
        xhr.addEventListener("load", async () => {
            appState.cvUploading = false;
            if (promptDiv) promptDiv.style.display = "block";
            if (progressContainer) progressContainer.style.display = "none";
            if (progressBar) progressBar.style.width = "0%";

            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    const data = JSON.parse(xhr.responseText);
                    appState.currentCV = data;
                    
                    // Sync candidate details
                    if (data.name) {
                        appState.profile.fullname = data.name;
                        settingsFullname.value = data.name;
                        profileDisplayName.textContent = data.name;
                        
                        // Generate initials for avatar
                        const initials = safeInitials(data.name);
                        avatarLetters.textContent = initials;
                    }
                    if (data.email) {
                        appState.profile.email = data.email;
                        settingsEmail.value = data.email;
                    }
                    if (data.phone) {
                        appState.profile.phone = data.phone;
                        settingsPhone.value = data.phone;
                    }
                    
                    displayCVDetails(data);
                    showToast("CV uploaded and parsed successfully!", "success");
                    
                    // Trigger auto search based on extracted info
                    searchTitleInput.value = data.job_title || (data.skills && data.skills[0]) || "Software Engineer";
                    triggerJobSearch();
                    resolve(data);
                } catch (err) {
                    console.error("Failed to parse server response", err);
                    showToast("Error processing CV. Invalid response from server.", "danger");
                    reject(err);
                }
            } else {
                showToast("Error parsing CV. Make sure it is a valid PDF or DOCX file.", "danger");
                reject(new Error(`Upload failed with status ${xhr.status}`));
            }
        });

        xhr.addEventListener("error", () => {
            appState.cvUploading = false;
            if (promptDiv) promptDiv.style.display = "block";
            if (progressContainer) progressContainer.style.display = "none";
            if (progressBar) progressBar.style.width = "0%";
            showToast("Network error during CV upload.", "danger");
            reject(new Error("Network error"));
        });

        xhr.addEventListener("abort", () => {
            appState.cvUploading = false;
            if (promptDiv) promptDiv.style.display = "block";
            if (progressContainer) progressContainer.style.display = "none";
            if (progressBar) progressBar.style.width = "0%";
            showToast("Upload aborted.", "warning");
            reject(new Error("Upload aborted"));
        });

        xhr.send(formData);
    });
}

// ----------------------------------------------------
// Job Board Searching
// ----------------------------------------------------
searchBtn.addEventListener('click', triggerJobSearch);

async function triggerJobSearch() {
    // Prevent concurrent searches
    if (appState.isSearching) return;

    if (appState.isGuest && localStorage.getItem("jobseeker_guest_search_done") === "true") {
        showToast("Free Scan Limit Reached: Please sign in or register to search again.", "danger");
        appState.token = null;
        checkAuth();
        return;
    }

    appState.isSearching = true;
    searchBtn.disabled = true;
    searchBtn.style.opacity = "0.6";
    searchBtn.style.pointerEvents = "none";

    jobsContainer.innerHTML = `
        <div style="text-align: center; padding: 3rem 0;">
            <i class="fa-solid fa-spinner fa-spin" style="font-size: 2.5rem; color: var(--primary); margin-bottom: 1rem;"></i>
            <p>Searching job listings and computing ATS scores...</p>
        </div>
    `;
    
    // Prepare query payload
    const query = {
        title: searchTitleInput.value || null,
        location: searchLocationInput.value || null,
        work_type: searchWorkStyleSelect.value,
        commitment: searchCommitmentSelect.value,
        platform: searchPlatformSelect.value,
        keywords: null,
        cv_text: appState.currentCV ? appState.currentCV.raw_text : null
    };

    // Standard fetch
    try {
        const response = await authFetch("/api/search-jobs", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(query)
        });
        
        if (!response.ok) throw new Error("Search failed");
        const jobs = await response.json();
        
        // If we have a CV, let's verify if server pre-calculated the score. If not, fallback to local fetch.
        if (appState.currentCV) {
            for (let job of jobs) {
                if (job.ats_score === undefined || job.ats_score === null) {
                    // Fetch dynamic score only as a fallback
                    const analysisRes = await authFetch("/api/analyze-ats", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            cv_text: appState.currentCV.raw_text,
                            job_description: job.description
                        })
                    });
                    if (analysisRes.ok) {
                        const analysis = await analysisRes.json();
                        job.ats_score = analysis.score;
                        job.analysis = analysis; // cache detailed analysis
                    }
                }
            }
            // Sort by ATS score (highest first)
            jobs.sort((a, b) => (b.ats_score || 0) - (a.ats_score || 0));
        }
        
        appState.jobs = jobs;
        renderJobs(jobs);
        
        // Update stats
        appState.stats.matches = jobs.length;
        document.getElementById('stat-matches').textContent = jobs.length;
        
        if (appState.currentCV && jobs.length > 0) {
            const avg = Math.round(jobs.reduce((acc, j) => acc + (j.ats_score || 0), 0) / jobs.length);
            appState.stats.ats = avg;
            document.getElementById('stat-ats').textContent = `${avg}%`;
        }
        
        if (appState.isGuest) {
            localStorage.setItem("jobseeker_guest_search_done", "true");
            const guestBadge = document.getElementById("guest-mode-badge");
            if (guestBadge) {
                guestBadge.innerHTML = `<i class="fa-solid fa-lock" style="color: var(--danger); margin-right: 0.35rem;"></i> Free Scan Used - Login Required`;
                guestBadge.style.borderColor = "rgba(244, 63, 94, 0.3)";
                guestBadge.style.background = "rgba(244, 63, 94, 0.15)";
                guestBadge.style.color = "var(--danger)";
            }
            showToast("First free job search completed! Register or log in to search again or auto-apply.", "success");
        }
        
    } catch (err) {
        jobsContainer.innerHTML = `
            <div style="text-align: center; padding: 3rem 0; color: var(--text-secondary);">
                <i class="fa-solid fa-triangle-exclamation" style="font-size: 2rem; margin-bottom: 1rem; color: var(--danger);"></i>
                <p>Search failed. Please try again.</p>
            </div>
        `;
        showToast("Failed to retrieve jobs. Please check network connection.", "danger");
    } finally {
        appState.isSearching = false;
        searchBtn.disabled = false;
        searchBtn.style.opacity = "1";
        searchBtn.style.pointerEvents = "auto";
    }
}

function renderJobs(jobs) {
    if (jobs.length === 0) {
        jobsContainer.innerHTML = `
            <div style="text-align: center; padding: 3rem 0; color: var(--text-secondary);">
                <i class="fa-solid fa-folder-open" style="font-size: 2rem; margin-bottom: 1rem; opacity: 0.5;"></i>
                <p>No matching jobs found. Try adjusting filters.</p>
            </div>
        `;
        return;
    }
    
    jobsContainer.innerHTML = "";
    jobs.forEach(job => {
        const jobCard = document.createElement("div");
        jobCard.className = "job-card";
        jobCard.addEventListener('click', () => openSidePanel(job));
        
        // Determine ATS pill styling
        let scoreHTML = "";
        if (job.ats_score !== undefined) {
            let ratingClass = "low";
            if (job.ats_score >= 75) ratingClass = "high";
            else if (job.ats_score >= 40) ratingClass = "med";
            
            scoreHTML = `
                <div class="score-pill ${ratingClass}">
                    ${job.ats_score}% Match
                </div>
            `;
        }
        
        jobCard.innerHTML = `
            <div class="job-card-details">
                <div class="job-card-title">${escapeHtml(job.title)}</div>
                <div style="font-weight: 500; font-size: 0.85rem; color: #fff;">${escapeHtml(job.company)}</div>
                <div class="job-card-meta">
                    <span><i class="fa-solid fa-location-dot"></i> ${escapeHtml(job.location)}</span>
                    <span><i class="fa-solid fa-clock"></i> ${escapeHtml(job.posted_date)}</span>
                </div>
                <div class="job-card-badges">
                    <span class="badge ${(job.platform || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')}">${escapeHtml(job.platform)}</span>
                    <span class="badge worktype">${escapeHtml(job.work_type)}</span>
                    <span class="badge worktype">${escapeHtml(job.commitment)}</span>
                    ${job.easy_apply ? '<span class="badge" style="background: rgba(16,185,129,0.15); color: #10b981;"><i class="fa-solid fa-bolt"></i> Auto Apply</span>' : ''}
                </div>
            </div>
            ${scoreHTML}
        `;
        
        jobsContainer.appendChild(jobCard);
    });
}

// ----------------------------------------------------
// Side Detail Panel & ATS Check
// ----------------------------------------------------
async function openSidePanel(job) {
    appState.selectedJob = job;
    
    panelJobTitle.textContent = job.title;
    panelJobCompany.textContent = `${job.company} | ${job.location}`;
    panelJobDescription.innerHTML = sanitizeHtml(job.description);
    
    // Hide auto apply progress logs by default
    autoApplyBox.style.display = "none";
    autoApplySteps.innerHTML = "";
    
    if (appState.currentCV) {
        // If analysis is cached, render it. Otherwise compute it.
        let analysis = job.analysis;
        if (!analysis) {
            try {
                const response = await authFetch("/api/analyze-ats", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        cv_text: appState.currentCV.raw_text,
                        job_description: job.description
                    })
                });
                analysis = await response.json();
                job.analysis = analysis;
                job.ats_score = analysis.score;
            } catch (e) {
                console.error(e);
            }
        }
        
        if (analysis) {
            renderAtsAnalysis(analysis);
        }
    } else {
        // No CV uploaded yet
        panelAtsScore.textContent = "--%";
        setProgress(0);
        panelAtsSummary.textContent = "Upload your CV to check ATS alignment.";
        panelMatchedSkills.innerHTML = `<span style="color: var(--text-secondary); font-size: 0.8rem;">No CV parsed</span>`;
        panelMissingSkills.innerHTML = `<span style="color: var(--text-secondary); font-size: 0.8rem;">No CV parsed</span>`;
        panelRecommendations.innerHTML = `<li>Upload your CV in the manager to unlock automatic keyword alignment and recommendation tips.</li>`;
    }
    
    // Generate Action Buttons
    renderActionButtons(job);
    
    atsSidePanel.classList.add('open');
}

function closeSidePanel() {
    atsSidePanel.classList.remove('open');
}

closePanelBtn.addEventListener('click', closeSidePanel);

function setProgress(percent) {
    const offset = CIRCLE_CIRCUMFERENCE - (percent / 100) * CIRCLE_CIRCUMFERENCE;
    panelProgressCircle.style.strokeDashoffset = offset;
    
    // Stroke Color depending on score
    if (percent >= 75) {
        panelProgressCircle.style.stroke = "var(--success)";
    } else if (percent >= 40) {
        panelProgressCircle.style.stroke = "var(--warning)";
    } else {
        panelProgressCircle.style.stroke = "var(--danger)";
    }
}

function renderAtsAnalysis(analysis) {
    panelAtsScore.textContent = `${analysis.score}%`;
    setProgress(analysis.score);
    
    // Summary line
    if (analysis.score >= 75) {
        panelAtsSummary.textContent = "Highly aligned! Excellent match for your background.";
    } else if (analysis.score >= 40) {
        panelAtsSummary.textContent = "Moderate alignment. Suggest tweaking your CV keywords.";
    } else {
        panelAtsSummary.textContent = "Low keyword density. CV tailoring recommended.";
    }
    
    // Matched skills
    panelMatchedSkills.innerHTML = "";
    if (analysis.matched_skills.length === 0) {
        panelMatchedSkills.innerHTML = `<span style="color: var(--text-secondary); font-size: 0.75rem;">None found</span>`;
    } else {
        analysis.matched_skills.forEach(skill => {
            const span = document.createElement("span");
            span.className = "skill-pill match";
            span.textContent = skill;
            panelMatchedSkills.appendChild(span);
        });
    }
    
    // Missing skills
    panelMissingSkills.innerHTML = "";
    if (analysis.missing_skills.length === 0) {
        panelMissingSkills.innerHTML = `<span style="color: var(--text-secondary); font-size: 0.75rem;">None! Clear Match</span>`;
    } else {
        analysis.missing_skills.forEach(skill => {
            const span = document.createElement("span");
            span.className = "skill-pill miss";
            span.textContent = skill;
            panelMissingSkills.appendChild(span);
        });
    }
    
    // Recommendations
    panelRecommendations.innerHTML = "";
    analysis.recommendations.forEach(rec => {
        const li = document.createElement("li");
        li.textContent = rec;
        panelRecommendations.appendChild(li);
    });
}

function renderActionButtons(job) {
    panelActionButtons.innerHTML = "";
    panelActionButtons.style.display = "flex";
    panelActionButtons.style.flexDirection = "column";
    panelActionButtons.style.gap = "0.75rem";
    panelActionButtons.style.width = "100%";

    // Get platform-specific icon class
    const getPlatformIcon = (platform) => {
        const p = platform.toLowerCase();
        if (p.includes("linkedin")) return "fa-brands fa-linkedin";
        if (p.includes("google")) return "fa-brands fa-google";
        if (p.includes("upwork")) return "fa-brands fa-upwork";
        if (p.includes("fiverr")) return "fa-brands fa-fiverr";
        return "fa-solid fa-arrow-up-right-from-square";
    };
    
    const iconClass = getPlatformIcon(job.platform);
    const actionUrl = getJobActionUrl(job);

    // Create the "View on Platform" button (used as full-width secondary if Auto Apply is available, or as fallback)
    const viewPlatformBtn = document.createElement("a");
    viewPlatformBtn.className = "btn-secondary";
    viewPlatformBtn.style.display = "flex";
    viewPlatformBtn.style.alignItems = "center";
    viewPlatformBtn.style.justifyContent = "center";
    viewPlatformBtn.style.gap = "0.5rem";
    viewPlatformBtn.style.width = "100%";
    viewPlatformBtn.style.textDecoration = "none";
    viewPlatformBtn.href = actionUrl;
    viewPlatformBtn.target = "_blank";
    viewPlatformBtn.innerHTML = `<i class="${iconClass}"></i> View on ${job.platform}`;
    viewPlatformBtn.addEventListener('click', () => {
        showToast(`Opening original job listing on ${job.platform}.`, "info");
    });

    if (!appState.currentCV) {
        const uploadBtn = document.createElement("button");
        uploadBtn.className = "btn-primary";
        uploadBtn.style.width = "100%";
        uploadBtn.innerHTML = `<i class="fa-solid fa-file-arrow-up"></i> Upload CV to Apply`;
        uploadBtn.addEventListener('click', () => {
            closeSidePanel();
            document.querySelector('[data-target="section-dashboard"]').click();
            document.getElementById('cv-file-input').click();
        });
        panelActionButtons.appendChild(uploadBtn);
        panelActionButtons.appendChild(viewPlatformBtn);
        return;
    }
    
    if (job.easy_apply) {
        const row1 = document.createElement("div");
        row1.style.display = "flex";
        row1.style.gap = "0.75rem";
        row1.style.width = "100%";

        const applyBtn = document.createElement("button");
        applyBtn.className = "btn-primary";
        applyBtn.style.flex = "1";
        applyBtn.innerHTML = `<i class="fa-solid fa-bolt"></i> Auto Apply`;
        applyBtn.addEventListener('click', () => triggerAutoApply(job));
        row1.appendChild(applyBtn);

        const tailorBtn = document.createElement("button");
        tailorBtn.className = "btn-secondary";
        tailorBtn.style.flex = "1";
        tailorBtn.style.display = "flex";
        tailorBtn.style.alignItems = "center";
        tailorBtn.style.justifyContent = "center";
        tailorBtn.style.gap = "0.5rem";
        tailorBtn.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> Tailor Resume`;
        tailorBtn.addEventListener('click', () => openCVOptimizer(job));
        row1.appendChild(tailorBtn);

        panelActionButtons.appendChild(row1);
        panelActionButtons.appendChild(viewPlatformBtn);
    } else {
        const row1 = document.createElement("div");
        row1.style.display = "flex";
        row1.style.gap = "0.75rem";
        row1.style.width = "100%";

        const primaryViewBtn = document.createElement("a");
        primaryViewBtn.className = "btn-primary";
        primaryViewBtn.style.flex = "1";
        primaryViewBtn.style.textDecoration = "none";
        primaryViewBtn.style.display = "flex";
        primaryViewBtn.style.alignItems = "center";
        primaryViewBtn.style.justifyContent = "center";
        primaryViewBtn.style.gap = "0.5rem";
        primaryViewBtn.href = actionUrl;
        primaryViewBtn.target = "_blank";
        primaryViewBtn.innerHTML = `<i class="${iconClass}"></i> View on ${job.platform}`;
        primaryViewBtn.addEventListener('click', () => {
            showToast(`Opening original job listing on ${job.platform}. Tailor CV recommended!`, "info");
        });
        row1.appendChild(primaryViewBtn);

        const tailorBtn = document.createElement("button");
        tailorBtn.className = "btn-secondary";
        tailorBtn.style.flex = "1";
        tailorBtn.style.display = "flex";
        tailorBtn.style.alignItems = "center";
        tailorBtn.style.justifyContent = "center";
        tailorBtn.style.gap = "0.5rem";
        tailorBtn.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> Tailor Resume`;
        tailorBtn.addEventListener('click', () => openCVOptimizer(job));
        row1.appendChild(tailorBtn);

        panelActionButtons.appendChild(row1);
    }
}

// ----------------------------------------------------
// Auto-Apply Flow Automation
// ----------------------------------------------------
async function triggerAutoApply(job) {
    // Prevent concurrent applications
    if (appState.isApplying) return;

    if (appState.isGuest) {
        showToast("Access Locked: Register or log in to auto-apply to jobs.", "warning");
        appState.token = null;
        checkAuth();
        return;
    }
    
    appState.isApplying = true;
    
    autoApplyBox.style.display = "flex";
    autoApplySteps.innerHTML = "";
    
    const steps = [
        "Reading CV text & parsing contacts...",
        "Identifying job matching parameters...",
        "Generating application payload fields...",
        "Simulating OAuth & application forms upload...",
        "Uploading tailored PDF resume to portal...",
        "Reviewing and answering mandatory employer screening questions..."
    ];
    
    for (let step of steps) {
        addLogStep(step, "loading");
        await new Promise(r => setTimeout(r, 600));
        // Update previous log to completed
        const logs = autoApplySteps.querySelectorAll('.progress-log-step');
        if (logs.length > 0) {
            logs[logs.length - 1].className = "progress-log-step done";
        }
    }
    
    // Perform Actual Backend Apply request
    addLogStep("Submitting final application payload to FastAPI applier...", "loading");
    
    try {
        const response = await authFetch("/api/apply", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                job_id: job.id,
                cv_text: appState.currentCV.raw_text,
                full_name: appState.profile.fullname,
                email: appState.profile.email,
                phone: appState.profile.phone,
                cover_letter: `Applying for ${job.title} at ${job.company}.`
            })
        });
        
        const logs = autoApplySteps.querySelectorAll('.progress-log-step');
        if (logs.length > 0) logs[logs.length - 1].className = "progress-log-step done";
        
        if (!response.ok) throw new Error("API apply error");
        
        const result = await response.json();
        
        if (result.success) {
            addLogStep(`SUCCESS: Application submitted. Reference status: ${result.status}`, "done");
            appState.stats.applied++;
            document.getElementById('stat-applied').textContent = appState.stats.applied;
            showToast(`Auto-applied to ${job.company}!`, "success");
        } else {
            addLogStep(`MANUAL SUBMISSION REQUIRED: ${result.message}`, "done");
            showToast("Application requires manual steps. Redirecting to link.", "warning");
            setTimeout(() => {
                window.open(result.apply_url || getJobActionUrl(job), "_blank");
            }, 1500);
        }
        
    } catch (e) {
        console.error(e);
        addLogStep("ERROR: Auto-apply session failed. Please submit manually.", "done");
        showToast("Auto-apply system error. Try manual apply instead.", "danger");
    } finally {
        appState.isApplying = false;
    }
}

function addLogStep(text, status) {
    const stepDiv = document.createElement("div");
    stepDiv.className = `progress-log-step ${status}`;
    stepDiv.textContent = text;
    autoApplySteps.appendChild(stepDiv);
    autoApplySteps.scrollTop = autoApplySteps.scrollHeight;
}

// ----------------------------------------------------
// CV Optimizer & Tailoring API
// ----------------------------------------------------
async function triggerCVTailoring(job) {
    // Prevent concurrent tailoring operations
    if (appState.isTailoring) return;

    if (appState.isGuest) {
        showToast("Access Locked: Register or log in to tailor your CV.", "warning");
        appState.token = null;
        checkAuth();
        return;
    }
    if (!appState.currentCV) {
        showToast("Please upload your CV on the dashboard first.", "warning");
        optOriginalText.value = "";
        optTailoredText.value = "Upload a CV on the dashboard first to enable tailoring...";
        optDownloadBtn.removeAttribute("href");
        optDownloadBtn.style.pointerEvents = "none";
        optDownloadBtn.style.opacity = "0.5";
        return;
    }
    
    appState.isTailoring = true;
    
    optJobTitle.textContent = `Tailoring CV: ${job.title}`;
    optJobMeta.textContent = `${job.company} | ${job.location} | Current ATS Match Score: ${job.ats_score || '0'}%`;
    
    optOriginalText.value = appState.currentCV.raw_text;
    optTailoredText.value = "⏳ Tailoring resume, updating headers, injecting key missing skills & saving professional PDF template...";
    optDownloadBtn.removeAttribute("href");
    optDownloadBtn.style.pointerEvents = "none";
    optDownloadBtn.style.opacity = "0.5";
    
    const payload = {
        cv_text: appState.currentCV.raw_text,
        job_description: job.description,
        job_title: job.title,
        company_name: job.company,
        missing_skills: job.analysis ? job.analysis.missing_skills : []
    };
    
    try {
        const response = await authFetch("/api/tailor-cv", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        
        
        if (!response.ok) {
            const errText = await response.text();
            throw new Error("Tailoring request failed");
        }
        
        const data = await response.json();
        optTailoredText.value = data.tailored_text;
        
        // Enable PDF download link
        optDownloadBtn.href = data.download_url;
        optDownloadBtn.style.pointerEvents = "auto";
        optDownloadBtn.style.opacity = "1";
        
        appState.stats.tailored++;
        document.getElementById('stat-tailored').textContent = appState.stats.tailored;
        
        showToast("Tailored CV generated successfully!", "success");
        
    } catch (e) {
        optTailoredText.value = "Failed to customize CV automatically. Please modify the keywords in the editor manually.";
        showToast("Failed to automate CV tailor rewrite.", "danger");
    } finally {
        appState.isTailoring = false;
    }
}

async function openCVOptimizer(job) {
    if (appState.isGuest) {
        showToast("Access Locked: Register or log in to tailor your CV.", "warning");
        appState.token = null;
        checkAuth();
        return;
    }
    
    closeSidePanel();
    
    appState.selectedJob = job;
    
    // Switch navigation tabs to Optimizer
    document.querySelector('[data-target="section-optimizer"]').click();
    
    // Trigger tailoring immediately
    await triggerCVTailoring(job);
}

// ----------------------------------------------------
// Settings Form Control
// ----------------------------------------------------
saveSettingsBtn.addEventListener('click', async () => {
    appState.profile.fullname = settingsFullname.value;
    appState.profile.email = settingsEmail.value;
    appState.profile.phone = settingsPhone.value;
    
    document.querySelector('.page-title p').textContent = appState.profile.fullname;
    
    // Attempt to persist to backend
    if (!appState.isGuest && appState.token) {
        try {
            await authFetch('/api/update-profile', {
                method: 'POST',
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(appState.profile)
            });
        } catch(e) { console.error("Profile update failed", e); }
    }
    
    const initials = safeInitials(settingsFullname.value);
    avatarLetters.textContent = initials;
    
    showToast("Settings saved successfully!", "success");
});

// ----------------------------------------------------
// Toast Notification Utility
// ----------------------------------------------------
function showToast(message, type = "info") {
    toastMessage.textContent = message;
    
    // Reset classes
    toastNotification.className = "toast";
    toastIcon.className = "fa-solid";
    
    if (type === "success") {
        toastNotification.classList.add("show", "success");
        toastIcon.classList.add("fa-circle-check");
        toastIcon.style.color = "var(--success)";
    } else if (type === "warning") {
        toastNotification.classList.add("show", "warning");
        toastIcon.classList.add("fa-triangle-exclamation");
        toastIcon.style.color = "var(--warning)";
    } else if (type === "danger") {
        toastNotification.classList.add("show", "danger");
        toastIcon.classList.add("fa-circle-xmark");
        toastIcon.style.color = "var(--danger)";
    } else {
        toastNotification.classList.add("show");
        toastIcon.classList.add("fa-circle-info");
        toastIcon.style.color = "var(--primary)";
    }
    
    // Hide toast after 4 seconds
    setTimeout(() => {
        toastNotification.classList.remove("show");
    }, 4000);
}

// ----------------------------------------------------
// UI Custom Formatter Utilities
// ----------------------------------------------------
function formatExperienceHTML(experienceLines) {
    if (!experienceLines || experienceLines.length === 0) {
        return `<span style="color: var(--text-secondary); font-size: 0.82rem;">No experience details found.</span>`;
    }
    
    let html = "";
    experienceLines.forEach(line => {
        const trimmed = line.trim();
        if (!trimmed) return;
        
        // Match Job Role & Company headers containing "|"
        if (trimmed.includes('|')) {
            const parts = trimmed.split('|');
            const role = parts[0].trim();
            const company = parts[1].trim();
            html += `<div class="job-role-header" style="font-weight: 600; margin-top: 1rem; color: var(--text-primary); font-family: var(--font-outfit); font-size: 0.95rem;">
                        ${escapeHtml(role)} <span style="font-weight: 500; color: var(--secondary);">@ ${escapeHtml(company)}</span>
                     </div>`;
        } 
        // Match Date Ranges: contains months, years, or "Present"
        else if (/present|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|spring|summer|fall|winter|\b(19|20)\d{2}\b/i.test(trimmed.toLowerCase()) && trimmed.length < 50) {
            html += `<div class="job-role-date" style="font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 0.5rem; font-style: italic; display: flex; align-items: center; gap: 0.25rem;">
                        <i class="fa-regular fa-calendar-days" style="opacity: 0.75;"></i> ${escapeHtml(trimmed)}
                     </div>`;
        } 
        // Match standard descriptive bullet points
        else {
            const cleanText = trimmed.replace(/^[•\*\-\s\d\.]+\s*/, '');
            html += `<div class="job-role-bullet" style="margin-left: 0.4rem; padding-left: 0.6rem; border-left: 1.5px solid var(--primary-glow); margin-bottom: 0.35rem; font-size: 0.82rem; color: var(--text-secondary); line-height: 1.45;">
                        ${escapeHtml(cleanText)}
                     </div>`;
        }
    });
    
    return html;
}

function formatEducationHTML(educationLines) {
    if (!educationLines || educationLines.length === 0) {
        return `<span style="color: var(--text-secondary); font-size: 0.82rem;">No education details found.</span>`;
    }
    
    let html = "";
    educationLines.forEach(line => {
        const trimmed = line.trim();
        if (!trimmed) return;
        
        if (trimmed.includes(',')) {
            const parts = trimmed.split(',');
            const degree = parts[0].trim();
            const university = parts.slice(1).map(p => p.trim()).join(', ');
            html += `<div class="edu-item" style="margin-top: 0.6rem; margin-bottom: 0.6rem;">
                        <div style="font-weight: 600; color: var(--text-primary); font-size: 0.9rem;">${escapeHtml(degree)}</div>
                        <div style="font-size: 0.8rem; color: var(--text-secondary); font-style: italic; margin-top: 0.15rem;">${escapeHtml(university)}</div>
                     </div>`;
        } else {
            html += `<div class="edu-item" style="margin-top: 0.5rem; margin-bottom: 0.5rem; font-size: 0.85rem; color: var(--text-secondary); line-height: 1.4;">
                        ${escapeHtml(trimmed)}
                     </div>`;
        }
    });
    
    return html;
}

// ----------------------------------------------------
// Custom Dropdown Initialization
// ----------------------------------------------------
function initCustomDropdowns() {
    // Only target select elements that haven't been wrapped yet
    const selectElements = document.querySelectorAll('select.form-control:not(.wrapped):not(.native-select)');
    
    selectElements.forEach(select => {
        select.classList.add('wrapped');
        
        // Create wrapper
        const wrapper = document.createElement('div');
        wrapper.className = 'custom-select-wrapper';
        wrapper.id = `wrapper-${select.id}`;
        
        // Hide original select (visually)
        select.style.display = 'none';
        
        // Insert wrapper before select
        select.parentNode.insertBefore(wrapper, select);
        wrapper.appendChild(select);
        
        // Create trigger
        const trigger = document.createElement('div');
        trigger.className = 'custom-select-trigger';
        
        const textSpan = document.createElement('span');
        textSpan.className = 'custom-select-text';
        // Get initial selected option text
        const selectedOption = select.options[select.selectedIndex];
        textSpan.textContent = selectedOption ? selectedOption.textContent : '';
        
        const arrowIcon = document.createElement('i');
        arrowIcon.className = 'fa-solid fa-chevron-down custom-select-arrow';
        
        trigger.appendChild(textSpan);
        trigger.appendChild(arrowIcon);
        wrapper.appendChild(trigger);
        
        // Create options container
        const optionsContainer = document.createElement('div');
        optionsContainer.className = 'custom-select-options';
        
        // Populate options (with support for optgroup)
        let globalIndex = 0;
        const renderOption = (option, index) => {
            const optDiv = document.createElement('div');
            optDiv.className = 'custom-select-option';
            if (index === select.selectedIndex) {
                optDiv.classList.add('selected');
            }
            optDiv.dataset.value = option.value;
            optDiv.textContent = option.textContent;
            
            optDiv.addEventListener('click', (e) => {
                e.stopPropagation();
                // Update selected option in select element
                select.value = option.value;
                // Dispatch change event
                select.dispatchEvent(new Event('change'));
                
                // Update text & classes
                textSpan.textContent = option.textContent;
                optionsContainer.querySelectorAll('.custom-select-option').forEach(o => o.classList.remove('selected'));
                optDiv.classList.add('selected');
                
                // Close dropdown
                wrapper.classList.remove('open');
            });
            return optDiv;
        };

        Array.from(select.children).forEach((child) => {
            if (child.tagName.toLowerCase() === 'optgroup') {
                const groupHeader = document.createElement('div');
                groupHeader.className = 'custom-select-group-header';
                groupHeader.textContent = child.label;
                optionsContainer.appendChild(groupHeader);
                
                Array.from(child.children).forEach((option) => {
                    const optIndex = globalIndex++;
                    const optDiv = renderOption(option, optIndex);
                    optDiv.classList.add('grouped');
                    optionsContainer.appendChild(optDiv);
                });
            } else if (child.tagName.toLowerCase() === 'option') {
                const optIndex = globalIndex++;
                const optDiv = renderOption(child, optIndex);
                optionsContainer.appendChild(optDiv);
            }
        });
        
        wrapper.appendChild(optionsContainer);
        
        // Toggle dropdown on click
        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            
            // Close other dropdowns
            document.querySelectorAll('.custom-select-wrapper').forEach(w => {
                if (w !== wrapper) w.classList.remove('open');
            });
            
            wrapper.classList.toggle('open');
        });

        // Listen for changes on the original select (e.g. if updated programmatically)
        select.addEventListener('change', () => {
            const index = select.selectedIndex;
            const option = select.options[index];
            if (option) {
                textSpan.textContent = option.textContent;
                optionsContainer.querySelectorAll('.custom-select-option').forEach((o, i) => {
                    if (i === index) {
                        o.classList.add('selected');
                    } else {
                        o.classList.remove('selected');
                    }
                });
            }
        });
    });
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', () => {
        document.querySelectorAll('.custom-select-wrapper').forEach(w => {
            w.classList.remove('open');
        });
    });
}

// Initialize on script load
let dropdownsInitialized = false;
function safeInitDropdowns() {
    if (dropdownsInitialized) return;
    dropdownsInitialized = true;
    initCustomDropdowns();
}
document.addEventListener('DOMContentLoaded', safeInitDropdowns);
if (document.readyState === 'interactive' || document.readyState === 'complete') {
    safeInitDropdowns();
}

// ----------------------------------------------------
// Authentication Flow & Persistent Profile Sync
// ----------------------------------------------------
const authScreen = document.getElementById("auth-screen");
const appContent = document.getElementById("app-content");
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const loginFormWrapper = document.getElementById("login-form-wrapper");
const registerFormWrapper = document.getElementById("register-form-wrapper");

const showRegisterBtn = document.getElementById("show-register-btn");
const showLoginBtn = document.getElementById("show-login-btn");
const logoutBtn = document.getElementById("nav-logout-btn");

if (showRegisterBtn) {
    showRegisterBtn.addEventListener("click", (e) => {
        e.preventDefault();
        loginFormWrapper.style.display = "none";
        registerFormWrapper.style.display = "block";
    });
}

if (showLoginBtn) {
    showLoginBtn.addEventListener("click", (e) => {
        e.preventDefault();
        registerFormWrapper.style.display = "none";
        loginFormWrapper.style.display = "block";
    });
}

if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const username = document.getElementById("login-username").value;
        const password = document.getElementById("login-password").value;
        const errorDiv = document.getElementById("login-error");
        errorDiv.style.display = "none";

        try {
            const res = await fetch("/api/auth/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password })
            });

            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || "Invalid credentials");
            }

            const data = await res.json();
            appState.token = data.token;
            localStorage.setItem("jobseeker_token", data.token);
            showToast("Successfully logged in!", "success");
            await initAppAfterAuth();
        } catch (err) {
            errorDiv.textContent = err.message;
            errorDiv.style.display = "block";
        }
    });
}

if (registerForm) {
    registerForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const username = document.getElementById("register-username").value;
        const email = document.getElementById("register-email").value;
        const password = document.getElementById("register-password").value;
        const errorDiv = document.getElementById("register-error");
        errorDiv.style.display = "none";

        try {
            const res = await fetch("/api/auth/register", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, email, password })
            });

            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || "Registration failed");
            }

            const data = await res.json();
            appState.token = data.token;
            localStorage.setItem("jobseeker_token", data.token);
            showToast("Account created successfully!", "success");
            await initAppAfterAuth();
        } catch (err) {
            errorDiv.textContent = err.message;
            errorDiv.style.display = "block";
        }
    });
}

if (logoutBtn) {
    logoutBtn.addEventListener("click", async (e) => {
        e.preventDefault();
        try {
            await authFetch("/api/auth/logout", { method: "POST" });
        } catch (err) {
            console.error("Logout request error", err);
        }
        appState.token = null;
        appState.currentCV = null;
        localStorage.removeItem("jobseeker_token");
        
        // Hide profile & reset Dropzone
        cvProfileBox.style.display = "none";
        cvDropzone.style.display = "block";
        
        showToast("Logged out successfully.", "info");
        checkAuth();
    });
}

function checkAuth() {
    const guestNotice = document.getElementById("guest-auth-notice");
    if (guestNotice) guestNotice.style.display = "none";

    if (appState.token) {
        appState.isGuest = false;
        const guestBadge = document.getElementById("guest-mode-badge");
        if (guestBadge) guestBadge.style.display = "none";
        
        // Reset settings navigation state back to unlocked
        const settingsNavItem = document.querySelector('[data-target="section-settings"]');
        if (settingsNavItem) {
            settingsNavItem.style.opacity = "1";
            settingsNavItem.style.cursor = "pointer";
            const aElement = settingsNavItem.querySelector('a');
            if (aElement) {
                aElement.innerHTML = `<i class="fa-solid fa-sliders"></i> Settings`;
            }
        }

        authScreen.style.display = "none";
        appContent.style.display = "flex";
        initAppAfterAuth();
    } else {
        const scanUsed = localStorage.getItem("jobseeker_guest_search_done") === "true";
        if (scanUsed) {
            appContent.style.display = "none";
            authScreen.style.display = "flex";
            if (guestNotice) guestNotice.style.display = "block";
        } else {
            appState.isGuest = true;
            authScreen.style.display = "none";
            appContent.style.display = "flex";
            initGuestMode();
        }
    }
}

function initGuestMode() {
    // Show guest badge
    const guestBadge = document.getElementById("guest-mode-badge");
    if (guestBadge) {
        guestBadge.style.display = "block";
        guestBadge.innerHTML = `<i class="fa-solid fa-gift" style="color: var(--secondary); margin-right: 0.35rem;"></i> Guest Mode: 1 Free Scan Remaining`;
        guestBadge.style.borderColor = "rgba(99, 102, 241, 0.3)";
        guestBadge.style.background = "rgba(99, 102, 241, 0.15)";
        guestBadge.style.color = "var(--primary)";
    }
    
    // Set default names for guest UI
    profileDisplayName.textContent = "Guest Candidate";
    avatarLetters.textContent = "GU";
    
    // Sync default profile values
    appState.profile.fullname = "Guest Candidate";
    appState.profile.email = "guest@seeker.com";
    appState.profile.phone = "";
    
    settingsFullname.value = appState.profile.fullname;
    settingsEmail.value = appState.profile.email;
    settingsPhone.value = appState.profile.phone;
    
    // Lock settings sidebar visually
    const settingsNavItem = document.querySelector('[data-target="section-settings"]');
    if (settingsNavItem) {
        settingsNavItem.style.opacity = "0.5";
        settingsNavItem.style.cursor = "not-allowed";
        const aElement = settingsNavItem.querySelector('a');
        if (aElement) {
            aElement.innerHTML = `<i class="fa-solid fa-lock" style="font-size: 0.85rem; margin-right: 0.2rem;"></i> Settings (Locked)`;
        }
    }
    
    // Reset dropzone
    cvDropzone.style.display = "block";
    cvProfileBox.style.display = "none";
    
    // Clear out memory cv & job stats
    appState.currentCV = null;
    appState.jobs = [];
    appState.stats.matches = 0;
    appState.stats.ats = 0;
    appState.stats.applied = 0;
    appState.stats.tailored = 0;
    
    document.getElementById('stat-matches').textContent = "0";
    document.getElementById('stat-ats').textContent = "--%";
    document.getElementById('stat-applied').textContent = "0";
    document.getElementById('stat-tailored').textContent = "0";
    
    // Auto-search default jobs
    triggerJobSearch();
}

async function initAppAfterAuth() {
    try {
        const res = await authFetch("/api/auth/me");
        if (!res.ok) {
            throw new Error("Session expired");
        }
        const user = await res.json();
        
        // Sync display details
        appState.profile.fullname = user.fullname || user.username;
        appState.profile.email = user.profile_email || user.email;
        appState.profile.phone = user.phone || "";
        
        // Populate inputs
        settingsFullname.value = appState.profile.fullname;
        settingsEmail.value = appState.profile.email;
        settingsPhone.value = appState.profile.phone;
        
        profileDisplayName.textContent = appState.profile.fullname;
        const initials = safeInitials(appState.profile.fullname);
        avatarLetters.textContent = initials;
        
        // Load CV if user has already uploaded one
        if (user.cv_text) {
            if (user.parsed_cv) {
                appState.currentCV = user.parsed_cv;
                displayCVDetails(user.parsed_cv);
            } else {
                appState.currentCV = {
                    raw_text: user.cv_text,
                    name: user.fullname,
                    email: user.profile_email,
                    phone: user.phone,
                    skills: [],
                    experience: [],
                    education: []
                };
                displayCVDetails(appState.currentCV);
            }
        } else {
            cvProfileBox.style.display = "none";
            cvDropzone.style.display = "block";
        }
        
        // Show dashboard views
        authScreen.style.display = "none";
        appContent.style.display = "flex";
        
        // Search default jobs
        triggerJobSearch();
    } catch (err) {
        console.error(err);
        appState.token = null;
        localStorage.removeItem("jobseeker_token");
        checkAuth();
    }
}

// Trigger initial check
let authChecked = false;
function safeCheckAuth() {
    if (authChecked) return;
    authChecked = true;
    checkAuth();
}
document.addEventListener("DOMContentLoaded", safeCheckAuth);
if (document.readyState === 'interactive' || document.readyState === 'complete') {
    safeCheckAuth();
}

// Mobile Menu Toggle
const mobileMenuToggle = document.getElementById('mobile-menu-toggle');
if (mobileMenuToggle) {
    mobileMenuToggle.addEventListener('click', () => {
        document.querySelector('.sidebar').classList.toggle('open');
    });
}


