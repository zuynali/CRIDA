const API = "http://localhost:5000/api/v1";
let TOKEN = localStorage.getItem("crida_token") || null;
let OFFICER = null;

// ── Role-based tab visibility ─────────────────────────────────────────────
// Called after every login. Reads data-roles on each nav link and hides
// links (and their tab panels) that the current role is not allowed to see.
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

    // Apply role-based nav visibility BEFORE switching tabs
    applyRoleVisibility(OFFICER.role_name);

    toast("Welcome, " + OFFICER.full_name + "!", "ok");
    document.querySelector("[data-tab='dashboard']").click();
    loadDashboard();
  } else {
    msg.className = "msg-box err";
    msg.textContent = r.data.error || "Login failed";
  }
}

function logout() {
  TOKEN = null; OFFICER = null;
  localStorage.removeItem("crida_token");

  // Stop any active biometric camera on logout
  stopBioCamera();

  // Restore all nav links visibility for the next login
  document.querySelectorAll("[data-tab][data-roles]").forEach(link => {
    link.style.display = "";
  });

  document.querySelector("[data-tab='login']").click();
  document.getElementById("user-info").classList.add("hidden");
  toast("Logged out", "warn");
}

// ── Dashboard ─────────────────────────────────────────────────────────────
async function loadDashboard() {
  const [cr, nr, ar] = await Promise.all([
    req("GET", "/citizens/?limit=1"),
    req("GET", "/notifications/unread-count"),
    req("GET", "/audit/?limit=1")
  ]);
  const stats = [
    { n: cr.ok ? (cr.data.total || "—") : "—", l: "Total Citizens" },
    { n: OFFICER?.role_name || "—", l: "Your Role" },
    { n: OFFICER?.access_level || "—", l: "Access Level" },
    { n: nr.ok ? (nr.data.unread_count ?? "—") : "—", l: "Unread Alerts" },
    { n: ar.ok ? (ar.data.total || "—") : "N/A", l: "Audit Entries" },
    { n: "MySQL 8.0", l: "Database" },
  ];
  document.getElementById("stats-grid").innerHTML = stats.map(s =>
    `<div class="stat-card">
       <div class="number">${s.n}</div>
       <div class="label">${s.l}</div>
     </div>`
  ).join("");
  acidLog("Dashboard loaded — API health confirmed.");
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

  if (!cid) {
    alert("Enter Citizen ID");
    return;
  }

  try {
    const r = await req("GET", `/family-tree/${cid}`);

    if (!r.ok) {
      throw new Error(r.data.error || "Failed");
    }

    renderTree(r.data);

  } catch (e) {
    document.getElementById('family-result').innerHTML =
      `<div style="color:red;">Error: ${e.message}</div>`;
  }
}
function renderTree(data) {
  _treeData = data;

  const parents = [];
  const children = [];
  const siblings = [];
  const others = [];
  const seen = new Set();

  [
    ...(data.relationships || []).map(r => ({ ...r, _rel: r.relationship_type })),
    ...(data.reverse_relations || []).map(r => ({ ...r, _rel: r.relationship_type }))
  ].forEach(r => {
    if (seen.has(r.citizen_id)) return;
    seen.add(r.citizen_id);

    const rel = r._rel;

    if (['Father', 'Mother', 'Grandfather', 'Grandmother'].includes(rel)) {
      parents.push(r);
    } else if (['Son', 'Daughter', 'Child', 'Grandson', 'Granddaughter'].includes(rel)) {
      children.push(r);
    } else if (['Brother', 'Sister', 'Sibling', 'Brother-in-law', 'Sister-in-law'].includes(rel)) {
      siblings.push(r);
    } else if (['Husband', 'Wife', 'Spouse'].includes(rel)) {
      // Handled separately by the spouse section
    } else {
      others.push(r);
    }
  });

  const root = data.citizen;
  const spouse = data.spouse;

  let html = `<div class="ft-tree">`;

  // PARENTS
  if (parents.length) {
    html += `
      <div class="ft-row-wrap">
        <div class="ft-section-label">Parents</div>
        <div class="ft-row">
          ${parents.map(p => personNode(p, p._rel, false, 52)).join('')}
        </div>
      </div>
      <div class="ft-vline" style="height:30px;background:#85B7EB"></div>
    `;
  }

  // MIDDLE
  html += `<div class="ft-row" style="align-items:center;gap:30px;flex-wrap:wrap">`;

  // SIBLINGS
  if (siblings.length) {
    html += `
      <div style="display:flex;flex-direction:column;align-items:center">
        <div class="ft-section-label">Siblings</div>
        <div style="display:flex;gap:12px;flex-wrap:wrap">
          ${siblings.map(p => personNode(p, p._rel, false, 50)).join('')}
        </div>
      </div>
      <div style="width:25px;height:2px;background:#ccc"></div>
    `;
  }

  // ROOT
  html += `
    <div style="display:flex;flex-direction:column;align-items:center">
      <div class="ft-root-label">Root</div>
      ${personNode(root, null, true, 70)}
    </div>
  `;

  // SPOUSE
  if (spouse) {
    const spouseRel = root.gender === 'Male' ? 'Wife' : 'Husband';

    html += `
      <div style="width:25px;height:2px;background:#EF9F27"></div>
      <div style="display:flex;flex-direction:column;align-items:center">
        <div class="ft-section-label">${spouseRel}</div>
        ${personNode({
      citizen_id: spouse.spouse_id,
      full_name: spouse.spouse_name,
      _rel: spouseRel
    }, spouseRel, false, 50)}
      </div>
    `;
  }

  html += `</div>`;

  // CHILDREN
  if (children.length) {
    html += `
      <div class="ft-vline" style="height:30px;background:#97C459"></div>
      <div class="ft-row-wrap">
        <div class="ft-section-label">Children</div>
        <div class="ft-row">
          ${children.map(p => personNode(p, p._rel, false, 52)).join('')}
        </div>
      </div>
    `;
  }

  // OTHERS
  if (others.length) {
    html += `
      <div style="margin-top:20px">
        <div class="ft-section-label">Others</div>
        <div class="ft-row">
          ${others.map(p => personNode(p, p._rel, false, 48)).join('')}
        </div>
      </div>
    `;
  }

  html += `</div>`;

  document.getElementById('family-result').innerHTML = html;
}
function personNode(person, relation, isRoot = false, size = 60) {
  const initials = person.full_name
    ? person.full_name.split(" ").map(n => n[0]).join("").toUpperCase()
    : "?";

  return `
    <div style="
      display:flex;
      flex-direction:column;
      align-items:center;
      margin:6px;
    ">
      
      <div style="
        width:${size}px;
        height:${size}px;
        border-radius:50%;
        background:${isRoot ? '#4CAF50' : '#2C3E50'};
        color:white;
        display:flex;
        align-items:center;
        justify-content:center;
        font-weight:bold;
        font-size:${size / 3}px;
        border:${isRoot ? '3px solid #FFD700' : '2px solid #555'};
      ">
        ${initials}
      </div>

      <div style="margin-top:6px;font-size:12px;text-align:center">
        ${person.full_name || "Unknown"}
      </div>

      ${relation ? `
        <div style="
          font-size:10px;
          color:#aaa;
          margin-top:2px;
        ">
          ${relation}
        </div>
      ` : ""}
    </div>
  `;
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
      video: {
        width:      { ideal: 1280 },
        height:     { ideal: 720  },
        facingMode: "user"
      }
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
    toast("Camera started", "ok");
    acidLog(`BIO camera started for citizen ${document.getElementById("bio-cid").value || "?"}`);
  } catch (e) {
    toast("Camera error: " + e.message, "err");
  }
}

