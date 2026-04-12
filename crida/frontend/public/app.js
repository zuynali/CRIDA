const API = "http://localhost:5000/api/v1";
let TOKEN = localStorage.getItem("crida_token") || null;
let OFFICER = null;

// ── Role-based tab visibility ─────────────────────────────────────────────
function applyRoleVisibility(roleName) {
  document.querySelectorAll("[data-tab][data-roles]").forEach(link => {
    const allowed = link.dataset.roles;
    const visible = allowed === "all" || allowed.split(",").includes(roleName);
    link.style.display = visible ? "" : "none";
  });
}

// ── Tab navigation ────────────────────────────────────────────────────────
document.querySelectorAll("[data-tab]").forEach(link => {
  link.addEventListener("click", e => {
    e.preventDefault();
    const tab = link.dataset.tab;
    document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
    document.querySelectorAll("[data-tab]").forEach(l => l.classList.remove("active"));
    document.getElementById("tab-" + tab).classList.add("active");
    link.classList.add("active");
    document.getElementById("page-title").innerHTML =
      `<i class="${link.querySelector("i").className}"></i> ${link.textContent.trim()}`;
    // Load tab-specific content
    if (tab === "dashboard") loadDashboard();
    else if (tab === "citizens") loadCitizens();
    else if (tab === "applications") loadApplications();
    else if (tab === "doc-applications") loadDocApplications();
    // Add more as needed
  });
});

// ── Toast ─────────────────────────────────────────────────────────────────
function toast(msg, type = "ok") {
  const el = document.createElement("div");
  el.className = "toast " + type;
  el.textContent = msg;
  document.getElementById("toast-container").appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

// ── Theme Toggling ────────────────────────────────────────────────────────
const savedTheme = localStorage.getItem("crida_theme") || "dark";
if(savedTheme === "light") document.documentElement.setAttribute("data-theme", "light");

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "dark";
  const target = current === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", target);
  localStorage.setItem("crida_theme", target);
  
  const icon = document.getElementById("theme-icon");
  if(icon) {
    icon.className = target === "light" ? "fas fa-moon" : "fas fa-sun";
  }
}

window.addEventListener("DOMContentLoaded", () => {
  const icon = document.getElementById("theme-icon");
  if(icon) icon.className = savedTheme === "light" ? "fas fa-moon" : "fas fa-sun";
});

