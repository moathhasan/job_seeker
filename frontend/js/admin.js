// ============================================================
// Admin Application — v2.0
// Features: User monitoring, Session management,
//           API Settings management, Job Source status
// ============================================================

const adminState = {
    token: localStorage.getItem("jobseeker_admin_token") || null,
    stats: { total_users: 0, logged_in_users: 0, active_users: 0, users: [], sessions: [] },
    settings: {},
    providers: [],
    refreshIntervalId: null
};

// XSS Protection Utility
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

async function adminFetch(url, options = {}) {
    if (!options.headers) options.headers = {};
    if (adminState.token) options.headers["Authorization"] = `Bearer ${adminState.token}`;
    return fetch(url, options);
}

// ── DOM refs ──────────────────────────────────────────────
const adminAuthScreen   = document.getElementById("admin-auth-screen");
const adminAppContent   = document.getElementById("admin-app-content");
const adminLoginForm    = document.getElementById("admin-login-form");
const adminLogoutBtn    = document.getElementById("admin-logout-btn");
const adminNavItems     = document.querySelectorAll('.nav-item');
const adminSections     = document.querySelectorAll('.page-section');
const statTotalUsers    = document.getElementById("admin-stat-total-users");
const statLoggedIn      = document.getElementById("admin-stat-logged-in");
const statActiveUsers   = document.getElementById("admin-stat-active-users");
const usersTableBody    = document.getElementById("admin-users-table-body");
const sessionsTableBody = document.getElementById("admin-sessions-table-body");
const toastEl           = document.getElementById("admin-toast-notification");
const toastIcon         = document.getElementById("admin-toast-icon");
const toastMsg          = document.getElementById("admin-toast-message");

// ── Toast ─────────────────────────────────────────────────
function showAdminToast(message, type = "info") {
    toastMsg.textContent = message;
    toastEl.className = "toast";
    toastIcon.className = "fa-solid";
    const map = {
        success: ["success", "fa-circle-check",      "var(--success)"],
        warning: ["warning", "fa-triangle-exclamation","var(--warning)"],
        danger:  ["danger",  "fa-circle-xmark",       "var(--danger)"],
        info:    ["",        "fa-circle-info",         "var(--primary)"],
    };
    const [cls, ico, clr] = map[type] || map.info;
    if (cls) toastEl.classList.add(cls);
    toastEl.classList.add("show");
    toastIcon.classList.add(ico);
    toastIcon.style.color = clr;
    setTimeout(() => toastEl.classList.remove("show"), 4000);
}

// ── Navigation ────────────────────────────────────────────
const sectionMeta = {
    "section-admin-dashboard": { title: "Admin Dashboard",    sub: "Real-time stats and management of active users." },
    "section-admin-sessions":  { title: "Active Sessions",    sub: "Monitor live tokens and revoke access instantly." },
    "section-api-settings":    { title: "API Settings",       sub: "Configure API keys for job providers — stored securely in MySQL." },
    "section-job-sources":     { title: "Job Source Status",  sub: "Live status of all integrated job providers." },
};

adminNavItems.forEach(item => {
    item.addEventListener('click', () => {
        const targetId = item.getAttribute('data-target');
        if (!targetId) return;
        adminNavItems.forEach(n => n.classList.remove('active'));
        adminSections.forEach(s => s.classList.remove('active'));
        item.classList.add('active');
        document.getElementById(targetId)?.classList.add('active');
        const meta = sectionMeta[targetId] || {};
        document.getElementById('admin-header-title').textContent    = meta.title || "";
        document.getElementById('admin-header-subtitle').textContent = meta.sub   || "";
        // Lazy-load on navigate
        if (targetId === "section-api-settings") loadSettings();
        if (targetId === "section-job-sources")  loadProviderStatus();
        // Close sidebar on mobile after navigation
        const sidebar = document.querySelector('.sidebar');
        if (sidebar && window.innerWidth <= 900) sidebar.classList.remove('open');
    });
});

// ── Admin Mobile Menu Toggle ──────────────────────────────
const adminMobileToggle = document.getElementById("admin-mobile-menu-toggle");
if (adminMobileToggle) {
    adminMobileToggle.addEventListener("click", () => {
        const sidebar = document.querySelector('.sidebar');
        if (sidebar) sidebar.classList.toggle('open');
    });
}