function stopBioCamera() {
  if (bioStream) {
    bioStream.getTracks().forEach(t => t.stop());
    bioStream = null;
  }
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
}

// ─────────────────────────────────────────────────────────────────────────
//  Capture a frame from the live camera and return { base64, hash }
//  base64 → full data-URL JPEG  (sent to /documents/upload-photo)
//  hash   → SHA-256 hex string  (stored in Biometric_Data.facial_scan_hash)
// ─────────────────────────────────────────────────────────────────────────
async function captureFrame() {
  const video = document.getElementById("bio-video");
  if (!video.videoWidth || !video.videoHeight) return null;

  const canvas = document.createElement("canvas");
  canvas.width  = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0);

  const base64 = canvas.toDataURL("image/jpeg", 0.92);
  if (base64.length < 5000) return null;          // blank / dark frame guard

  // Compute SHA-256 of the raw JPEG bytes
  const blob = await new Promise(res => canvas.toBlob(res, "image/jpeg", 0.92));
  const buf  = await blob.arrayBuffer();
  const raw  = await crypto.subtle.digest("SHA-256", buf);
  const hash = Array.from(new Uint8Array(raw))
    .map(b => b.toString(16).padStart(2, "0")).join("");

  return { base64, hash };
}

// ─────────────────────────────────────────────────────────────────────────
//  ENROLL BIOMETRIC
//
//  Two independent operations happen in sequence:
//
//  1. POST /documents/upload-photo  → saves the JPEG to disk and inserts a
//     row in Document (document_type = 'photo').  This is the reference
//     image that verify_face will compare against.
//
//  2. POST /biometric/enroll        → upserts Biometric_Data with:
//       facial_scan_hash = SHA-256 of the captured JPEG
//       fingerprint_hash = value from the text field (empty = "")
//
//  Schema constraints respected:
//    • Biometric_Data.facial_scan_hash  VARCHAR(256)  ← 64-char hex hash
//    • Biometric_Data.fingerprint_hash  VARCHAR(256)  ← text field value
//    • Document.document_type           ENUM('photo','signature','supporting_doc')
// ─────────────────────────────────────────────────────────────────────────
async function enrollBiometric() {
  const r = await req("POST", "/biometric/enroll", {
    citizen_id:       parseInt(document.getElementById("bio-cid").value),
    fingerprint_hash: document.getElementById("bio-enroll-fp").value,
    facial_scan_hash: "enrolled_face_" + document.getElementById("bio-cid").value
  });
  if (r.ok) toast("Biometric enrolled/updated", "ok");
  else toast("Error: " + r.data.error, "err");
}