// ── ACID log ──────────────────────────────────────────────────────────────
function acidLog(msg) {
  const log = document.getElementById("acid-log");
  if (!log) return;
  const ts = new Date().toLocaleTimeString();
  log.innerHTML = `[${ts}] ${msg}\n` + log.innerHTML;
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

// ── Login ─────────────────────────────────────────────────────────────────
async function doLogin() {
  const msg = document.getElementById("login-msg");
  msg.className = "msg-box";
  const r = await req("POST", "/auth/login", {
    email: document.getElementById("login-email").value,
    password: document.getElementById("login-pass").value
  });
  if (r.ok) {
    TOKEN = r.data.token;
    OFFICER = r.data.officer;
    localStorage.setItem("crida_token", TOKEN);
    msg.className = "msg-box ok";
    msg.textContent = "Logged in as " + OFFICER.full_name;
    document.getElementById("user-name").textContent = OFFICER.full_name;
    document.getElementById("user-role").textContent = OFFICER.role_name;
    document.getElementById("user-info").classList.remove("hidden");
    applyRoleVisibility(OFFICER.role_name);
    toast("Welcome, " + OFFICER.full_name + "!", "ok");
    document.querySelector("[data-tab='dashboard']").click();
    loadDashboard();
    if (["Admin", "Registrar"].includes(OFFICER.role_name)) {
      loadApplications();
    }
  } else {
    msg.className = "msg-box err";
    msg.textContent = r.data.error || "Login failed";
  }
}

function logout() {
  TOKEN = null; OFFICER = null;
  localStorage.removeItem("crida_token");
  stopBioCamera();
  document.querySelectorAll("[data-tab][data-roles]").forEach(link => {
    link.style.display = "";
  });
  document.querySelector("[data-tab='login']").click();
  document.getElementById("user-info").classList.add("hidden");
  toast("Logged out", "warn");
}

// ── Dashboard ─────────────────────────────────────────────────────────────
async function loadDashboard() {
  try {
    const r = await req("GET", "/citizens/stats");
    if (!r.ok) {
      toast("Failed to load dashboard stats", "err");
      return;
    }
    const stats = r.data || {};

    const renderChart = (canvasId, labels, values, colors) => {
      const canvas = document.getElementById(canvasId);
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      if (!ctx || !labels || !values || !labels.length || !values.some(v => v > 0)) {
        if (canvas.parentElement) {
          canvas.parentElement.innerHTML = `<div style="padding:34px 22px;text-align:center;color:var(--text-muted);font-size:.92rem;">No data available yet.</div>`;
        }
        return;
      }

      const existing = Chart.getChart(canvas);
      if (existing) {
        existing.destroy();
      }

      new Chart(ctx, {
        type: "pie",
        data: {
          labels,
          datasets: [{
            data: values,
            backgroundColor: colors,
            borderWidth: 2,
            borderColor: "#ffffff"
          }]
        },
        options: {
          responsive: true,
          plugins: {
            legend: { position: "bottom" },
            tooltip: { callbacks: { label: (ctx) => `${ctx.label}: ${ctx.parsed}` } }
          }
        }
      });
    };

    renderChart(
      "citizen-status-chart",
      Object.keys(stats.citizen_status || {}),
      Object.values(stats.citizen_status || {}),
      ["#0a5c36", "#c0392b", "#d4860d", "#6b9c80"]
    );
    renderChart(
      "citizen-gender-chart",
      Object.keys(stats.citizen_gender || {}),
      Object.values(stats.citizen_gender || {}),
      ["#16a365", "#0d7a49", "#a0c8b4"]
    );
    renderChart(
      "application-status-chart",
      Object.keys(stats.application_status || {}),
      Object.values(stats.application_status || {}),
      ["#0a6641", "#d4860d", "#c0392b", "#6b9c80"]
    );

    acidLog("Dashboard charts loaded.");
  } catch (e) {
    toast(`Dashboard failed: ${e.message}`, "err");
    document.querySelectorAll("#tab-dashboard .stats-card").forEach(card => {
      if (card) card.innerHTML = `<div style="padding:34px 22px;text-align:center;color:var(--text-muted);font-size:.92rem;">Unable to load dashboard data.</div>`;
    });
  }
}

// ── Citizens ──────────────────────────────────────────────────────────────
async function loadCitizens(search = "") {
  const url = search
    ? `/citizens/?search=${encodeURIComponent(search)}&limit=30`
    : "/citizens/?limit=30";
  const r = await req("GET", url);
  const div = document.getElementById("citizens-table");
  if (!r.ok) { div.innerHTML = `<p style="color:var(--danger)">Error: ${r.data.error}</p>`; return; }
  const rows = r.data.citizens || [];
  if (!rows.length) { div.innerHTML = "<p>No citizens found.</p>"; return; }
  div.innerHTML = `<table>
    <tr><th>ID</th><th>NID</th><th>Name</th><th>DOB</th><th>Gender</th><th>Status</th></tr>
    ${rows.map(c => `<tr>
      <td><code>${c.citizen_id}</code></td>
      <td><code>${c.national_id_number}</code></td>
      <td>${c.full_name}</td>
      <td>${c.dob || "—"}</td>
      <td>${c.gender}</td>
      <td><span class="badge ${c.status === 'active' ? 'success' : 'danger'}">${c.status}</span></td>
    </tr>`).join("")}
  </table>`;
}

async function searchCitizens() {
  await loadCitizens(document.getElementById("citizen-search").value);
}

// ── Applications (Citizen Registration) ──────────────────────────────────
async function loadApplications() {
  const status = document.getElementById("app-status-filter").value;
  const url = status ? `/citizens/applications?status=${status}&limit=50` : "/citizens/applications?limit=50";
  const r = await req("GET", url);
  const div = document.getElementById("applications-table");
  if (!r.ok) { div.innerHTML = `<p style="color:var(--danger)">Error: ${r.data.error}</p>`; return; }
  const apps = r.data.applications || [];
  if (!apps.length) { div.innerHTML = "<p>No applications found.</p>"; return; }
  div.innerHTML = `<table>
    <tr><th>ID</th><th>Name</th><th>DOB</th><th>Gender</th><th>City</th><th>Status</th><th>Submitted</th><th>Actions</th></tr>
    ${apps.map(a => `<tr>
      <td><code>${a.application_id}</code></td>
      <td>${a.first_name} ${a.last_name}</td>
      <td>${a.dob}</td>
      <td>${a.gender}</td>
      <td>${a.city}, ${a.province}</td>
      <td><span class="badge ${a.status === 'Approved' ? 'success' : a.status === 'Rejected' ? 'danger' : 'warning'}">${a.status}</span></td>
      <td>${new Date(a.submission_date).toLocaleDateString()}</td>
      <td>
        ${a.status === 'Pending' ? `
          <button onclick="approveApplication(${a.application_id})" class="btn btn-success btn-sm"><i class="fas fa-check"></i> Approve</button>
          <button onclick="rejectApplication(${a.application_id})" class="btn btn-danger btn-sm"><i class="fas fa-times"></i> Reject</button>
        ` : a.status === 'Approved' ? 'Approved' : 'Rejected'}
      </td>
    </tr>`).join("")}
  </table>`;
}

async function approveApplication(appId) {
  if (!confirm("Approve this application? This will create a citizen record.")) return;
  const r = await req("PUT", `/citizens/applications/${appId}/approve`);
  if (r.ok) {
    toast("Application approved!", "ok");
    loadApplications();
    acidLog(`Application ${appId} approved`);
  } else {
    toast(`Error: ${r.data.error}`, "err");
  }
}

async function rejectApplication(appId) {
  const reason = prompt("Rejection reason:");
  if (!reason) return;
  const r = await req("PUT", `/citizens/applications/${appId}/reject`, { reason });
  if (r.ok) {
    toast("Application rejected!", "ok");
    loadApplications();
    acidLog(`Application ${appId} rejected`);
  } else {
    toast(`Error: ${r.data.error}`, "err");
  }
}

// ── Document Applications (CNIC / Passport / License) ────────────────────
async function loadDocApplications() {
  const role = OFFICER?.role_name || "";
  const div = document.getElementById("doc-applications-table");
  if (!div) return;
  div.innerHTML = `<div style="padding:18px;color:var(--text-muted)"><i class="fas fa-circle-notch fa-spin"></i> Loading…</div>`;

  // Fetch all three types in parallel
  const [cnicR, passR, dlR] = await Promise.all([
    req("GET", "/cnic/?limit=100"),
    req("GET", "/passports/?limit=100"),
    req("GET", "/licenses/?limit=100")
  ]);

  let rows = [];

  // Role-based filtering: Passport_Officer sees passports only,
  // others (Registrar/Admin/License_Officer) see CNIC+DL, Admin sees all.
  const isAdmin          = role === "Admin";
  const isPassportOff    = role === "Passport_Officer";
  const isLicenseOff     = role === "License_Officer";
  const isRegistrar      = role === "Registrar";

  if (cnicR.ok && (isAdmin || isRegistrar)) {
    (cnicR.data.applications || []).forEach(a =>
      rows.push({ ...a, doc_type: "CNIC", app_id: a.application_id, id_field: "application_id" }));
  }
  if (passR.ok && (isAdmin || isPassportOff)) {
    (passR.data.applications || []).forEach(a =>
      rows.push({ ...a, doc_type: "Passport", app_id: a.passport_app_id, id_field: "passport_app_id" }));
  }
  if (dlR.ok && (isAdmin || isLicenseOff || isRegistrar)) {
    (dlR.data.applications || []).forEach(a =>
      rows.push({ ...a, doc_type: "License", app_id: a.dl_app_id, id_field: "dl_app_id" }));
  }

  // Sort newest first
  rows.sort((a, b) => new Date(b.submission_date) - new Date(a.submission_date));

  if (!rows.length) {
    div.innerHTML = "<p style='padding:18px'>No document applications found for your role.</p>";
    return;
  }

  const sc = s => {
    if (!s) return "warning";
    const sl = s.toLowerCase();
    if (sl.includes("approved") || sl.includes("collected")) return "success";
    if (sl.includes("reject")) return "danger";
    return "warning";
  };

  const actionBtns = (a) => {
    const s = a.status;
    const type = a.doc_type.toLowerCase().replace(" ", "");
    const id = a.app_id;
    const cid = a.citizen_id;

    // ── CNIC flow: Pending → Under Review (biometric) → Approved (trigger creates card) ──
    // ── License flow: Pending → Test Scheduled (visit) → Test Passed + Approved (license issued) ──
    // ── Passport flow: Submitted/Under Review → Pending Biometric → Pending Admin Approval → Approved ──
    // Only request a visit if we are at the very beginning of the pipeline
    const canRequestVisit = (
      (type === 'cnic' && s === 'Pending') ||
      (type === 'drivinglicense' && s === 'Pending') ||
      (type === 'passport' && s === 'Submitted')
    );
    const canFinalize = (
      (type === 'cnic' && s === 'Under Review') ||
      (type === 'drivinglicense' && s === 'Test Scheduled') ||
      (type === 'passport' && s === 'Pending Biometric')
    );
    const isAdminFinalStep = (s === 'Pending Admin Approval' && isAdmin);
    const isFinalDone = (s === 'Approved' || s === 'Rejected' || s === 'Test Passed' || s === 'Test Failed');

    if (isFinalDone) {
      return `<span style="font-size:.75rem;color:var(--text-muted)">${s}</span>`;
    }
    if (isAdminFinalStep) {
      return `<button onclick="docFinalApprove('${type}',${id})" class="btn btn-sm btn-success" style="font-size:.72rem">
                <i class="fas fa-check-double"></i> Final Approve
              </button>
              <button onclick="docReject('${type}',${id})" class="btn btn-sm btn-danger" style="font-size:.72rem">
                <i class="fas fa-times"></i> Reject
              </button>`;
    }
    if (s === 'Pending Admin Approval') {
      return `<span style="font-size:.75rem;color:var(--text-muted)"><i class="fas fa-hourglass-half"></i> Awaiting Admin</span>`;
    }
    if (canFinalize && !canRequestVisit) {
      // Officer has already requested the visit — show the finalize step only
      const stepLabel = type === 'drivinglicense' ? 'Issue License' : 'Submit to Admin';
      return `
        <div style="display:flex;flex-direction:column;gap:4px">
          <div style="font-size:.7rem;color:var(--text-muted);margin-bottom:2px">
            <i class="fas fa-info-circle"></i> Citizen visited office. Finalize:
          </div>
          <button onclick="goToBiometric(${cid})" class="btn btn-sm btn-secondary" style="font-size:.72rem;background:var(--green-deep);border-color:var(--green-deep);color:#fff">
            <i class="fas fa-camera"></i> 1. Capture Biometric (Citizen ID: ${cid})
          </button>
          <button onclick="docSubmitToAdmin('${type}',${id})" class="btn btn-sm btn-secondary" style="font-size:.72rem;background:var(--gold);color:#000;border-color:var(--gold)">
            <i class="fas fa-check"></i> 2. Done — ${stepLabel}
          </button>
          <button onclick="docReject('${type}',${id})" class="btn btn-sm btn-danger" style="font-size:.72rem">
            <i class="fas fa-times"></i> Reject
          </button>
        </div>`;
    }
    // Default: first-step — request visit/biometric
    const visitLabel = type === 'drivinglicense' ? '<i class="fas fa-car"></i> Schedule Test Visit' : '<i class="fas fa-fingerprint"></i> Request Biometric';
    return `<button onclick="docRequestBiometric('${type}',${id},${cid})" class="btn btn-sm btn-secondary" style="font-size:.72rem">
              ${visitLabel}
            </button>
            <button onclick="docReject('${type}',${id})" class="btn btn-sm btn-danger" style="font-size:.72rem">
              <i class="fas fa-times"></i> Reject
            </button>`;
  };

  div.innerHTML = `<table style="margin-top:8px">
    <tr><th>Type</th><th>App ID</th><th>Citizen ID</th><th>Citizen Name</th><th>Sub-type</th><th>Submitted</th><th>Status</th><th>Actions</th></tr>
    ${rows.map(a => `<tr>
      <td><span class="badge ${a.doc_type==='CNIC'?'success':a.doc_type==='Passport'?'warning':''}">
            <i class="fas ${a.doc_type==='CNIC'?'fa-id-card':a.doc_type==='Passport'?'fa-passport':'fa-car'}" style="margin-right:4px"></i>${a.doc_type}
          </span></td>
      <td><code>${a.app_id}</code></td>
      <td><code style="color:var(--green)">${a.citizen_id}</code></td>
      <td>${a.citizen_name || '—'}</td>
      <td>${a.application_type || a.license_type || '—'}</td>
      <td>${String(a.submission_date).substring(0,10)}</td>
      <td><span class="badge ${sc(a.status)}">${a.status}</span></td>
      <td style="min-width:220px">${actionBtns(a)}</td>
    </tr>`).join("")}
  </table>`;
}

async function docRequestBiometric(type, id, cid) {
  const endpoints = { cnic: `/cnic/${id}/request-biometric`, passport: `/passports/${id}/request-biometric`, license: `/licenses/${id}/request-biometric` };
  const r = await req("PUT", endpoints[type]);
  if (r.ok) { 
    toast("Biometric requested — citizen will be notified to visit the office!", "ok"); 
    loadDocApplications();
    // Redirect to biometric tab directly and pre-fill the citizen ID
    if (cid) goToBiometric(cid);
  }
  else toast(`Error: ${r.data.error || r.status}`, "err");
}

// Navigate to the Biometric tab and pre-fill the citizen ID so the officer
// can immediately capture the face photo and fingerprint for this application.
function goToBiometric(citizenId) {
  // Switch to the biometric tab
  const bioTab = document.querySelector("[data-tab='biometric']");
  if (bioTab) bioTab.click();

  // Pre-fill the citizen ID field
  setTimeout(() => {
    const cidField = document.getElementById("bio-cid");
    if (cidField) {
      cidField.value = citizenId;
      cidField.dispatchEvent(new Event("input"));
    }
    toast(`Biometric tab opened — Citizen ID ${citizenId} pre-filled. Start the camera and capture face + fingerprint, then return to Doc Applications and click "Done — Submit to Admin".`, "ok");
  }, 200);
}

async function docSubmitToAdmin(type, id) {
  const endpoints = { cnic: `/cnic/${id}/submit-to-admin`, passport: `/passports/${id}/submit-to-admin`, license: `/licenses/${id}/submit-to-admin` };
  const r = await req("PUT", endpoints[type]);
  if (r.ok) { toast("Submitted to Admin for final approval!", "ok"); loadDocApplications(); }
  else toast(`Error: ${r.data.error || r.status}`, "err");
}

async function docFinalApprove(type, id) {
  if (!confirm("Grant FINAL approval? This will issue the document and make it downloadable for the citizen.")) return;
  const endpoints = {
    cnic:     `/cnic/${id}/approve`,
    passport: `/passports/${id}/approve`,
    license:  `/licenses/${id}/issue`
  };
  const method = type === "license" ? "POST" : "PUT";
  const r = await req(method, endpoints[type]);
  if (r.ok) { toast("Document approved and issued!", "ok"); loadDocApplications(); acidLog(`Doc ${type.toUpperCase()} #${id} — FINAL APPROVED`); }
  else toast(`Error: ${r.data.error || r.status}`, "err");
}

async function docReject(type, id) {
  const reason = prompt("Rejection reason:");
  if (!reason) return;
  const endpoints = { cnic: `/cnic/${id}/reject`, passport: `/passports/${id}/reject`, license: `/licenses/${id}/reject` };
  const r = await req("PUT", endpoints[type], { reason });
  if (r.ok) { toast("Application rejected", "warn"); loadDocApplications(); }
  else toast(`Error: ${r.data.error || r.status}`, "err");
}



// ── PDF ───────────────────────────────────────────────────────────────────
async function generatePDF() {
  const type = document.getElementById("pdf-type").value;
  const id = document.getElementById("pdf-id").value;
  const msg = document.getElementById("pdf-msg");
  msg.className = "msg-box";
  try {
    const blob = await req("GET", `/pdf/${type}/${id}`, null, true);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${type}_${id}.pdf`; a.click();
    msg.className = "msg-box ok";
    msg.textContent = `PDF downloaded: ${type}_${id}.pdf`;
    acidLog(`PDF generated: ${type} for ID ${id}`);
    toast("PDF downloaded!", "ok");
  } catch (e) {
    msg.className = "msg-box err";
    msg.textContent = "PDF failed: " + e.message;
  }
}

// ── Family Tree ───────────────────────────────────────────────────────────
async function loadFamilyTree() {
  const cid = document.getElementById('family-cid').value;
  if (!cid) { alert("Enter Citizen ID"); return; }
  try {
    const r = await req("GET", `/family-tree/${cid}`);
    if (!r.ok) throw new Error(r.data.error || "Failed");
    renderTree(r.data);
  } catch (e) {
    document.getElementById('family-result').innerHTML =
      `<div style="color:red;">Error: ${e.message}</div>`;
  }
}

function renderTree(data) {
  _treeData = data;
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
  let html = `<div class="ft-tree">`;

  if (parents.length) {
    html += `
      <div class="ft-row-wrap">
        <div class="ft-section-label">Parents</div>
        <div class="ft-row">${parents.map(p => personNode(p, p._rel, false, 52)).join('')}</div>
      </div>
      <div class="ft-vline" style="height:30px;background:#85B7EB"></div>`;
  }

  html += `<div class="ft-row" style="align-items:center;gap:30px;flex-wrap:wrap">`;

  if (siblings.length) {
    html += `
      <div style="display:flex;flex-direction:column;align-items:center">
        <div class="ft-section-label">Siblings</div>
        <div style="display:flex;gap:12px;flex-wrap:wrap">
          ${siblings.map(p => personNode(p, p._rel, false, 50)).join('')}
        </div>
      </div>
      <div style="width:25px;height:2px;background:#ccc"></div>`;
  }

  html += `
    <div style="display:flex;flex-direction:column;align-items:center">
      <div class="ft-root-label">Root</div>
      ${personNode(root, null, true, 70)}
    </div>`;

  if (spouse) {
    const spouseRel = spouse._rel || (root.gender === 'Male' ? 'Wife' : 'Husband');
    const spouseId = spouse.spouse_id || spouse.citizen_id;
    const spouseName = spouse.spouse_name || spouse.full_name;
    html += `
      <div style="width:25px;height:2px;background:#EF9F27"></div>
      <div style="display:flex;flex-direction:column;align-items:center">
        <div class="ft-section-label">${spouseRel}</div>
        ${personNode({ citizen_id: spouseId, full_name: spouseName, _rel: spouseRel }, spouseRel, false, 50)}
      </div>`;
  }

  html += `</div>`;

  if (children.length) {
    html += `
      <div class="ft-vline" style="height:30px;background:#97C459"></div>
      <div class="ft-row-wrap">
        <div class="ft-section-label">Children</div>
        <div class="ft-row">${children.map(p => personNode(p, p._rel, false, 52)).join('')}</div>
      </div>`;
  }

  if (others.length) {
    html += `
      <div style="margin-top:20px">
        <div class="ft-section-label">Others</div>
        <div class="ft-row">${others.map(p => personNode(p, p._rel, false, 48)).join('')}</div>
      </div>`;
  }

  html += `</div>`;
  document.getElementById('family-result').innerHTML = html;
}

function personNode(person, relation, isRoot = false, size = 60) {
  const initials = person.full_name
    ? person.full_name.split(" ").map(n => n[0]).join("").toUpperCase()
    : "?";
  return `
    <div style="display:flex;flex-direction:column;align-items:center;margin:6px;">
      <div style="width:${size}px;height:${size}px;border-radius:50%;
        background:${isRoot ? '#4CAF50' : '#2C3E50'};color:white;
        display:flex;align-items:center;justify-content:center;
        font-weight:bold;font-size:${size / 3}px;
        border:${isRoot ? '3px solid #FFD700' : '2px solid #555'};">
        ${initials}
      </div>
      <div style="margin-top:6px;font-size:12px;text-align:center">${person.full_name || "Unknown"}</div>
      ${relation ? `<div style="font-size:10px;color:#aaa;margin-top:2px;">${relation}</div>` : ""}
    </div>`;
}

// ── Criminal Records ──────────────────────────────────────────────────────
async function loadCriminalRecords() {
  const cid = document.getElementById("criminal-cid").value;
  const url = cid ? `/security/criminal-records?citizen_id=${cid}` : "/security/criminal-records";
  const r = await req("GET", url);
  const div = document.getElementById("criminal-table");
  const rows = r.data.records || [];
  if (!rows.length) { div.innerHTML = "<p>No records found.</p>"; return; }
  div.innerHTML = `<table>
    <tr><th>Record ID</th><th>Case No</th><th>Citizen</th><th>Offense</th><th>Date</th><th>Status</th><th>Court</th></tr>
    ${rows.map(rec => `<tr>
      <td><code>${rec.record_id}</code></td>
      <td>${rec.case_number || "—"}</td>
      <td>${rec.citizen_name}</td>
      <td>${rec.offense}</td>
      <td>${String(rec.offense_date).substring(0, 10)}</td>
      <td><span class="badge ${rec.status === 'Convicted' ? 'danger' : rec.status === 'Acquitted' ? 'success' : 'warning'}">${rec.status}</span></td>
      <td>${rec.court_name || "—"}</td>
    </tr>`).join("")}
  </table>`;
}

function showAddCriminal() {
  const f = document.getElementById("add-criminal-form");
  f.style.display = f.style.display === "none" ? "block" : "none";
}

async function addCriminalRecord() {
  const r = await req("POST", "/security/criminal-records", {
    citizen_id: parseInt(document.getElementById("cr-cid").value),
    case_number: document.getElementById("cr-case").value,
    offense: document.getElementById("cr-offense").value,
    offense_date: document.getElementById("cr-date").value,
    status: document.getElementById("cr-status").value,
    court_name: document.getElementById("cr-court").value
  });
  if (r.ok) {
    toast("Criminal record added", "ok");
    acidLog(`CRIMINAL_RECORD ${r.data.record_id} added — ACID: INSERT + Audit_Log COMMIT`);
    loadCriminalRecords();
  } else toast("Error: " + r.data.error, "err");
}

// ── Watchlist ─────────────────────────────────────────────────────────────
async function loadWatchlist() {
  const r = await req("GET", "/security/watchlist");
  const div = document.getElementById("watchlist-table");
  if (!r.ok) { div.innerHTML = `<p style="color:var(--text-muted)">Requires Security Officer or Admin role.</p>`; return; }
  const rows = r.data.watchlist || [];
  if (!rows.length) { div.innerHTML = "<p style='margin-top:12px'>Watchlist is empty.</p>"; return; }
  div.innerHTML = `<table style="margin-top:14px">
    <tr><th>ID</th><th>Citizen</th><th>Type</th><th>Reason</th><th>Added</th><th>Expiry</th></tr>
    ${rows.map(w => `<tr>
      <td><code>${w.watchlist_id}</code></td>
      <td>${w.citizen_name} (${w.citizen_id})</td>
      <td><span class="badge warning">${w.watchlist_type}</span></td>
      <td>${w.reason}</td>
      <td>${String(w.added_date).substring(0, 10)}</td>
      <td>${w.expiry_date ? String(w.expiry_date).substring(0, 10) : "—"}</td>
    </tr>`).join("")}
  </table>`;
}

function showAddWatchlist() {
  const f = document.getElementById("add-watchlist-form");
  f.style.display = f.style.display === "none" ? "block" : "none";
}

async function addToWatchlist() {
  const expiry = document.getElementById("wl-expiry").value || undefined;
  const r = await req("POST", "/security/watchlist", {
    citizen_id: parseInt(document.getElementById("wl-cid").value),
    reason: document.getElementById("wl-reason").value,
    watchlist_type: document.getElementById("wl-type").value,
    ...(expiry ? { expiry_date: expiry } : {})
  });
  if (r.ok) {
    toast("Added to watchlist", "ok");
    acidLog(`WATCHLIST entry ${r.data.watchlist_id} added`);
    loadWatchlist();
  } else toast("Error: " + r.data.error, "err");
}

// ── Update Requests ───────────────────────────────────────────────────────
async function submitUpdateRequest() {
  const r = await req("POST", "/update-requests/", {
    citizen_id: parseInt(document.getElementById("upd-cid").value),
    field_name: document.getElementById("upd-field").value,
    new_value: document.getElementById("upd-value").value,
    reason: document.getElementById("upd-reason").value
  });
  if (r.ok) {
    toast("Update request submitted (Pending)", "ok");
    acidLog("UPDATE_REQUEST submitted — awaiting officer approval");
    loadUpdateRequests();
  } else toast("Error: " + r.data.error, "err");
}

async function loadUpdateRequests() {
  const r = await req("GET", "/update-requests/?status=Pending");
  const div = document.getElementById("update-table");
  const rows = r.data.requests || [];
  if (!rows.length) { div.innerHTML = "<p style='margin-top:12px'>No pending requests.</p>"; return; }
  div.innerHTML = `<table style="margin-top:14px">
    <tr><th>ID</th><th>Citizen</th><th>Field</th><th>Old</th><th>New</th><th>Status</th><th>Actions</th></tr>
    ${rows.map(r => `<tr>
      <td><code>${r.request_id}</code></td>
      <td>${r.citizen_name}</td>
      <td><code>${r.field_name}</code></td>
      <td>${r.old_value || "—"}</td>
      <td><strong>${r.new_value}</strong></td>
      <td><span class="badge warning">${r.status}</span></td>
      <td>
        <button onclick="approveRequest(${r.request_id})" class="btn btn-sm btn-success">&#10003; Approve</button>
        <button onclick="rejectRequest(${r.request_id})"  class="btn btn-sm btn-danger">&#10005; Reject</button>
      </td>
    </tr>`).join("")}
  </table>`;
}

async function approveRequest(rid) {
  const r = await req("PUT", `/update-requests/${rid}/approve`);
  if (r.ok) {
    toast("Request approved!", "ok");
    acidLog(`UPDATE_REQUEST ${rid} APPROVED → Citizen UPDATE + Audit_Log — COMMIT`);
    loadUpdateRequests();
  } else toast("Error: " + r.data.error, "err");
}

async function rejectRequest(rid) {
  const r = await req("PUT", `/update-requests/${rid}/reject`, { reason: "Rejected by officer" });
  if (r.ok) { toast("Request rejected", "warn"); loadUpdateRequests(); }
  else toast("Error: " + r.data.error, "err");
}

// ── Camera ────────────────────────────────────────────────────────────────
let cameraStream = null;

async function startCamera() {
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({ video: true });
    document.getElementById("cam-video").srcObject = cameraStream;
    toast("Camera started", "ok");
  } catch (e) { toast("Camera error: " + e.message, "err"); }
}

async function capturePhoto() {
  const video = document.getElementById("cam-video");
  const canvas = document.getElementById("cam-canvas");
  canvas.getContext("2d").drawImage(video, 0, 0, 320, 240);
  const base64 = canvas.toDataURL("image/jpeg");
  const cid = document.getElementById("cam-cid").value;
  const r = await req("POST", "/camera/capture", { citizen_id: parseInt(cid), image: base64 });
  const div = document.getElementById("cam-result");
  if (r.ok) {
    div.innerHTML = `<div class="msg-box ok" style="display:block;margin-top:10px">
      Photo captured!<br>
      Faces detected: ${r.data.face_count ?? "N/A"}<br>
      Background removed: ${r.data.bg_removed ? "Yes" : "No (library not installed)"}<br>
      Path: <code>${r.data.path}</code>
    </div>`;
    acidLog(`PHOTO captured for citizen ${cid} — stored in Document table`);
  } else {
    div.innerHTML = `<div class="msg-box err" style="display:block;margin-top:10px">${r.data.error}</div>`;
  }
}

// ── Biometric ─────────────────────────────────────────────────────────────
let bioStream = null;

async function startBioCamera() {
  try {
    bioStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" }
    });
    const video = document.getElementById("bio-video");
    video.srcObject = bioStream;
    video.style.display = "block";

    const btn = document.getElementById("bio-cam-btn");
    btn.innerHTML = `<i class="fas fa-video-slash"></i> Stop Camera`;
    btn.onclick = stopBioCamera;
    btn.classList.replace("btn-secondary", "btn-danger");

    document.getElementById("bio-verify-face-btn").disabled = false;
    document.getElementById("bio-enroll-btn").disabled = false;
    document.getElementById("bio-enroll-fp-btn").disabled = false;
    document.getElementById("bio-verify-fp-btn").disabled = false;
    toast("Camera started", "ok");
    acidLog(`BIO camera started for citizen ${document.getElementById("bio-cid").value || "?"}`);
  } catch (e) {
    toast("Camera error: " + e.message, "err");
  }
}

function stopBioCamera() {
  if (bioStream) { bioStream.getTracks().forEach(t => t.stop()); bioStream = null; }
  const video = document.getElementById("bio-video");
  if (video) { video.srcObject = null; video.style.display = "none"; }

  const btn = document.getElementById("bio-cam-btn");
  if (btn) {
    btn.innerHTML = `<i class="fas fa-video"></i> Start Camera`;
    btn.onclick = startBioCamera;
    btn.classList.replace("btn-danger", "btn-secondary");
  }
  const vfBtn = document.getElementById("bio-verify-face-btn");
  if (vfBtn) vfBtn.disabled = true;
  const enrBtn = document.getElementById("bio-enroll-btn");
  if (enrBtn) enrBtn.disabled = true;
  const fpEnrBtn = document.getElementById("bio-enroll-fp-btn");
  if (fpEnrBtn) fpEnrBtn.disabled = true;
  const fpVerBtn = document.getElementById("bio-verify-fp-btn");
  if (fpVerBtn) fpVerBtn.disabled = true;
}

// Full-frame capture — used for face enroll/verify
async function captureFrame() {
  const video = document.getElementById("bio-video");
  if (!video.videoWidth || !video.videoHeight) return null;

  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0);

  const base64 = canvas.toDataURL("image/jpeg", 0.92);
  if (base64.length < 5000) return null;

  const blob = await new Promise(res => canvas.toBlob(res, "image/jpeg", 0.92));
  const buf = await blob.arrayBuffer();
  const raw = await crypto.subtle.digest("SHA-256", buf);
  const hash = Array.from(new Uint8Array(raw))
    .map(b => b.toString(16).padStart(2, "0")).join("");

  return { base64, hash };
}

// Finger-zone crop capture — used for fingerprint enroll/verify
// Crops the centre 40% width x 60% height of the frame where the
// overlay box guides the officer to place the finger.
async function captureFingerFrame() {
  const video = document.getElementById("bio-video");
  if (!video.videoWidth || !video.videoHeight) return null;

  const vw = video.videoWidth;
  const vh = video.videoHeight;

  // Crop region matches the overlay box drawn in drawFingerprintOverlay()
  const cropW = Math.floor(vw * 0.40);
  const cropH = Math.floor(vh * 0.60);
  const cropX = Math.floor((vw - cropW) / 2);
  const cropY = Math.floor((vh - cropH) / 2);

  const canvas = document.createElement("canvas");
  canvas.width = cropW;
  canvas.height = cropH;
  canvas.getContext("2d").drawImage(video, cropX, cropY, cropW, cropH, 0, 0, cropW, cropH);

  const base64 = canvas.toDataURL("image/jpeg", 0.95);   // higher quality for ridges
  if (base64.length < 2000) return null;

  const blob = await new Promise(res => canvas.toBlob(res, "image/jpeg", 0.95));
  const buf = await blob.arrayBuffer();
  const raw = await crypto.subtle.digest("SHA-256", buf);
  const hash = Array.from(new Uint8Array(raw))
    .map(b => b.toString(16).padStart(2, "0")).join("");

  return { base64, hash };
}

// Draws a semi-transparent finger-zone overlay on top of the video.
// Called on an animation loop while the fingerprint mode is active.
let _fpOverlayActive = false;
let _fpOverlayCanvas = null;

function startFingerprintOverlay() {
  const video = document.getElementById("bio-video");
  if (_fpOverlayCanvas) return;   // already running

  _fpOverlayCanvas = document.createElement("canvas");
  _fpOverlayCanvas.style.position = 'absolute';
  _fpOverlayCanvas.style.top = video.offsetTop + 'px';
  _fpOverlayCanvas.style.left = video.offsetLeft + 'px';
  _fpOverlayCanvas.style.width = video.offsetWidth + 'px';
  _fpOverlayCanvas.style.height = video.offsetHeight + 'px';
  _fpOverlayCanvas.style.pointerEvents = 'none';
  _fpOverlayCanvas.style.borderRadius = '6px';
  video.parentElement.style.position = "relative";
  video.parentElement.appendChild(_fpOverlayCanvas);
  _fpOverlayActive = true;
  drawFingerprintOverlay();
}

function stopFingerprintOverlay() {
  _fpOverlayActive = false;
  if (_fpOverlayCanvas) {
    _fpOverlayCanvas.remove();
    _fpOverlayCanvas = null;
  }
}

function drawFingerprintOverlay() {
  if (!_fpOverlayActive || !_fpOverlayCanvas) return;

  const video = document.getElementById("bio-video");
  const c = _fpOverlayCanvas;
  c.width = video.offsetWidth || 320;
  c.height = video.offsetHeight || 240;

  const ctx = c.getContext("2d");
  ctx.clearRect(0, 0, c.width, c.height);

  // Darken everything outside the crop zone
  const bx = c.width * 0.30;
  const by = c.height * 0.20;
  const bw = c.width * 0.40;
  const bh = c.height * 0.60;

  ctx.fillStyle = "rgba(0,0,0,0.55)";
  ctx.fillRect(0, 0, c.width, c.height);   // full dark
  ctx.clearRect(bx, by, bw, bh);             // cut out the finger zone

  // Bright border around the finger zone
  ctx.strokeStyle = "#00e5ff";
  ctx.lineWidth = 2;
  ctx.strokeRect(bx, by, bw, bh);

  // Corner tick marks
  const t = 14;
  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = 3;
  [[bx, by], [bx + bw, by], [bx, by + bh], [bx + bw, by + bh]].forEach(([x, y], i) => {
    const sx = i % 2 === 0 ? 1 : -1;
    const sy = i < 2 ? 1 : -1;
    ctx.beginPath(); ctx.moveTo(x, y + sy * t); ctx.lineTo(x, y); ctx.lineTo(x + sx * t, y); ctx.stroke();
  });

  // Label
  ctx.fillStyle = "#00e5ff";
  ctx.font = "bold 11px monospace";
  ctx.fillText("PLACE FINGER HERE", bx + 8, by - 6);

  requestAnimationFrame(drawFingerprintOverlay);
}

async function enrollBiometric() {
  const cid = parseInt(document.getElementById("bio-cid").value);
  const fp = (document.getElementById("bio-enroll-fp")?.value || "").trim();
  const div = document.getElementById("bio-result");

  if (!cid) { toast("Enter a Citizen ID", "err"); return; }
  if (!bioStream) { toast("Start the camera first — a live photo is required to enroll a face", "warn"); return; }

  div.innerHTML = `<div class="msg-box" style="display:block;margin-top:10px">⏳ Capturing face…</div>`;

  const frame = await captureFrame();
  if (!frame) {
    toast("Camera frame is empty — check lighting and try again", "err");
    div.innerHTML = `<div class="msg-box err" style="display:block;margin-top:10px">
      ❌ Could not capture a usable frame. Ensure good lighting and face the camera directly.
    </div>`;
    return;
  }

  div.innerHTML = `<div class="msg-box" style="display:block;margin-top:10px">⏳ Saving face photo…</div>`;

  try {
    const photoResp = await req("POST", "/biometric/upload-photo", {
      citizen_id: cid,
      image: frame.base64
    });

    if (!photoResp.ok) {
      const msg = photoResp.data?.error || `HTTP ${photoResp.status}`;
      div.innerHTML = `<div class="msg-box err" style="display:block;margin-top:10px">❌ Photo save failed: ${msg}</div>`;
      toast("Photo save failed", "err");
      return;
    }
  } catch (e) {
    div.innerHTML = `<div class="msg-box err" style="display:block;margin-top:10px">❌ Network error saving photo: ${e.message}</div>`;
    toast("Network error", "err");
    return;
  }

  div.innerHTML = `<div class="msg-box" style="display:block;margin-top:10px">⏳ Storing biometric hash…</div>`;

  try {
    const bioResp = await req("POST", "/biometric/enroll", {
      citizen_id: cid,
      fingerprint_hash: fp,
      facial_scan_hash: frame.hash
    });

    if (bioResp.ok) {
      toast("Biometric enrolled ✓", "ok");
      acidLog(`BIOMETRIC enrolled for citizen ${cid} | facial hash: ${frame.hash.substring(0, 16)}…`);
      div.innerHTML = `<div class="msg-box ok" style="display:block;margin-top:10px">
        ✅ ${bioResp.data.message}<br>
        <small>
          Face photo saved to Documents table.<br>
          Facial hash: <code>${frame.hash.substring(0, 24)}…</code><br>
          ${fp ? `Fingerprint hash stored: <code>${fp.substring(0, 24)}…</code>` : "No fingerprint enrolled."}
        </small>
      </div>`;
    } else {
      toast("Biometric enroll error: " + bioResp.data.error, "err");
      div.innerHTML = `<div class="msg-box err" style="display:block;margin-top:10px">❌ ${bioResp.data.error}</div>`;
    }
  } catch (e) {
    toast("Network error: " + e.message, "err");
    div.innerHTML = `<div class="msg-box err" style="display:block;margin-top:10px">❌ Network error: ${e.message}</div>`;
  }
}

// ── FINGERPRINT ENROLL (camera-based) ────────────────────────────────────
// Point camera at finger → captures image → saves to Document table as
// document_type='fingerprint_photo' → stores SHA-256 hash in fingerprint_hash
async function enrollFingerprint() {
  const cid = parseInt(document.getElementById("bio-cid").value);
  const div = document.getElementById("bio-result");
  if (!cid) { toast("Enter a Citizen ID", "err"); return; }
  if (!bioStream) { toast("Start the camera and point it at the finger", "warn"); return; }

  startFingerprintOverlay();
  div.innerHTML = `<div class="msg-box" style="display:block;margin-top:10px">
    📷 Place finger flat inside the <strong>blue box</strong> on the camera…<br>
    ⏳ Capturing in 3 seconds…
  </div>`;

  await new Promise(r => setTimeout(r, 3000));

  const frame = await captureFingerFrame();
  stopFingerprintOverlay();
  if (!frame) {
    toast("Camera frame is empty — check lighting", "err");
    div.innerHTML = `<div class="msg-box err" style="display:block;margin-top:10px">
      ❌ Could not capture a usable frame. Ensure good lighting and hold the finger steady inside the blue box.
    </div>`;
    return;
  }

  div.innerHTML = `<div class="msg-box" style="display:block;margin-top:10px">⏳ Saving fingerprint photo…</div>`;

  // Save image to Document table (document_type = 'fingerprint_photo' stored via supporting_doc)
  try {
    const photoResp = await req("POST", "/biometric/upload-fingerprint", {
      citizen_id: cid,
      image: frame.base64
    });
    if (!photoResp.ok) {
      const msg = photoResp.data?.error || `HTTP ${photoResp.status}`;
      div.innerHTML = `<div class="msg-box err" style="display:block;margin-top:10px">❌ Photo save failed: ${msg}</div>`;
      toast("Photo save failed", "err");
      return;
    }
  } catch (e) {
    div.innerHTML = `<div class="msg-box err" style="display:block;margin-top:10px">❌ Network error: ${e.message}</div>`;
    return;
  }

  div.innerHTML = `<div class="msg-box" style="display:block;margin-top:10px">⏳ Storing fingerprint hash…</div>`;

  // Store SHA-256 of image in Biometric_Data.fingerprint_hash
  try {
    const bioResp = await req("POST", "/biometric/enroll", {
      citizen_id: cid,
      fingerprint_hash: frame.hash,
      facial_scan_hash: ""
    });
    if (bioResp.ok) {
      toast("Fingerprint enrolled ✓", "ok");
      acidLog(`BIOMETRIC fingerprint enrolled for citizen ${cid} | hash: ${frame.hash.substring(0, 16)}…`);
      div.innerHTML = `<div class="msg-box ok" style="display:block;margin-top:10px">
        ✅ ${bioResp.data.message}<br>
        <small>
          Fingerprint photo saved to Documents table.<br>
          Hash: <code>${frame.hash.substring(0, 24)}…</code>
        </small>
      </div>`;
    } else {
      div.innerHTML = `<div class="msg-box err" style="display:block;margin-top:10px">❌ ${bioResp.data.error}</div>`;
    }
  } catch (e) {
    div.innerHTML = `<div class="msg-box err" style="display:block;margin-top:10px">❌ Network error: ${e.message}</div>`;
  }
}

// ── FINGERPRINT VERIFY (camera-based image matching) ─────────────────────
// Point camera at finger → captures image → backend does OpenCV ORB matching
// against stored fingerprint photo (same algorithm as face verify)
async function verifyFingerprint() {
  const cid = parseInt(document.getElementById("bio-cid").value);
  if (!cid) { toast("Enter a Citizen ID", "err"); return; }
  if (!bioStream) { toast("Start the camera and point it at the finger", "warn"); return; }

  const video = document.getElementById("bio-video");
  if (!video.videoWidth || !video.videoHeight) {
    toast("Camera not ready — wait a moment", "warn"); return;
  }

  const div = document.getElementById("bio-result");
  startFingerprintOverlay();
  div.innerHTML = `<div class="msg-box" style="display:block;margin-top:10px">
    📷 Place the <strong>same finger</strong> flat inside the <strong>blue box</strong> (same angle as enrollment)…<br>
    ⏳ Capturing in 3 seconds…
  </div>`;

  await new Promise(r => setTimeout(r, 3000));

  const frame = await captureFingerFrame();
  stopFingerprintOverlay();
  if (!frame) { toast("Camera frame empty — check lighting", "err"); return; }

  try {
    const r = await req("POST", "/biometric/verify-fingerprint-image", {
      citizen_id: cid,
      image: frame.base64
    });

    if (!r.ok) {
      div.innerHTML = `<div class="msg-box err" style="display:block;margin-top:10px">
        <strong>Error:</strong> ${r.data.error || "Unknown error"}
        ${r.status === 404 ? `<br><small>→ Enroll this citizen's fingerprint first (camera must be on).</small>` : ""}
        ${r.status === 501 ? `<br><small>→ Run: <code>pip install opencv-python</code> in your backend venv.</small>` : ""}
      </div>`;
      toast("Fingerprint verify failed: " + (r.data.error || r.status), "err");
      return;
    }

    const v = r.data.verified;
    const conf = r.data.confidence != null ? `${r.data.confidence}%` : "—";
    const note = r.data.note ? `<br><small style="color:var(--text-muted)">${r.data.note}</small>` : "";
    const reason = r.data.reason ? `<br><small>${r.data.reason}</small>` : "";

    div.innerHTML = `<div class="msg-box ${v ? "ok" : "err"}" style="display:block;margin-top:10px">
      Fingerprint: <strong>${v ? "✅ VERIFIED" : "❌ NOT MATCHED"}</strong>
      &nbsp;| Confidence: <strong>${conf}</strong>
      &nbsp;| Method: ${r.data.method}
      ${reason}${note}
    </div>`;

    toast(v ? "Fingerprint verified!" : "Fingerprint not matched", v ? "ok" : "err");
    acidLog(`BIOMETRIC fp verify citizen ${cid}: ${v ? "MATCH" : "NO MATCH"} (${conf}) via ${r.data.method}`);

  } catch (e) {
    div.innerHTML = `<div class="msg-box err" style="display:block;margin-top:10px">
      <strong>Network error</strong> — is the Flask backend running?<br>
      <small>${e.message}</small>
    </div>`;
    toast("Network error: " + e.message, "err");
  }
}

async function verifyFace() {
  const cid = parseInt(document.getElementById("bio-cid").value);
  if (!cid) { toast("Enter a Citizen ID", "err"); return; }
  if (!bioStream) { toast("Start the camera first", "err"); return; }

  const video = document.getElementById("bio-video");
  if (!video.videoWidth || !video.videoHeight) {
    toast("Camera not ready yet — wait a moment and try again", "warn");
    return;
  }

  const frame = await captureFrame();
  if (!frame) {
    toast("Camera frame appears empty — check lighting", "err");
    return;
  }

  const div = document.getElementById("bio-result");
  div.innerHTML = `<div class="msg-box" style="display:block;margin-top:10px">
    ⏳ Verifying face… (this may take 2–5 seconds)
  </div>`;

  try {
    const r = await req("POST", "/biometric/verify-face", {
      citizen_id: cid,
      image: frame.base64
    });

    if (!r.ok) {
      div.innerHTML = `<div class="msg-box err" style="display:block;margin-top:10px">
        <strong>Error:</strong> ${r.data.error || "Unknown error"}
        ${r.status === 404 ? `<br><small>→ Enroll this citizen's face first (camera must be on).</small>` : ""}
        ${r.status === 501 ? `<br><small>→ Run: <code>pip install opencv-python</code> in your backend venv.</small>` : ""}
      </div>`;
      toast("Face verify failed: " + (r.data.error || r.status), "err");
      return;
    }

    const v = r.data.verified;
    const conf = r.data.confidence != null ? `${r.data.confidence}%` : "—";
    const note = r.data.note ? `<br><small style="color:var(--text-muted)">${r.data.note}</small>` : "";
    const reason = r.data.reason ? `<br><small>${r.data.reason}</small>` : "";

    div.innerHTML = `<div class="msg-box ${v ? "ok" : "err"}" style="display:block;margin-top:10px">
      Face: <strong>${v ? "✅ VERIFIED" : "❌ NOT MATCHED"}</strong>
      &nbsp;| Confidence: <strong>${conf}</strong>
      &nbsp;| Method: ${r.data.method}
      ${reason}${note}
    </div>`;

    toast(v ? "Face verified!" : "Face not matched", v ? "ok" : "err");
    acidLog(`BIOMETRIC face verify citizen ${cid}: ${v ? "MATCH" : "NO MATCH"} (${conf}) via ${r.data.method}`);

  } catch (e) {
    div.innerHTML = `<div class="msg-box err" style="display:block;margin-top:10px">
      <strong>Network error</strong> — is the Flask backend running?<br>
      <small>${e.message}</small>
    </div>`;
    toast("Network error: " + e.message, "err");
  }
}

async function bioDebug(citizenId) {
  const r = await req("GET", `/biometric/debug/${citizenId}`);
  console.table(r.data);
  const div = document.getElementById("bio-result");
  div.innerHTML = `<div class="msg-box" style="display:block;margin-top:10px;font-family:monospace;font-size:0.78rem">
    <strong>Debug — Citizen ${citizenId}</strong><br>
    Photo in DB:   <code>${r.data.photo?.db_path || "none"}</code><br>
    Resolved path: <code>${r.data.photo?.resolved || "—"}</code><br>
    File exists:   <strong>${r.data.photo?.exists ?? "—"}</strong>
    &nbsp; Size: ${r.data.photo?.size_bytes ? (r.data.photo.size_bytes / 1024).toFixed(1) + " KB" : "—"}<br>
    Biometric row: ${r.data.biometric_row ? "✅ Yes" : "❌ No"}<br>
    FP hash:       <code>${r.data.biometric_row?.fingerprint_hash?.substring(0, 20) || "—"}…</code><br>
    Facial hash:   <code>${r.data.biometric_row?.facial_scan_hash?.substring(0, 20) || "—"}…</code><br>
    Uploads dir:   <code>${r.data.uploads_dir}</code>
  </div>`;
}

// ── Complaints ────────────────────────────────────────────────────────────
async function submitComplaint() {
  const r = await req("POST", "/complaints/", {
    citizen_id: parseInt(document.getElementById("comp-cid").value),
    subject: document.getElementById("comp-subject").value,
    description: document.getElementById("comp-desc").value
  });
  if (r.ok) { toast("Complaint submitted", "ok"); loadComplaints(); }
  else toast("Error: " + r.data.error, "err");
}

async function loadComplaints() {
  const r = await req("GET", "/complaints/");
  const div = document.getElementById("complaints-table");
  const rows = r.data.complaints || [];
  if (!rows.length) { div.innerHTML = "<p style='margin-top:12px'>No complaints.</p>"; return; }
  div.innerHTML = `<table style="margin-top:14px">
    <tr><th>ID</th><th>Citizen</th><th>Subject</th><th>Status</th><th>Created</th></tr>
    ${rows.map(c => `<tr>
      <td><code>${c.complaint_id}</code></td>
      <td>${c.citizen_id}</td>
      <td>${c.subject}</td>
      <td><span class="badge ${c.status === 'Resolved' || c.status === 'Closed' ? 'success' : 'warning'}">${c.status}</span></td>
      <td>${String(c.created_at).substring(0, 10)}</td>
    </tr>`).join("")}
  </table>`;
}

// ── Notifications ─────────────────────────────────────────────────────────
async function loadUnreadCount() {
  const cid = document.getElementById("notif-cid").value;
  const url = cid ? `/notifications/unread-count?citizen_id=${cid}` : "/notifications/unread-count";
  const r = await req("GET", url);
  document.getElementById("notif-count").innerHTML =
    `<span class="badge warning">Unread: ${r.data.unread_count ?? 0}</span>`;
}

async function loadNotifications() {
  const cid = document.getElementById("notif-cid").value;
  const unread = document.getElementById("notif-unread").checked;
  let url = "/notifications/?";
  if (cid) url += `citizen_id=${cid}&`;
  if (unread) url += "unread=1";
  const r = await req("GET", url);
  const div = document.getElementById("notif-list");
  const rows = r.data.notifications || [];
  if (!rows.length) { div.innerHTML = "<p>No notifications found.</p>"; return; }
  div.innerHTML = rows.map(n => `
    <div class="notif-card ${n.notification_type}">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div class="notif-title">${n.title}</div>
        <span class="badge ${n.notification_type === 'success' ? 'success' : n.notification_type === 'warning' ? 'warning' : 'info'}">${n.notification_type}</span>
      </div>
      <div class="notif-msg">${n.message}</div>
      <div class="notif-meta">
        ${String(n.created_at).substring(0, 19)} &nbsp;·&nbsp;
        Citizen: ${n.citizen_id || "—"} &nbsp;·&nbsp;
        ${n.is_read ? "Read" : "<strong>Unread</strong>"}
        ${!n.is_read ? `&nbsp;<button onclick="markRead(${n.notification_id})" class="btn btn-sm btn-secondary" style="margin-left:8px">Mark Read</button>` : ""}
      </div>
    </div>
  `).join("");
}

async function markRead(nid) {
  await req("PUT", `/notifications/${nid}/read`);
  toast("Marked as read", "ok");
  loadNotifications();
}

// ── Permissions ───────────────────────────────────────────────────────────
async function loadPermissions() {
  const r = await req("GET", "/permissions/");
  const div = document.getElementById("perms-table");
  if (!r.ok) {
    div.innerHTML = `<p style="color:var(--text-muted);margin-top:12px">Requires Admin role.</p>`;
    return;
  }
  const rows = r.data.permissions || [];
  if (!rows.length) { div.innerHTML = "<p style='margin-top:12px'>No permissions granted yet.</p>"; return; }
  div.innerHTML = `<table style="margin-top:14px">
    <tr><th>Officer</th><th>Role</th><th>Permission</th><th>Granted At</th></tr>
    ${rows.map(p => `<tr>
      <td>${p.full_name} (${p.officer_id})</td>
      <td><span class="badge">${p.role_name}</span></td>
      <td><code>${p.permission_name}</code></td>
      <td>${String(p.granted_at).substring(0, 16)}</td>
    </tr>`).join("")}
  </table>`;
}

async function myPermissions() {
  const r = await req("GET", "/permissions/my-permissions");
  const div = document.getElementById("perms-table");
  const perms = r.data.permissions || [];
  div.innerHTML = `<div style="margin-top:14px">
    <p><strong>Role:</strong> <span class="badge info">${r.data.role}</span></p>
    <p style="margin-top:10px"><strong>Permissions (${perms.length}):</strong></p>
    <div style="margin-top:8px">${perms.map(p => `<code style="margin:3px;display:inline-block">${p}</code>`).join("")}</div>
    ${r.data.note ? `<p style="margin-top:8px;color:var(--text-muted);font-size:0.8rem">${r.data.note}</p>` : ""}
  </div>`;
}

async function grantPermission() {
  const r = await req("POST", "/permissions/grant", {
    officer_id: parseInt(document.getElementById("perm-oid").value),
    permission_name: document.getElementById("perm-name").value
  });
  if (r.ok) { toast("Permission granted", "ok"); loadPermissions(); }
  else toast("Error: " + r.data.error, "err");
}

async function revokePermission() {
  const r = await req("DELETE", "/permissions/revoke", {
    officer_id: parseInt(document.getElementById("perm-oid").value),
    permission_name: document.getElementById("perm-name").value
  });
  if (r.ok) { toast("Permission revoked", "warn"); loadPermissions(); }
  else toast("Error: " + r.data.error, "err");
}

// ── Audit Log ─────────────────────────────────────────────────────────────
async function loadAuditLog() {
  const oid = document.getElementById("audit-officer").value;
  const tbl = document.getElementById("audit-table-input").value;
  const action = document.getElementById("audit-action").value;
  let url = "/audit/?limit=30";
  if (oid) url += `&officer_id=${oid}`;
  if (tbl) url += `&table_name=${encodeURIComponent(tbl)}`;
  if (action) url += `&action_type=${action}`;
  const r = await req("GET", url);
  const div = document.getElementById("audit-table-div");
  if (!r.ok) {
    div.innerHTML = `<p style="color:var(--text-muted);margin-top:12px">Requires Admin or Security Officer role.</p>`;
    return;
  }
  const rows = r.data.logs || [];
  if (!rows.length) { div.innerHTML = "<p style='margin-top:12px'>No logs found.</p>"; return; }
  div.innerHTML = `<p style="margin-bottom:8px;color:var(--text-muted);font-size:0.78rem">Total: ${r.data.total} entries</p>
  <table>
    <tr><th>Log ID</th><th>Officer</th><th>Action</th><th>Table</th><th>Record</th><th>IP</th><th>Time</th></tr>
    ${rows.map(l => `<tr>
      <td><code>${l.log_id}</code></td>
      <td>${l.officer_name} (${l.officer_id})</td>
      <td><span class="badge ${l.action_type === 'DELETE' ? 'danger' : l.action_type === 'INSERT' ? 'success' : 'info'}">${l.action_type}</span></td>
      <td>${l.table_name}</td>
      <td>${l.record_id ?? "—"}</td>
      <td><code>${l.ip_address || "—"}</code></td>
      <td style="font-family:var(--font-mono);font-size:0.75rem">${String(l.timestamp).substring(0, 19)}</td>
    </tr>`).join("")}
  </table>`;
}

// ── Auto-login on page load ───────────────────────────────────────────────
window.addEventListener("load", async () => {
  if (TOKEN) {
    const r = await req("GET", "/auth/me");
    if (r.ok) {
      OFFICER = r.data.officer;
      document.getElementById("user-name").textContent = OFFICER.full_name;
      document.getElementById("user-role").textContent = OFFICER.role_name;
      document.getElementById("user-info").classList.remove("hidden");
      applyRoleVisibility(OFFICER.role_name);
      document.querySelector("[data-tab='dashboard']").click();
      loadDashboard();
    } else {
      TOKEN = null;
      localStorage.removeItem("crida_token");
    }
  }
});