// ── Authentication ────────────────────────────────────────
adminLoginForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const username  = document.getElementById("admin-username").value;
    const password  = document.getElementById("admin-password").value;
    const errorDiv  = document.getElementById("admin-login-error");
    const loginBtn  = document.getElementById("admin-login-btn");
    errorDiv.style.display = "none";
    loginBtn.disabled = true;
    loginBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Authenticating...`;
    try {
        const res  = await fetch("/api/admin/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });
        if (!res.ok) { const d = await res.json(); throw new Error(d.detail || "Access Denied"); }
        const data = await res.json();
        adminState.token = data.token;
        localStorage.setItem("jobseeker_admin_token", data.token);
        showAdminToast("Access granted. Admin session started.", "success");
        checkAdminAuth();
    } catch (err) {
        errorDiv.textContent  = err.message;
        errorDiv.style.display = "block";
    } finally {
        loginBtn.disabled = false;
        loginBtn.innerHTML = `<i class="fa-solid fa-shield-halved"></i> Authenticate`;
    }
});

adminLogoutBtn?.addEventListener("click", (e) => {
    e.preventDefault();
    adminFetch("/api/auth/logout", { method: "POST" }).catch(() => {});
    adminState.token = null;
    localStorage.removeItem("jobseeker_admin_token");
    if (adminState.refreshIntervalId) { clearInterval(adminState.refreshIntervalId); adminState.refreshIntervalId = null; }
    showAdminToast("Admin logged out.", "info");
    checkAdminAuth();
});

function checkAdminAuth() {
    if (adminState.token) {
        adminAuthScreen.style.display  = "none";
        adminAppContent.style.display  = "flex";
        fetchAdminStats();
        if (!adminState.refreshIntervalId)
            adminState.refreshIntervalId = setInterval(fetchAdminStats, 10000);
    } else {
        adminAppContent.style.display  = "none";
        adminAuthScreen.style.display  = "flex";
        if (adminState.refreshIntervalId) { clearInterval(adminState.refreshIntervalId); adminState.refreshIntervalId = null; }
    }
}

// ── Stats & Tables ────────────────────────────────────────
async function fetchAdminStats() {
    try {
        const res = await adminFetch("/api/admin/stats");
        if (!res.ok) { if (res.status === 401) { adminState.token = null; localStorage.removeItem("jobseeker_admin_token"); checkAdminAuth(); return; } throw new Error("Failed to load stats"); }
        adminState.stats = await res.json();
        renderStats();
    } catch (err) {
        showAdminToast("Error: " + err.message, "danger");
    }
}

function renderStats() {
    const { total_users, logged_in_users, active_users, users, sessions } = adminState.stats;
    statTotalUsers.textContent  = total_users;
    statLoggedIn.textContent    = logged_in_users;
    statActiveUsers.textContent = active_users;

    usersTableBody.innerHTML = users.length === 0
        ? `<tr><td colspan="6" style="text-align:center;color:var(--text-secondary);padding:2rem;">No candidates registered yet.</td></tr>`
        : users.map(u => {
            const isActive = u.last_seen && (new Date() - new Date(u.last_seen) < 900000) && u.session_count > 0;
            return `<tr>
                <td>#${escapeHtml(String(u.id))}</td>
                <td style="font-weight:600;"><i class="fa-solid fa-user" style="opacity:0.5;margin-right:0.5rem;"></i>${escapeHtml(u.username)}</td>
                <td>${escapeHtml(u.email)}</td>
                <td>${u.created_at ? new Date(u.created_at).toLocaleString() : "-"}</td>
                <td>${u.last_seen ? new Date(u.last_seen).toLocaleString() : "Never"}</td>
                <td style="display:flex;align-items:center;justify-content:space-between;gap:1rem;">
                    <span>${u.session_count} session(s)</span>
                    <span class="status-badge ${isActive ? "active" : "inactive"}">${isActive ? "Active Now" : "Offline"}</span>
                </td>
            </tr>`;
        }).join("");

    sessionsTableBody.innerHTML = sessions.length === 0
        ? `<tr><td colspan="6" style="text-align:center;color:var(--text-secondary);padding:2rem;">No active sessions.</td></tr>`
        : sessions.map(s => `<tr>
            <td style="font-weight:600;"><i class="fa-solid fa-user-clock" style="opacity:0.5;margin-right:0.5rem;"></i>${escapeHtml(s.username)}</td>
            <td>${escapeHtml(s.email || '')}</td>
            <td><span class="token-display">${escapeHtml((s.token || '').substring(0,12))}...</span></td>
            <td>${s.created_at ? new Date(s.created_at).toLocaleString() : "-"}</td>
            <td>${s.last_activity ? new Date(s.last_activity).toLocaleString() : "-"}</td>
            <td><button class="btn-revoke" data-token="${escapeHtml(s.token)}" data-username="${escapeHtml(s.username)}">
                <i class="fa-solid fa-right-from-bracket"></i> Revoke
            </button></td>
        </tr>`).join("");

    // Event delegation for revoke buttons (replaces inline onclick)
    sessionsTableBody.querySelectorAll('.btn-revoke').forEach(btn => {
        btn.addEventListener('click', () => {
            revokeUserSession(btn.dataset.token, btn.dataset.username);
        });
    });
}

window.revokeUserSession = async function(token, username) {
    if (!confirm(`Force log out ${username}?`)) return;
    try {
        const res = await adminFetch("/api/admin/revoke-session", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token })
        });
        if (!res.ok) throw new Error("Revocation failed");
        showAdminToast(`Session revoked for ${username}.`, "success");
        fetchAdminStats();
    } catch (err) {
        showAdminToast("Failed: " + err.message, "danger");
    }
};

document.getElementById("refresh-users-btn")?.addEventListener("click",    () => { showAdminToast("Refreshing...", "info"); fetchAdminStats(); });
document.getElementById("refresh-sessions-btn")?.addEventListener("click", () => { showAdminToast("Refreshing...", "info"); fetchAdminStats(); });

// ── API Settings ──────────────────────────────────────────
const SETTING_GROUPS = [
    {
        icon: "fa-magnifying-glass-dollar",
        title: "General Job Boards",
        settings: [
            { key: "ADZUNA_APP_ID",   label: "Adzuna App ID",    type: "text",     desc: "Free at developer.adzuna.com" },
            { key: "ADZUNA_APP_KEY",  label: "Adzuna App Key",   type: "password", desc: "Free at developer.adzuna.com" },
            { key: "JOOBLE_API_KEY",  label: "Jooble API Key",   type: "password", desc: "Free at jooble.org/api/about" },
            { key: "JSEARCH_API_KEY", label: "JSearch (RapidAPI) Key", type: "password", desc: "Free tier at rapidapi.com → JSearch" },
        ]
    },
    {
        icon: "fa-cloud",
        title: "Scraping Tools",
        settings: [
            { key: "APIFY_TOKEN",      label: "Apify Token",         type: "password", desc: "Create account at apify.com" },
            { key: "BRIGHTDATA_PROXY", label: "Bright Data Proxy URL", type: "text",   desc: "Format: http://user:pass@host:port (optional)" },
        ]
    },
    {
        icon: "fa-building",
        title: "ATS — Greenhouse Board Tokens",
        settings: [
            { key: "GREENHOUSE_COMPANIES", label: "Company Tokens", type: "textarea", desc: "Comma-separated Greenhouse board tokens (e.g. stripe,airbnb,notion)" },
        ]
    },
    {
        icon: "fa-lever-war-mace",
        title: "ATS — Lever Company Slugs",
        settings: [
            { key: "LEVER_COMPANIES", label: "Company Slugs", type: "textarea", desc: "Comma-separated Lever slugs (e.g. netflix,reddit,box)" },
        ]
    },
    {
        icon: "fa-briefcase",
        title: "ATS — Ashby Board Names",
        settings: [
            { key: "ASHBY_COMPANIES", label: "Board Names", type: "textarea", desc: "Comma-separated Ashby board names (e.g. ashby,retool,ramp)" },
        ]
    },
    {
        icon: "fa-users-gear",
        title: "ATS — SmartRecruiters Company IDs",
        settings: [
            { key: "SMARTRECRUITERS_COMPANIES", label: "Company IDs", type: "textarea", desc: "Comma-separated SmartRecruiters IDs (e.g. spotify,philips,bosch)" },
        ]
    },
];

async function loadSettings() {
    const container = document.getElementById("settings-grid-container");
    container.innerHTML = `<div style="text-align:center;padding:3rem;color:var(--text-secondary);"><i class="fa-solid fa-spinner fa-spin fa-2x"></i></div>`;
    try {
        const res = await adminFetch("/api/admin/settings");
        if (!res.ok) throw new Error("Failed to load settings");
        adminState.settings = await res.json();
        renderSettings();
    } catch (err) {
        container.innerHTML = `<p style="color:var(--danger);">Error: ${err.message}</p>`;
    }
}

function renderSettings() {
    const container = document.getElementById("settings-grid-container");
    container.innerHTML = SETTING_GROUPS.map(group => `
        <div class="settings-group">
            <div class="settings-group-title">
                <i class="fa-solid ${group.icon}"></i> ${group.title}
            </div>
            ${group.settings.map(s => {
                const settingData = adminState.settings[s.key] || {};
                const hasValue = settingData.has_value || false;
                const masked  = settingData.masked_value || "";
                const inputEl = s.type === "textarea"
                    ? `<textarea id="input-${s.key}" placeholder="${hasValue ? 'Current value set (enter new to change)' : 'Enter value...'}">${""}</textarea>`
                    : `<input type="${s.type}" id="input-${s.key}"
                        placeholder="${hasValue ? (masked || 'Value configured') : 'Enter value...'}"
                        value="">`;
                return `
                <div class="setting-row">
                    <label>
                        <span>${s.label}</span>
                        <span class="key-badge">${s.key}</span>
                    </label>
                    <div class="input-wrap">
                        ${inputEl}
                        <button class="btn-save-setting" onclick="saveSetting('${s.key}')">
                            <i class="fa-solid fa-floppy-disk"></i> Save
                        </button>
                    </div>
                    <p class="desc">${s.desc}</p>
                </div>`;
            }).join("")}
        </div>
    `).join("");
}

window.saveSetting = async function(key) {
    const inputEl = document.getElementById(`input-${key}`);
    if (!inputEl) return;
    const value = inputEl.value.trim();
    const btn   = inputEl.closest(".input-wrap")?.querySelector(".btn-save-setting");
    if (btn) { btn.disabled = true; btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i>`; }
    try {
        const res = await adminFetch("/api/admin/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ settings: { [key]: value } })
        });
        if (!res.ok) throw new Error("Save failed");
        showAdminToast(`✓ ${key} saved successfully.`, "success");
        await loadSettings();
    } catch (err) {
        showAdminToast(`Error saving ${key}: ${err.message}`, "danger");
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = `<i class="fa-solid fa-floppy-disk"></i> Save`; }
    }
};

