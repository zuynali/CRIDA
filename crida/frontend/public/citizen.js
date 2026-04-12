// ── Config ────────────────────────────────────────────────────────────────
const API = "http://localhost:5000/api/v1";
let TOKEN      = sessionStorage.getItem("crida_citizen_token") || null;
let CITIZEN_ID = sessionStorage.getItem("crida_citizen_id") ? parseInt(sessionStorage.getItem("crida_citizen_id")) : null;
let CITIZEN    = null;

// ── Toast ─────────────────────────────────────────────────────────────────
function toast(msg, type = "ok") {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  document.getElementById("toast-container").appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

// ── Message box helper ────────────────────────────────────────────────────
function showMsg(id, text, type) {
  const el = document.getElementById(id);
  el.className = `msg ${type} show`;
  el.innerHTML = `<i class="fas fa-${type === 'ok' ? 'check-circle' : type === 'err' ? 'exclamation-circle' : 'info-circle'}"></i> ${text}`;
}

// ── API helper ────────────────────────────────────────────────────────────
async function req(method, path, body = null, asBlob = false) {
  const opts = {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(TOKEN ? { "Authorization": "Bearer " + TOKEN } : {})
    }
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(API + path, opts);
  if (asBlob) {
    if (!res.ok) throw new Error("Request failed: " + res.status);
    return res.blob();
  }
  const text = await res.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch (err) {
    const cleanText = text.replace(/<[^>]*>/g, '').trim();
    data = { error: cleanText ? cleanText.split('\n')[0] : `HTTP ${res.status}` };
  }
  return { ok: res.ok, status: res.status, data };
}

// ── Panel switching ───────────────────────────────────────────────────────
const _loaded = new Set();

function switchPanel(name, btn) {
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-tab").forEach(b => b.classList.remove("active"));
  const targetPanel = document.getElementById("panel-" + name);
  if (targetPanel) targetPanel.classList.add("active");
  if (btn) btn.classList.add("active");

  // Lazy-load once per panel
  if (!_loaded.has(name)) {
    _loaded.add(name);
    if (name === "dashboard")     loadDashboardSummary();
    if (name === "applications")  loadApplications();
    if (name === "documents")     renderDocButtons();
    if (name === "family")        loadFamily();
    if (name === "notifications") loadNotifications();
    if (name === "complaints")    loadMyComplaints();
    if (name === "updates")       loadMyUpdateRequests();
  }
}

// ── LOGIN ─────────────────────────────────────────────────────────────────
async function citizenLogin() {
  const nid = document.getElementById("c-nid").value.trim();
  const cid = parseInt(document.getElementById("c-cid").value);
  const msg = document.getElementById("login-msg");

  msg.className = "msg";
  if (!nid || nid.length !== 13 || !/^\d{13}$/.test(nid)) {
    showMsg("login-msg", "National ID must be exactly 13 digits.", "err"); return;
  }
  if (!cid) {
    showMsg("login-msg", "Please enter your Citizen ID.", "err"); return;
  }

  showMsg("login-msg", "Verifying identity…", "info");

  const loginPayload = { citizen_id: cid, national_id_number: nid };
  let r = await req("POST", "/auth/citizen-login", loginPayload);

  if (!r.ok && r.status === 404) {
    // If the user entered a CNIC number instead of the national ID, retry explicitly.
    r = await req("POST", "/auth/citizen-login", { citizen_id: cid, cnic_number: nid });
  }

  if (r.ok) {
    TOKEN      = r.data.token;
    CITIZEN_ID = r.data.citizen.citizen_id;
    CITIZEN    = {
      ...r.data.citizen,
      full_name: `${r.data.citizen.first_name} ${r.data.citizen.last_name}`.trim()
    };
    sessionStorage.setItem("crida_citizen_token", TOKEN);
    sessionStorage.setItem("crida_citizen_id", CITIZEN_ID);

    showPortal();
    toast("Welcome, " + CITIZEN.first_name + "!", "ok");
  } else {
    showMsg("login-msg", r.data.error || "Identity verification failed. Check your NID and Citizen ID.", "err");
  }
}

function showRegistrationForm(evt) {
  if (evt) evt.preventDefault();
  document.getElementById("login-panel").style.display = "none";
  document.getElementById("status-panel").style.display = "none";
  document.getElementById("register-panel").style.display = "block";
  document.getElementById("login-msg").className = "msg";
  document.getElementById("status-msg").className = "msg";
  document.getElementById("status-details").style.display = "none";
}

function showStatusCheckForm(evt) {
  if (evt) evt.preventDefault();
  document.getElementById("login-panel").style.display = "none";
  document.getElementById("register-panel").style.display = "none";
  document.getElementById("status-panel").style.display = "block";
  document.getElementById("login-msg").className = "msg";
  document.getElementById("apply-msg").className = "msg";
}

function showLoginForm(evt) {
  if (evt) evt.preventDefault();
  document.getElementById("register-panel").style.display = "none";
  document.getElementById("status-panel").style.display = "none";
  document.getElementById("login-panel").style.display = "block";
  document.getElementById("apply-msg").className = "msg";
  document.getElementById("status-msg").className = "msg";
  document.getElementById("status-details").style.display = "none";
}

async function submitCitizenApplication() {
  const data = {
    first_name: document.getElementById("r-first").value.trim(),
    last_name: document.getElementById("r-last").value.trim(),
    dob: document.getElementById("r-dob").value,
    gender: document.getElementById("r-gender").value,
    marital_status: document.getElementById("r-marital").value,
    blood_group: document.getElementById("r-blood").value,
    house_no: document.getElementById("r-house").value.trim(),
    street: document.getElementById("r-street").value.trim(),
    city: document.getElementById("r-city").value.trim(),
    province: document.getElementById("r-province").value.trim(),
    postal_code: document.getElementById("r-postal").value.trim(),
    phone: document.getElementById("r-phone").value.trim(),
    email: document.getElementById("r-email").value.trim()
  };

  if (!data.first_name || !data.last_name || !data.dob || !data.gender || !data.city || !data.province) {
    let missing = [];
    if (!data.first_name) missing.push("First Name");
    if (!data.last_name) missing.push("Last Name");
    if (!data.dob) missing.push("Date of Birth");
    if (!data.gender) missing.push("Gender");
    if (!data.city) missing.push("City");
    if (!data.province) missing.push("Province");
    showMsg("apply-msg", `Please fill in the following required fields: ${missing.join(", ")}`, "err");
    return;
  }

  showMsg("apply-msg", "Submitting your application…", "info");
  try {
    const r = await req("POST", "/citizens/apply", data);
    if (r.ok) {
      showMsg("apply-msg", "Application submitted successfully. An officer will review it shortly.", "ok");
      document.getElementById("r-first").value = "";
      document.getElementById("r-last").value = "";
      document.getElementById("r-dob").value = "";
      document.getElementById("r-gender").value = "";
      document.getElementById("r-marital").value = "Single";
      document.getElementById("r-blood").value = "";
      document.getElementById("r-house").value = "";
      document.getElementById("r-street").value = "";
      document.getElementById("r-city").value = "";
      document.getElementById("r-province").value = "";
      document.getElementById("r-postal").value = "";
      document.getElementById("r-phone").value = "";
      document.getElementById("r-email").value = "";
      toast("Registration application sent", "ok");
    } else {
      showMsg("apply-msg", r.data.error || "Could not submit the application.", "err");
    }
  } catch (e) {
    showMsg("apply-msg", `Submission failed: ${e.message}`, "err");
  }
}

async function checkApplicationStatus() {
  const first = document.getElementById("s-first").value.trim();
  const last = document.getElementById("s-last").value.trim();
  const dob = document.getElementById("s-dob").value;

  if (!first || !last || !dob) {
    showMsg("status-msg", "Please enter your first name, last name, and date of birth.", "err");
    return;
  }

  showMsg("status-msg", "Checking status…", "info");
  try {
    const r = await req("GET", `/citizens/applications/status?first_name=${encodeURIComponent(first)}&last_name=${encodeURIComponent(last)}&dob=${dob}`);
    if (r.ok) {
      const app = r.data.application;
      let content = `
        <p><strong>Status:</strong> <span class="badge ${app.status === 'Approved' ? 'badge-success' : app.status === 'Rejected' ? 'badge-danger' : 'badge-warning'}">${app.status}</span></p>
        <p><strong>Submitted:</strong> ${app.submission_date ? new Date(app.submission_date).toLocaleDateString() : 'N/A'}</p>
        <p><strong>Name:</strong> ${app.first_name} ${app.last_name}</p>
      `;
      if (app.status === 'Approved') {
        content += `
          <p><strong>Citizen ID:</strong> ${app.citizen_id}</p>
          <p><strong>National ID Number:</strong> ${app.national_id_number || app.cnic_number || '—'}</p>
          <p style="font-size:.8rem;color:#a06010;margin-top:4px">
            <i class="fas fa-info-circle"></i>
            Your <strong>Birth Certificate</strong> is now available in the citizen portal.
            To apply for a <strong>CNIC</strong>, please login and go to <em>Documents → Apply for CNIC</em>.
          </p>
          <button onclick="fillLoginForm('${app.citizen_id}', '${app.national_id_number || app.cnic_number}')" class="btn btn-primary" style="margin-top:10px">
            <i class="fas fa-sign-in-alt"></i> Login with these credentials
          </button>
        `;
      } else if (app.status === 'Rejected') {
        content += `<p><strong>Reason:</strong> ${app.rejection_reason || 'No reason provided'}</p>`;
      }
      document.getElementById("status-content").innerHTML = content;
      document.getElementById("status-details").style.display = "block";
      showMsg("status-msg", "Status retrieved.", "ok");
    } else {
      showMsg("status-msg", r.data.error || "Could not retrieve status.", "err");
      document.getElementById("status-details").style.display = "none";
    }
  } catch (e) {
    showMsg("status-msg", `Status lookup failed: ${e.message}`, "err");
    document.getElementById("status-details").style.display = "none";
  }
}

function fillLoginForm(cid, cnic) {
  document.getElementById("c-cid").value = cid;
  document.getElementById("c-nid").value = cnic;
  showLoginForm();
  toast("Credentials filled. Click 'Access My Records' to login.", "ok");
}

function showPortal() {
  const loginScreen = document.getElementById("screen-login");
  const portalScreen = document.getElementById("screen-portal");
  if (loginScreen) loginScreen.style.display = "none";
  if (portalScreen) portalScreen.style.display = "block";
  const displayName = CITIZEN?.full_name || ((CITIZEN?.first_name||"") + " " + (CITIZEN?.last_name||"")).trim() || "Citizen";
  document.getElementById("header-user").innerHTML = `
    <a href="Landing.html" style="font-size:.75rem;color:var(--text-muted);text-decoration:none;display:flex;align-items:center;gap:5px;margin-right:8px;padding:6px 10px;border:1px solid var(--border);border-radius:6px;transition:all .15s" onmouseover="this.style.borderColor='var(--green)';this.style.color='var(--green)'" onmouseout="this.style.borderColor='var(--border)';this.style.color='var(--text-muted)'"><i class='fas fa-home'></i> Home</a>
    <div class="user-pill">
      <div class="dot"></div>
      <span>${displayName}</span>
    </div>
    <button onclick="citizenLogout()" class="btn btn-secondary" style="padding:6px 12px;font-size:.76rem">
      <i class="fas fa-sign-out-alt"></i> Logout
    </button>
  `;
  const portalUserName = document.getElementById("portal-user-name");
  if (portalUserName) portalUserName.textContent = displayName;
  const dashboardTab = document.querySelector(".nav-tab[onclick*='dashboard']") || document.querySelector(".nav-tab");
  if (dashboardTab) switchPanel('dashboard', dashboardTab);
  loadProfile();
  loadUnreadCount();
}

function citizenLogout() {
  TOKEN = null; CITIZEN_ID = null; CITIZEN = null;
  sessionStorage.removeItem("crida_citizen_token");
  sessionStorage.removeItem("crida_citizen_id");
  const portalScreen = document.getElementById("screen-portal");
  if (portalScreen) portalScreen.style.display = "none";
  document.getElementById("screen-login").style.display  = "flex";
  document.getElementById("header-user").innerHTML = "";
  document.getElementById("login-panel").style.display = "block";
  document.getElementById("register-panel").style.display = "none";
  document.getElementById("status-panel").style.display = "none";
  document.getElementById("login-msg").className = "msg";
  document.getElementById("apply-msg").className = "msg";
  document.getElementById("status-msg").className = "msg";
  document.getElementById("status-details").style.display = "none";
  _loaded.clear();
  toast("Logged out successfully.", "warn");
}

// ── Auto-login on page load ───────────────────────────────────────────────
window.addEventListener("load", async () => {
  if (TOKEN && CITIZEN_ID) {
    const r = await req("GET", `/citizens/${CITIZEN_ID}`);
    if (r.ok) {
      const c = r.data.citizen || r.data;
      // Normalize — CitizenProfile_View returns full_name, citizen-login returns first/last
      const fullName = c.full_name || `${c.first_name || ""} ${c.last_name || ""}`.trim();
      const parts    = fullName.split(" ");
      CITIZEN = {
        first_name:  c.first_name  || parts[0] || "Citizen",
        last_name:   c.last_name   || parts.slice(1).join(" ") || "",
        full_name:   fullName,
        citizen_id:  c.citizen_id
      };
      showPortal();
    } else {
      sessionStorage.clear();
    }
  }
});

// ── PROFILE ───────────────────────────────────────────────────────────────
async function loadProfile() {
  const div = document.getElementById("profile-content");
  if (div) div.innerHTML = `<div class="loading"><i class="fas fa-circle-notch"></i>Loading your profile…</div>`;

  const r = await req("GET", `/citizens/${CITIZEN_ID}`);
  if (!r.ok) {
    div.innerHTML = `<div class="msg err show"><i class="fas fa-exclamation-circle"></i> Could not load profile: ${r.data.error || r.status}</div>`;
    return;
  }

  const raw = r.data.citizen || r.data;
  // Normalise name fields — API may return full_name only
  const fullName = raw.full_name || `${raw.first_name || ""} ${raw.last_name || ""}`.trim() || "Citizen";
  const nameParts = fullName.split(" ");
  const c = {
    ...raw,
    first_name: raw.first_name || nameParts[0] || "Citizen",
    last_name:  raw.last_name  || nameParts.slice(1).join(" ") || "",
    full_name:  fullName
  };
  const initials = (c.first_name?.[0] || "") + (c.last_name?.[0] || "");
  const statusBadge = c.status === "active"
    ? `<span class="badge badge-success"><i class="fas fa-check-circle" style="margin-right:3px"></i>Active</span>`
    : `<span class="badge badge-danger">${c.status}</span>`;

  const securityBadge = c.security_status && c.security_status !== "Clear"
    ? `<span class="badge badge-danger" style="margin-left:6px"><i class="fas fa-exclamation-triangle" style="margin-right:3px"></i>${c.security_status}</span>`
    : `<span class="badge badge-success" style="margin-left:6px"><i class="fas fa-shield-alt" style="margin-right:3px"></i>Clear</span>`;

  div.innerHTML = `
    <div class="card">
      <div class="profile-hero">
        <div class="profile-avatar">${initials}</div>
        <div class="profile-hero-info">
          <h3>${c.first_name} ${c.last_name}</h3>
          <p>NID: ${c.national_id_number || "—"} &nbsp;·&nbsp; Citizen ID: ${c.citizen_id}</p>
          <div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:6px">
            ${statusBadge}${securityBadge}
          </div>
        </div>
      </div>

      <div class="profile-grid">
        ${pf("Date of Birth",    c.dob ? (() => { try { const d = new Date(c.dob); return isNaN(d) ? String(c.dob).substring(0,10) : d.toLocaleDateString('en-PK',{day:'2-digit',month:'short',year:'numeric'}); } catch(e){ return String(c.dob).substring(0,10); }})() : "—")}
        ${pf("Age",              c.age ?? "—")}
        ${pf("Gender",           c.gender || "—")}
        ${pf("Marital Status",   c.marital_status || "—")}
        ${pf("Blood Group",      c.blood_group || "—")}
        ${pf("Active CNIC",      c.has_active_cnic  === "Yes" ? "✅ Yes" : "❌ No")}
        ${pf("Valid Passport",   c.has_valid_passport === "Yes" ? "✅ Yes" : "❌ No")}
        ${pf("Valid License",    c.has_valid_license === "Yes" ? "✅ Yes" : "❌ No")}
      </div>

      ${c.city ? `
        <div style="margin-top:18px;padding-top:16px;border-top:1px solid var(--border)">
          <div class="pf-label" style="margin-bottom:8px"><i class="fas fa-map-marker-alt" style="margin-right:5px;color:var(--green)"></i>Current Address</div>
          <div style="font-size:.88rem">${[c.house_no, c.street, c.city, c.province, c.postal_code].filter(Boolean).join(", ")}</div>
        </div>` : ""}
    </div>
  `;
}

function pf(label, value) {
  return `<div class="profile-field"><div class="pf-label">${label}</div><div class="pf-value">${value ?? "—"}</div></div>`;
}

// ── APPLICATIONS ──────────────────────────────────────────────────────────
async function loadApplications() {
  const div = document.getElementById("apps-content");
  div.innerHTML = `<div class="loading"><i class="fas fa-circle-notch"></i>Loading…</div>`;

  const [cnic, passport, license] = await Promise.all([
    req("GET", `/cnic/?citizen_id=${CITIZEN_ID}`).catch(() => ({ ok: false })),
    req("GET", `/passports/?citizen_id=${CITIZEN_ID}`).catch(() => ({ ok: false })),
    req("GET", `/licenses/?citizen_id=${CITIZEN_ID}`).catch(() => ({ ok: false }))
  ]);

  const all = [];
  if (cnic.ok)    (cnic.data.applications    || []).forEach(a => all.push({ type: "CNIC",            subtype: a.application_type, ...a }));
  if (passport.ok)(passport.data.applications|| []).forEach(a => all.push({ type: "Passport",         subtype: a.application_type, ...a }));
  if (license.ok) (license.data.applications || []).forEach(a => all.push({ type: "Driving License",  subtype: a.license_type,     ...a }));

  if (!all.length) {
    div.innerHTML = `<div class="empty"><i class="fas fa-file-alt"></i>No applications found.</div>`;
    return;
  }

  const sc = s => {
    if (!s) return "badge-info";
    const sl = s.toLowerCase();
    if (sl.includes("approved") || sl.includes("collected") || sl.includes("passed")) return "badge-success";
    if (sl.includes("reject") || sl.includes("fail"))  return "badge-danger";
    return "badge-warning";
  };

  div.innerHTML = all.map(a => `
    <div class="app-item">
      <div>
        <div class="ai-type">${a.type} — ${a.subtype || ""}</div>
        <div class="ai-meta">Submitted: ${a.submission_date ? String(a.submission_date).substring(0,10) : "—"}</div>
      </div>
      <span class="badge ${sc(a.status)}">${a.status}</span>
    </div>
  `).join("");
}

// ── DOCUMENTS ─────────────────────────────────────────────────────────────
async function renderDocButtons() {
  const grid = document.getElementById("doc-grid");
  const msgEl = document.getElementById("doc-msg");
  grid.innerHTML = `<div class="loading"><i class="fas fa-circle-notch"></i> Checking your documents…</div>`;

  // Fetch citizen profile to get live document status
  const r = await req("GET", `/citizens/${CITIZEN_ID}`);
  const profile = r.ok ? (r.data.citizen || r.data) : {};

  const hasCnic     = profile.has_active_cnic     === "Yes";
  const hasPassport = profile.has_valid_passport   === "Yes";
  const hasLicense  = profile.has_valid_license    === "Yes";

  // Fetch application statuses for pending/in-progress states
  const [cnicR, passR, dlR] = await Promise.all([
    req("GET", `/cnic/?citizen_id=${CITIZEN_ID}`),
    req("GET", `/passports/?citizen_id=${CITIZEN_ID}`),
    req("GET", `/licenses/?citizen_id=${CITIZEN_ID}`)
  ]);

  const latestApp = (apps) => {
    const list = apps || [];
    return list.sort((a, b) => new Date(b.submission_date) - new Date(a.submission_date))[0] || null;
  };

  const cnicApp     = latestApp(cnicR.ok  ? cnicR.data.applications  : []);
  const passApp     = latestApp(passR.ok  ? passR.data.applications  : []);
  const dlApp       = latestApp(dlR.ok    ? dlR.data.applications    : []);

  const statusTag = (s) => {
    if (!s) return '';
    const cls = s === 'Approved' ? 'badge-success'
              : s.includes('Reject') ? 'badge-danger'
              : 'badge-warning';
    return `<span class="badge ${cls}" style="font-size:.7rem">${s}</span>`;
  };

  const docCard = ({ name, icon, path, active, app, applyFn, applyLabel }) => {
    const appStatus = app ? app.status : null;
    const isPending = appStatus && !['Approved','Rejected'].includes(appStatus);
    return `
    <div class="doc-card">
      <div class="dc-icon"><i class="fas ${icon}"></i></div>
      <div class="dc-name">${name}</div>
      ${appStatus ? `<div style="margin:4px 0;">${statusTag(appStatus)}</div>` : ''}
      ${active
        ? `<div class="dc-btn" onclick="downloadPDF('${path}','${name}')">
             <i class="fas fa-download"></i> Download PDF
           </div>`
        : isPending
          ? `<div class="dc-btn" style="background:var(--gold);color:#000;cursor:default;">
               <i class="fas fa-clock"></i> In Progress
             </div>`
          : `<div class="dc-btn" onclick="${applyFn}" style="background:var(--green-deep)">
               <i class="fas fa-plus"></i> ${applyLabel}
             </div>`
      }
    </div>`;
  };

  const cards = [
    docCard({ name: "CNIC Card",        icon: "fa-id-card",  path: `cnic/${CITIZEN_ID}`,     active: hasCnic,     app: cnicApp,  applyFn: "openApplyModal('cnic')",     applyLabel: "Apply for CNIC" }),
    docCard({ name: "Passport",         icon: "fa-passport", path: `passport/${CITIZEN_ID}`, active: hasPassport, app: passApp,  applyFn: "openApplyModal('passport')", applyLabel: "Apply for Passport" }),
    docCard({ name: "Driving License",  icon: "fa-car",      path: `license/${CITIZEN_ID}`,  active: hasLicense,  app: dlApp,    applyFn: "openApplyModal('license')",  applyLabel: "Apply for License" }),
    // Birth Certificate is always available after registration — no application needed
    docCard({ name: "Birth Certificate",    icon: "fa-baby",  path: `birth-certificate/${CITIZEN_ID}`,    active: true,  app: null, applyFn: "", applyLabel: "" }),
    // Marriage Certificate is available if the citizen is registered as married
    docCard({ name: "Marriage Certificate", icon: "fa-heart", path: `marriage-certificate/${CITIZEN_ID}`, active: (profile.marital_status === 'Married'), app: null, applyFn: "", applyLabel: "" }),
  ];

  grid.innerHTML = cards.join("");
}

// ── APPLY MODAL ───────────────────────────────────────────────────────────
function openApplyModal(type) {
  const titles = { cnic: "Apply for CNIC", passport: "Apply for Passport", license: "Apply for Driving License" };
  let bodyHtml = "";

  if (type === "cnic") {
    bodyHtml = `
      <div class="form-group">
        <label>Application Type</label>
        <select id="apply-type" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:7px;background:var(--surface);color:var(--text)">
          <option value="New">New</option>
          <option value="Renewal">Renewal</option>
          <option value="Replacement">Replacement</option>
        </select>
      </div>`;
  } else if (type === "passport") {
    bodyHtml = `
      <div class="form-group">
        <label>Application Type</label>
        <select id="apply-type" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:7px;background:var(--surface);color:var(--text)">
          <option value="New">New</option>
          <option value="Renewal">Renewal</option>
          <option value="Lost Replacement">Lost Replacement</option>
        </select>
      </div>`;
  } else if (type === "license") {
    bodyHtml = `
      <div class="form-group">
        <label>License Type</label>
        <select id="apply-license-type" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:7px;background:var(--surface);color:var(--text)">
          <option value="Car">Car</option>
          <option value="Motorcycle">Motorcycle</option>
          <option value="Commercial">Commercial</option>
          <option value="Heavy Vehicle">Heavy Vehicle</option>
        </select>
      </div>`;
  }

  bodyHtml += `<div id="apply-modal-msg" class="msg" style="margin-top:10px"></div>`;

  document.getElementById("apply-modal-title").textContent = titles[type];
  document.getElementById("apply-modal-body").innerHTML = bodyHtml;
  document.getElementById("apply-modal-submit").onclick = () => submitDocApplication(type);
  document.getElementById("apply-modal").style.display = "flex";
}

function closeApplyModal() {
  document.getElementById("apply-modal").style.display = "none";
}

async function submitDocApplication(type) {
  const msgEl = document.getElementById("apply-modal-msg");
  msgEl.className = "msg info show";
  msgEl.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Submitting…`;

  let endpoint = "", body = {};

  if (type === "cnic") {
    endpoint = "/cnic/citizen-apply";
    body = { application_type: document.getElementById("apply-type").value };
  } else if (type === "passport") {
    endpoint = "/passports/citizen-apply";
    body = { application_type: document.getElementById("apply-type").value };
  } else if (type === "license") {
    endpoint = "/licenses/citizen-apply";
    body = { license_type: document.getElementById("apply-license-type").value };
  }

  const r = await req("POST", endpoint, body);
  if (r.ok) {
    msgEl.className = "msg ok show";
    msgEl.innerHTML = `<i class="fas fa-check-circle"></i> Application submitted successfully! You will receive a notification when it progresses.`;
    toast("Application submitted!", "ok");
    _loaded.delete("documents");
    setTimeout(() => { closeApplyModal(); renderDocButtons(); }, 2000);
  } else {
    msgEl.className = "msg err show";
    msgEl.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${r.data.error || "Submission failed."}` ;
  }
}