async function verifyFingerprint() {
  const r = await req("POST", "/biometric/verify-fingerprint", {
    citizen_id:       parseInt(document.getElementById("bio-cid").value),
    fingerprint_hash: document.getElementById("bio-fp").value
  });
  const div = document.getElementById("bio-result");
  if (r.ok) {
    const v = r.data.verified;
    div.innerHTML = `<div class="msg-box ${v ? 'ok' : 'err'}" style="display:block;margin-top:10px">
      Fingerprint: <strong>${v ? "✅ VERIFIED" : "❌ NOT MATCHED"}</strong>
      &nbsp;| Method: ${r.data.method}
    </div>`;
    toast(v ? "Fingerprint verified!" : "Mismatch", v ? "ok" : "err");
  }
}

// ─────────────────────────────────────────────────────────────────────────
//  VERIFY FACE
//  (No changes needed in the frontend — the backend verify_face route
//   reads from the Document table which enrollBiometric() now populates.)
// ─────────────────────────────────────────────────────────────────────────
async function verifyFace() {
  const cid = parseInt(document.getElementById("bio-cid").value);
  if (!cid)       { toast("Enter a Citizen ID", "err"); return; }
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
      image:      frame.base64
    });

    if (!r.ok) {
      div.innerHTML = `<div class="msg-box err" style="display:block;margin-top:10px">
        <strong>Error:</strong> ${r.data.error || "Unknown error"}
        ${r.status === 404
          ? `<br><small>→ Enroll this citizen's face first using the <b>Enroll Biometric</b> button (camera must be on).</small>`
          : ""}
        ${r.status === 501
          ? `<br><small>→ Run: <code>pip install face_recognition</code> or <code>pip install opencv-python</code> in your backend venv.</small>`
          : ""}
      </div>`;
      toast("Face verify failed: " + (r.data.error || r.status), "err");
      return;
    }

    const v      = r.data.verified;
    const conf   = r.data.confidence != null ? `${r.data.confidence}%` : "—";
    const note   = r.data.note   ? `<br><small style="color:var(--text-muted)">${r.data.note}</small>`   : "";
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


// ─────────────────────────────────────────────────────────────────────────
//  DEBUG HELPER  (dev only — call from browser console: bioDebug(7))
// ─────────────────────────────────────────────────────────────────────────
async function bioDebug(citizenId) {
  const r = await req("GET", `/biometric/debug/${citizenId}`);
  console.table(r.data);
  const div = document.getElementById("bio-result");
  div.innerHTML = `<div class="msg-box" style="display:block;margin-top:10px;font-family:monospace;font-size:0.78rem">
    <strong>Debug — Citizen ${citizenId}</strong><br>
    Photo in DB:      <code>${r.data.photo?.db_path   || "none"}</code><br>
    Resolved path:    <code>${r.data.photo?.resolved  || "—"}</code><br>
    File exists:      <strong>${r.data.photo?.exists  ?? "—"}</strong>
    &nbsp; Size: ${r.data.photo?.size_bytes ? (r.data.photo.size_bytes / 1024).toFixed(1) + " KB" : "—"}<br>
    Biometric row:    ${r.data.biometric_row ? "✅ Yes" : "❌ No"}<br>
    FP hash:          <code>${r.data.biometric_row?.fingerprint_hash?.substring(0,20) || "—"}…</code><br>
    Facial hash:      <code>${r.data.biometric_row?.facial_scan_hash?.substring(0,20) || "—"}…</code><br>
    Uploads dir:      <code>${r.data.uploads_dir}</code>
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

// ── Auto-login on page load ────────────────────────────────────────────────
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