// ── Provider Status ───────────────────────────────────────
async function loadProviderStatus() {
    const grid = document.getElementById("provider-status-grid");
    grid.innerHTML = `<div style="text-align:center;padding:2rem;color:var(--text-secondary);"><i class="fa-solid fa-spinner fa-spin"></i></div>`;
    try {
        const res = await adminFetch("/api/admin/provider-status");
        if (!res.ok) throw new Error("Failed");
        const data = await res.json();
        adminState.providers = data.providers || [];
        renderProviders();
    } catch (err) {
        grid.innerHTML = `<p style="color:var(--danger);">Error: ${err.message}</p>`;
    }
}

function renderProviders() {
    const grid = document.getElementById("provider-status-grid");
    if (!adminState.providers.length) {
        grid.innerHTML = `<p style="color:var(--text-secondary);">No providers found.</p>`;
        return;
    }
    grid.innerHTML = adminState.providers.map(p => {
        const dotClass = p.status;
        const label    = p.status === "active" ? "Active" : p.status === "configured" ? "Configured" : "Needs API Key";
        return `
        <div class="provider-card">
            <div class="provider-dot ${dotClass}"></div>
            <div class="provider-info">
                <div class="name">${p.name}</div>
                <div class="status">${label}${p.requires_key ? ' <i class="fa-solid fa-key" style="font-size:0.65rem;opacity:0.6;"></i>' : ''}</div>
            </div>
        </div>`;
    }).join("");
}

document.getElementById("refresh-providers-btn")?.addEventListener("click", () => {
    showAdminToast("Refreshing provider status...", "info");
    loadProviderStatus();
});

document.getElementById("clear-cache-btn")?.addEventListener("click", async () => {
    if (!confirm("Clear all cached jobs? Next search will fetch fresh real-time data from all providers.")) return;
    try {
        const res = await adminFetch("/api/admin/clear-job-cache", { method: "POST" });
        if (!res.ok) throw new Error("Failed to clear cache");
        const d = await res.json();
        showAdminToast(d.message, "success");
    } catch (err) {
        showAdminToast("Error: " + err.message, "danger");
    }
});

// ── Init ──────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", checkAdminAuth);
if (document.readyState === "interactive" || document.readyState === "complete") checkAdminAuth();