async function loadDashboardSummary() {
  const div = document.getElementById("dashboard-summary");
  if (!div) return;
  div.innerHTML = `<div class="loading"><i class="fas fa-circle-notch"></i>Loading dashboard summary…</div>`;

  const [cnicR, passportR, licenseR, notifR] = await Promise.all([
    req("GET", `/cnic/?citizen_id=${CITIZEN_ID}`),
    req("GET", `/passports/?citizen_id=${CITIZEN_ID}`),
    req("GET", `/licenses/?citizen_id=${CITIZEN_ID}`),
    req("GET", `/notifications/unread-count?citizen_id=${CITIZEN_ID}`)
  ]);

  const cnicApps = cnicR.ok ? (cnicR.data.applications || []) : [];
  const passportApps = passportR.ok ? (passportR.data.applications || []) : [];
  const licenseApps = licenseR.ok ? (licenseR.data.applications || []) : [];
  const unread = notifR.ok ? (notifR.data.unread_count || 0) : 0;

  const totalApps = cnicApps.length + passportApps.length + licenseApps.length;
  const latestApp = [...cnicApps, ...passportApps, ...licenseApps]
    .sort((a,b) => new Date(b.submission_date) - new Date(a.submission_date))[0] || null;

  div.innerHTML = `
    <div class="profile-grid">
      <div class="profile-field">
        <div class="pf-label">Pending applications</div>
        <div class="pf-value">${totalApps}</div>
      </div>
      <div class="profile-field">
        <div class="pf-label">Unread notifications</div>
        <div class="pf-value">${unread}</div>
      </div>
      <div class="profile-field">
        <div class="pf-label">Last submitted</div>
        <div class="pf-value">${latestApp ? String(latestApp.submission_date).substring(0, 10) : '—'}</div>
      </div>
      <div class="profile-field">
        <div class="pf-label">Latest status</div>
        <div class="pf-value">${latestApp ? latestApp.status : 'No applications yet'}</div>
      </div>
    </div>
    <div style="margin-top:16px;font-size:.88rem;color:var(--text-muted);">
      This dashboard provides a quick overview of your submitted documents, unread notifications, and most recent application status.
    </div>
  `;
}

