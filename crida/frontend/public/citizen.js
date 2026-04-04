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
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data };
}

// ── Panel switching ───────────────────────────────────────────────────────
const _loaded = new Set();

function switchPanel(name, btn) {
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-tab").forEach(b => b.classList.remove("active"));
  document.getElementById("panel-" + name).classList.add("active");
  btn.classList.add("active");

  // Lazy-load once per panel
  if (!_loaded.has(name)) {
    _loaded.add(name);
    if (name === "applications")  loadApplications();
    if (name === "documents")     renderDocButtons();
    if (name === "family")        loadFamilyTree();
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

  const r = await req("POST", "/auth/citizen-login", {
    national_id_number: nid,
    citizen_id: cid
  });

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

function showPortal() {
  document.getElementById("screen-login").style.display  = "none";
  document.getElementById("screen-portal").style.display = "block";
  document.getElementById("header-user").innerHTML = `
    <a href="Landing.html" style="font-size:.75rem;color:var(--text-muted);text-decoration:none;display:flex;align-items:center;gap:5px;margin-right:8px;padding:6px 10px;border:1px solid var(--border);border-radius:6px;transition:all .15s" onmouseover="this.style.borderColor='var(--green)';this.style.color='var(--green)'" onmouseout="this.style.borderColor='var(--border)';this.style.color='var(--text-muted)'"><i class='fas fa-home'></i> Home</a>
    <div class="user-pill">
      <div class="dot"></div>
      <span>${CITIZEN?.full_name || ((CITIZEN?.first_name||"") + " " + (CITIZEN?.last_name||"")).trim() || "Citizen"}</span>
    </div>
    <button onclick="citizenLogout()" class="btn btn-secondary" style="padding:6px 12px;font-size:.76rem">
      <i class="fas fa-sign-out-alt"></i> Logout
    </button>
  `;
  loadProfile();
  loadUnreadCount();
}

function citizenLogout() {
  TOKEN = null; CITIZEN_ID = null; CITIZEN = null;
  sessionStorage.removeItem("crida_citizen_token");
  sessionStorage.removeItem("crida_citizen_id");
  document.getElementById("screen-portal").style.display = "none";
  document.getElementById("screen-login").style.display  = "flex";
  document.getElementById("header-user").innerHTML = "";
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
  div.innerHTML = `<div class="loading"><i class="fas fa-circle-notch"></i>Loading your profile…</div>`;

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
function renderDocButtons() {
  const docs = [
    { name: "CNIC Card",            icon: "fa-id-card",   path: `cnic/${CITIZEN_ID}` },
    { name: "Passport",             icon: "fa-passport",  path: `passport/${CITIZEN_ID}` },
    { name: "Driving License",      icon: "fa-car",       path: `license/${CITIZEN_ID}` },
    { name: "Birth Certificate",    icon: "fa-baby",      path: `birth-certificate/${CITIZEN_ID}` },
    { name: "Marriage Certificate", icon: "fa-heart",     path: `marriage-certificate/${CITIZEN_ID}` },
    { name: "Death Certificate",    icon: "fa-cross",     path: `death-certificate/${CITIZEN_ID}` },
  ];

  document.getElementById("doc-grid").innerHTML = docs.map(d => `
    <div class="doc-card" onclick="downloadPDF('${d.path}','${d.name}')">
      <div class="dc-icon"><i class="fas ${d.icon}"></i></div>
      <div class="dc-name">${d.name}</div>
      <div class="dc-btn"><i class="fas fa-download"></i> Download PDF</div>
    </div>
  `).join("");
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