async function downloadPDF(path, label) {
  showMsg("doc-msg", `Generating ${label}…`, "info");
  try {
    // Use fetch directly so we can inspect status before treating as blob
    const res = await fetch(`${API}/pdf/${path}`, {
      headers: { "Authorization": "Bearer " + TOKEN }
    });
    if (res.status === 403) {
      showMsg("doc-msg",
        `Permission denied. Ask a Registrar officer to download your ${label} on your behalf, or visit your nearest CRIDA office.`,
        "err");
      return;
    }
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      showMsg("doc-msg", `Could not generate ${label}: ${errData.error || res.status}`, "err");
      return;
    }
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = `${path.replace("/","_")}.pdf`; a.click();
    showMsg("doc-msg", `${label} downloaded successfully.`, "ok");
    toast(`${label} ready!`, "ok");
  } catch (e) {
    showMsg("doc-msg", `Could not generate ${label}: ${e.message}`, "err");
  }
}

// ── FAMILY TREE ───────────────────────────────────────────────────────────
async function loadFamilyTree() {
  const div = document.getElementById("family-content");
  div.innerHTML = `<div class="loading"><i class="fas fa-circle-notch"></i>Loading…</div>`;

  const r = await req("GET", `/family-tree/${CITIZEN_ID}`);
  if (!r.ok) {
    div.innerHTML = `<div class="empty"><i class="fas fa-sitemap"></i>${r.data.error || "No family data found."}</div>`;
    return;
  }

  const data  = r.data;
  const root  = data.citizen;
  const allRels = [...(data.relationships || []), ...(data.reverse_relations || [])];
  const seen  = new Set();
  const parents = [], children = [], siblings = [], others = [];

  allRels.forEach(rel => {
    if (seen.has(rel.citizen_id)) return;
    seen.add(rel.citizen_id);
    const rt = rel.relationship_type;
    if (['Father','Mother','Grandfather','Grandmother'].includes(rt))           parents.push(rel);
    else if (['Son','Daughter','Child','Grandson','Granddaughter'].includes(rt)) children.push(rel);
    else if (['Brother','Sister','Sibling'].includes(rt))                        siblings.push(rel);
    else if (!['Husband','Wife','Spouse'].includes(rt))                          others.push(rel);
  });

  const spouse = data.spouse;
  const spouseRel = spouse ? (root.gender === 'Male' ? 'Wife' : 'Husband') : null;

  const node = (name, rel, isRoot = false, cid = null) => `
    <div class="ft-node ${isRoot ? 'ft-root' : ''}">
      <div class="ft-avatar">${(name || '?').split(' ').map(n=>n[0]).join('').substring(0,2).toUpperCase()}</div>
      <div class="ft-name">${name || '—'}</div>
      ${rel ? `<div class="ft-rel">${rel}</div>` : ''}
      ${cid ? `<div class="ft-cid">#${cid}</div>` : ''}
    </div>`;

  const nodeGroup = (items, label) => items.length ? `
    <div class="ft-group">
      <div class="ft-group-label">${label}</div>
      <div class="ft-group-nodes">${items.map(m => node(m.full_name, m.relationship_type, false, m.citizen_id)).join('')}</div>
    </div>` : '';

  div.innerHTML = `
    <div class="ft-tree-wrap">
      <style>
        .ft-tree-wrap{font-family:'IBM Plex Sans',sans-serif;padding:8px 0;}
        .ft-level{display:flex;justify-content:center;gap:12px;flex-wrap:wrap;margin:0 0 0;}
        .ft-connector{display:flex;justify-content:center;align-items:center;height:36px;position:relative;}
        .ft-connector::before{content:'';position:absolute;top:0;left:50%;width:2px;height:100%;background:var(--border-dark);}
        .ft-h-line{height:2px;background:var(--border-dark);flex:1;}
        .ft-node{display:flex;flex-direction:column;align-items:center;gap:4px;cursor:default;}
        .ft-node.ft-root .ft-avatar{background:var(--green);border:3px solid var(--green-light);box-shadow:0 0 0 4px rgba(10,92,54,.15);}
        .ft-avatar{width:52px;height:52px;border-radius:50%;background:var(--text-mid);color:white;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:700;font-family:'Playfair Display',serif;border:2px solid var(--border-dark);}
        .ft-name{font-size:.75rem;font-weight:600;text-align:center;max-width:80px;color:var(--text);}
        .ft-rel{font-size:.65rem;color:var(--text-muted);text-align:center;background:var(--green-pale);padding:1px 6px;border-radius:10px;color:var(--green);}
        .ft-cid{font-size:.62rem;color:var(--text-muted);font-family:'IBM Plex Mono',monospace;}
        .ft-group{display:flex;flex-direction:column;align-items:center;gap:6px;}
        .ft-group-label{font-size:.65rem;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:2px;}
        .ft-group-nodes{display:flex;gap:12px;flex-wrap:wrap;justify-content:center;}
        .ft-middle-row{display:flex;align-items:center;justify-content:center;gap:20px;flex-wrap:wrap;margin:12px 0;}
        .ft-spouse-line{width:40px;height:2px;background:var(--gold);}
        .ft-section{margin:8px 0;}
        .ft-section-title{text-align:center;font-size:.65rem;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px;}
      </style>

      ${parents.length ? `
        <div class="ft-section">
          <div class="ft-section-title"><i class="fas fa-arrow-up" style="margin-right:4px"></i>Parents</div>
          <div class="ft-level">${parents.map(m => node(m.full_name, m.relationship_type, false, m.citizen_id)).join('')}</div>
        </div>
        <div class="ft-connector"></div>
      ` : ''}

      <div class="ft-middle-row">
        ${siblings.length ? `
          <div class="ft-group">
            <div class="ft-group-label">Siblings</div>
            <div class="ft-group-nodes">${siblings.map(m => node(m.full_name, m.relationship_type, false, m.citizen_id)).join('')}</div>
          </div>
          <div style="width:30px;height:2px;background:var(--border-dark)"></div>
        ` : ''}

        ${node(root.full_name || (root.first_name + ' ' + root.last_name), 'You', true, root.citizen_id)}

        ${spouse ? `
          <div style="display:flex;align-items:center;gap:8px">
            <div class="ft-spouse-line"></div>
            <div class="ft-group">
              <div class="ft-group-label">${spouseRel}</div>
              ${node(spouse.spouse_name, spouseRel, false, spouse.spouse_id)}
            </div>
          </div>
        ` : ''}
      </div>

      ${children.length ? `
        <div class="ft-connector"></div>
        <div class="ft-section">
          <div class="ft-section-title"><i class="fas fa-arrow-down" style="margin-right:4px"></i>Children</div>
          <div class="ft-level">${children.map(m => node(m.full_name, m.relationship_type, false, m.citizen_id)).join('')}</div>
        </div>
      ` : ''}

      ${others.length ? `
        <div class="ft-section" style="margin-top:16px;padding-top:14px;border-top:1px solid var(--border)">
          <div class="ft-section-title">Other Relations</div>
          <div class="ft-level">${others.map(m => node(m.full_name, m.relationship_type, false, m.citizen_id)).join('')}</div>
        </div>
      ` : ''}

      ${!parents.length && !children.length && !siblings.length && !spouse && !others.length ? `
        <div class="empty"><i class="fas fa-sitemap"></i>No family relationships on record.</div>
      ` : ''}
    </div>`;
}

// ── NOTIFICATIONS ─────────────────────────────────────────────────────────
async function loadUnreadCount() {
  const r = await req("GET", `/notifications/unread-count?citizen_id=${CITIZEN_ID}`);
  if (r.ok && r.data.unread_count > 0) {
    document.getElementById("notif-dot").style.display = "inline-block";
  }
}

async function loadNotifications() {
  const div = document.getElementById("notif-content");
  div.innerHTML = `<div class="loading"><i class="fas fa-circle-notch"></i>Loading…</div>`;

  const r = await req("GET", `/notifications/?citizen_id=${CITIZEN_ID}`);
  const items = r.ok ? (r.data.notifications || []) : [];

  if (!items.length) {
    div.innerHTML = `<div class="empty"><i class="fas fa-bell"></i>No notifications yet.</div>`;
    return;
  }

  const typeIcon = t => t === "success" ? "fa-check-circle" : t === "warning" ? "fa-exclamation-triangle" : t === "error" ? "fa-times-circle" : "fa-info-circle";
  const typeBadge = t => t === "success" ? "badge-success" : t === "warning" ? "badge-warning" : t === "error" ? "badge-danger" : "badge-info";

  div.innerHTML = items.map(n => `
    <div class="notif-card ${n.is_read ? "" : "unread"}">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
        <div class="nc-title"><i class="fas ${typeIcon(n.notification_type)}" style="margin-right:6px;opacity:.7"></i>${n.title}</div>
        <span class="badge ${typeBadge(n.notification_type)}">${n.notification_type}</span>
      </div>
      <div class="nc-msg">${n.message}</div>
      <div class="nc-time">${String(n.created_at).substring(0,19)}${n.is_read ? "" : " &nbsp;·&nbsp; <strong style='color:var(--gold)'>Unread</strong>"}</div>
    </div>
  `).join("");

  document.getElementById("notif-dot").style.display = "none";
}

// ── COMPLAINTS ────────────────────────────────────────────────────────────
async function submitComplaint() {
  const subject = document.getElementById("comp-subject").value.trim();
  const desc    = document.getElementById("comp-desc").value.trim();

  if (!subject || !desc) { showMsg("comp-msg", "Please fill in both subject and description.", "err"); return; }

  showMsg("comp-msg", "Submitting…", "info");

  const r = await req("POST", "/complaints/", { citizen_id: CITIZEN_ID, subject, description: desc });

  if (r.ok) {
    showMsg("comp-msg", "Complaint submitted. We will respond within 5 working days.", "ok");
    document.getElementById("comp-subject").value = "";
    document.getElementById("comp-desc").value    = "";
    toast("Complaint submitted", "ok");
    _loaded.delete("complaints");
    loadMyComplaints();
  } else {
    showMsg("comp-msg", r.data.error || "Submission failed.", "err");
  }
}

async function loadMyComplaints() {
  const div = document.getElementById("complaints-content");
  div.innerHTML = `<div class="loading"><i class="fas fa-circle-notch"></i>Loading…</div>`;

  const r = await req("GET", `/complaints/?citizen_id=${CITIZEN_ID}`);
  const items = r.ok ? (r.data.complaints || []) : [];

  if (!items.length) {
    div.innerHTML = `<div class="empty"><i class="fas fa-comment-dots"></i>No complaints submitted yet.</div>`;
    return;
  }

  const sc = s => s === "Resolved" || s === "Closed" ? "badge-success" : s === "In Progress" ? "badge-warning" : "badge-info";

  div.innerHTML = `<table class="data-table">
    <thead><tr><th>Subject</th><th>Status</th><th>Submitted</th></tr></thead>
    <tbody>
      ${items.map(c => `<tr>
        <td>${c.subject}</td>
        <td><span class="badge ${sc(c.status)}">${c.status}</span></td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:.76rem">${String(c.created_at).substring(0,10)}</td>
      </tr>`).join("")}
    </tbody>
  </table>`;
}

// ── UPDATE REQUESTS ───────────────────────────────────────────────────────
async function submitUpdateRequest() {
  const field  = document.getElementById("upd-field").value;
  const value  = document.getElementById("upd-value").value.trim();
  const reason = document.getElementById("upd-reason").value.trim();

  if (!value) { showMsg("upd-msg", "Please enter the new value.", "err"); return; }

  showMsg("upd-msg", "Submitting request…", "info");

  const r = await req("POST", "/update-requests/", {
    citizen_id: CITIZEN_ID,
    field_name: field,
    new_value:  value,
    reason:     reason || "Requested by citizen"
  });

  if (r.ok) {
    showMsg("upd-msg", "Request submitted. A Registrar will review it within 2–5 working days.", "ok");
    document.getElementById("upd-value").value  = "";
    document.getElementById("upd-reason").value = "";
    toast("Update request submitted", "ok");
    _loaded.delete("updates");
    loadMyUpdateRequests();
  } else {
    showMsg("upd-msg", r.data.error || "Submission failed.", "err");
  }
}

async function loadMyUpdateRequests() {
  const div = document.getElementById("updates-content");
  div.innerHTML = `<div class="loading"><i class="fas fa-circle-notch"></i>Loading…</div>`;

  const r = await req("GET", `/update-requests/?citizen_id=${CITIZEN_ID}`);
  const items = r.ok ? (r.data.requests || []) : [];

  if (!items.length) {
    div.innerHTML = `<div class="empty"><i class="fas fa-edit"></i>No update requests yet.</div>`;
    return;
  }

  const sc = s => s === "Approved" ? "badge-success" : s === "Rejected" ? "badge-danger" : "badge-warning";

  div.innerHTML = `<table class="data-table">
    <thead><tr><th>Field</th><th>New Value</th><th>Status</th><th>Date</th></tr></thead>
    <tbody>
      ${items.map(u => `<tr>
        <td><code>${u.field_name}</code></td>
        <td>${u.new_value}</td>
        <td><span class="badge ${sc(u.status)}">${u.status}</span></td>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:.76rem">${String(u.created_at).substring(0,10)}</td>
      </tr>`).join("")}
    </tbody>
  </table>`;
}

// ── FAMILY TREE ───────────────────────────────────────────────────────────
async function loadFamily() {
  const div = document.getElementById("family-content");
  div.innerHTML = `<div class="loading"><i class="fas fa-circle-notch"></i>Loading family tree…</div>`;

  const r = await req("GET", `/family-tree/${CITIZEN_ID}`);
  if (r.ok) {
    if (!r.data.relationships?.length && !r.data.reverse_relations?.length && !r.data.spouse) {
      div.innerHTML = `<div class="empty"><i class="fas fa-sitemap"></i>No family relationships found.</div>`;
    } else {
      renderCitizenTree(r.data, "family-content");
    }
  } else {
    div.innerHTML = `<div class="msg err show"><i class="fas fa-exclamation-circle"></i> ${r.data.error || "Could not load family tree."}</div>`;
  }
}

function renderCitizenTree(data, targetId) {
  const parents = [], children = [], siblings = [], others = [];
  const seen = new Set();

  let customSpouse = null;

  [
    ...(data.relationships || []).map(r => ({ ...r, _rel: r.relationship_type })),
    ...(data.reverse_relations || []).map(r => ({ ...r, _rel: r.relationship_type }))
  ].forEach(r => {
    if (seen.has(r.citizen_id)) return;
    seen.add(r.citizen_id);
    const rel = r._rel;
    if (['Father', 'Mother', 'Grandfather', 'Grandmother'].includes(rel)) parents.push(r);
    else if (['Son', 'Daughter', 'Child', 'Grandson', 'Granddaughter'].includes(rel)) children.push(r);
    else if (['Brother', 'Sister', 'Sibling', 'Brother-in-law', 'Sister-in-law'].includes(rel)) siblings.push(r);
    else if (['Husband', 'Wife', 'Spouse'].includes(rel)) {
      if (!customSpouse) customSpouse = { citizen_id: r.citizen_id, full_name: r.full_name, _rel: rel };
    }
    else others.push(r);
  });

  const root = data.citizen;
  const spouse = data.spouse || customSpouse;
  let html = `<div style="display:flex;flex-direction:column;align-items:center;background:var(--off-white);padding:24px;border-radius:12px;gap:20px;overflow-x:auto;">`;

  if (parents.length) {
    html += `
      <div style="display:flex;flex-direction:column;align-items:center;">
        <div style="font-weight:600;font-size:0.75rem;color:var(--text-muted);text-transform:uppercase;margin-bottom:8px;letter-spacing:0.05em">Parents</div>
        <div style="display:flex;gap:15px">${parents.map(p => personNode(p, p._rel, false, 52)).join('')}</div>
      </div>
      <div style="width:2px;height:20px;background:var(--border);"></div>`;
  }

  html += `<div style="display:flex;align-items:center;gap:30px;flex-wrap:wrap">`;

  if (siblings.length) {
    html += `
      <div style="display:flex;flex-direction:column;align-items:center">
        <div style="font-weight:600;font-size:0.75rem;color:var(--text-muted);text-transform:uppercase;margin-bottom:8px;letter-spacing:0.05em">Siblings</div>
        <div style="display:flex;gap:15px;flex-wrap:wrap">
          ${siblings.map(p => personNode(p, p._rel, false, 50)).join('')}
        </div>
      </div>
      <div style="width:30px;height:2px;background:var(--border)"></div>`;
  }

  html += `
    <div style="display:flex;flex-direction:column;align-items:center">
      <div style="font-weight:600;font-size:0.75rem;color:var(--green);text-transform:uppercase;margin-bottom:8px;letter-spacing:0.05em">Me</div>
      ${personNode(root, null, true, 70)}
    </div>`;

  if (spouse) {
    const spouseRel = spouse._rel || (root.gender === 'Male' ? 'Wife' : 'Husband');
    const spouseId = spouse.spouse_id || spouse.citizen_id;
    const spouseName = spouse.spouse_name || spouse.full_name;
    html += `
      <div style="width:30px;height:2px;background:var(--gold);opacity:0.5"></div>
      <div style="display:flex;flex-direction:column;align-items:center">
        <div style="font-weight:600;font-size:0.75rem;color:var(--text-muted);text-transform:uppercase;margin-bottom:8px;letter-spacing:0.05em">${spouseRel}</div>
        ${personNode({ citizen_id: spouseId, full_name: spouseName, _rel: spouseRel }, spouseRel, false, 50)}
      </div>`;
  }

  html += `</div>`;

  if (children.length) {
    html += `
      <div style="width:2px;height:20px;background:var(--border);"></div>
      <div style="display:flex;flex-direction:column;align-items:center;">
        <div style="font-weight:600;font-size:0.75rem;color:var(--text-muted);text-transform:uppercase;margin-bottom:8px;letter-spacing:0.05em">Children</div>
        <div style="display:flex;gap:15px">${children.map(p => personNode(p, p._rel, false, 52)).join('')}</div>
      </div>`;
  }

  if (others.length) {
    html += `
      <div style="margin-top:20px">
        <div style="font-weight:600;font-size:0.75rem;color:var(--text-muted);text-transform:uppercase;margin-bottom:8px;letter-spacing:0.05em">Others</div>
        <div style="display:flex;gap:15px">${others.map(p => personNode(p, p._rel, false, 48)).join('')}</div>
      </div>`;
  }

  html += `</div>`;
  document.getElementById(targetId).innerHTML = html;
}

function personNode(person, relation, isRoot = false, size = 60) {
  const initials = person.full_name
    ? person.full_name.split(" ").map(n => n[0]).join("").toUpperCase().substring(0,2)
    : "?";
  return `
    <div style="display:flex;flex-direction:column;align-items:center;margin:6px;background:white;padding:12px 18px;border-radius:10px;box-shadow:var(--shadow);min-width:100px;border:1px solid ${isRoot ? 'var(--green)' : 'var(--border)'}">
      <div style="width:${size}px;height:${size}px;border-radius:50%;
        background:${isRoot ? 'var(--green)' : 'var(--green-pale)'};color:${isRoot ? 'white' : 'var(--green)'};
        display:flex;align-items:center;justify-content:center;
        font-weight:bold;font-size:${size / 2.5}px;
        border:${isRoot ? '2px solid rgba(255,255,255,0.2)' : 'none'};">
        ${initials}
      </div>
      <div style="margin-top:10px;font-size:0.8rem;text-align:center;font-weight:600;color:var(--text-mid);white-space:nowrap">${person.full_name || "Unknown"}</div>
      ${relation ? `<div style="font-size:0.7rem;color:var(--text-muted);margin-top:2px;">${relation}</div>` : ""}
    </div>`;
}

async function addRelation() {
  const relCid = document.getElementById("rel-cid").value;
  const relType = document.getElementById("rel-type").value;
  
  if (!relCid || !relType) {
    showMsg("rel-msg", "Please enter a Citizen ID and select a relationship type.", "err");
    return;
  }
  
  showMsg("rel-msg", "Submitting…", "info");
  
  const r = await req("POST", "/citizens/family", {
    related_citizen_id: parseInt(relCid),
    relationship_type: relType
  });

  if (r.ok) {
    document.getElementById("rel-cid").value = "";
    document.getElementById("rel-type").value = "";
    showMsg("rel-msg", r.data.message || "Relationship added successfully.", "ok");
    toast("Family relationship added!", "ok");
    loadFamily(); // refresh list
  } else {
    showMsg("rel-msg", r.data.error || "Failed to add relationship.", "err");
  }
}