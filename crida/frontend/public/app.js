const API = "http://localhost:5000/api/v1";
let TOKEN  = localStorage.getItem("crida_token") || null;
let OFFICER = null;

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
    email:    document.getElementById("login-email").value,
    password: document.getElementById("login-pass").value
  });
  if (r.ok) {
    TOKEN   = r.data.token;
    OFFICER = r.data.officer;
    localStorage.setItem("crida_token", TOKEN);
    msg.className = "msg-box ok";
    msg.textContent = "Logged in as " + OFFICER.full_name;
    document.getElementById("user-name").textContent = OFFICER.full_name;
    document.getElementById("user-role").textContent  = OFFICER.role_name;
    document.getElementById("user-info").classList.remove("hidden");
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
    { n: cr.data.total || "—",          l: "Total Citizens" },
    { n: OFFICER?.role_name || "—",     l: "Your Role" },
    { n: OFFICER?.access_level || "—",  l: "Access Level" },
    { n: nr.data.unread_count ?? "—",   l: "Unread Alerts" },
    { n: ar.data.total || "—",          l: "Audit Entries" },
    { n: "MySQL 8.0",                   l: "Database" },
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
  const url = search ? `/citizens/?search=${encodeURIComponent(search)}&limit=30` : "/citizens/?limit=30";
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
  const id   = document.getElementById("pdf-id").value;
  const msg  = document.getElementById("pdf-msg");
  msg.className = "msg-box";
  try {
    const blob = await req("GET", `/pdf/${type}/${id}`, null, true);
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = `${type}_${id}.pdf`; a.click();
    msg.className = "msg-box ok";
    msg.textContent = `PDF downloaded: ${type}_${id}.pdf`;
    acidLog(`PDF generated: ${type} for ID ${id} — ACID transaction logged`);
    toast("PDF downloaded!", "ok");
  } catch (e) {
    msg.className = "msg-box err";
    msg.textContent = "PDF failed: " + e.message;
  }
}

// ── Family Tree ───────────────────────────────────────────────────────────
async function loadFamilyTree() {
  const cid = document.getElementById("family-cid").value;
  const r   = await req("GET", `/family-tree/${cid}`);
  const div = document.getElementById("family-result");
  if (!r.ok) { div.innerHTML = `<p style="color:var(--danger)">${r.data.error || "Not found"}</p>`; return; }
  const d = r.data;
  let html = `<div style="margin-top:14px">
    <p><strong>${d.citizen?.full_name}</strong> &nbsp;
       <code>${d.citizen?.national_id_number}</code> &nbsp;
       <span class="badge">${d.citizen?.gender}</span> &nbsp;
       <span class="badge ${d.citizen?.status === 'active' ? 'success' : 'danger'}">${d.citizen?.status}</span>
    </p>
    ${d.spouse ? `<p style="margin-top:8px">&#128141; Spouse: <strong>${d.spouse.spouse_name}</strong> (ID: ${d.spouse.spouse_id}) — ${d.spouse.marriage_date?.substring(0,16)}</p>` : "<p style='margin-top:8px;color:var(--text-muted)'>No spouse on record</p>"}
    <p style="margin:10px 0 6px;color:var(--text-muted);font-size:0.78rem;text-transform:uppercase;letter-spacing:0.06em">${d.tree_summary?.total_relations} relations found</p>
    <div>`;
  (d.relationships || []).forEach(rel => {
    html += `<div class="tree-node">
      <div><strong>${rel.full_name}</strong></div>
      <div class="rel-type">${rel.relationship_type} &nbsp;·&nbsp; ID ${rel.citizen_id}</div>
    </div>`;
  });
  html += `</div></div>`;
  div.innerHTML = html;
}

// ── Criminal Records ──────────────────────────────────────────────────────
async function loadCriminalRecords() {
  const cid = document.getElementById("criminal-cid").value;
  const url = cid ? `/security/criminal-records?citizen_id=${cid}` : "/security/criminal-records";
  const r   = await req("GET", url);
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
      <td>${String(rec.offense_date).substring(0,10)}</td>
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
    citizen_id:   parseInt(document.getElementById("cr-cid").value),
    case_number:  document.getElementById("cr-case").value,
    offense:      document.getElementById("cr-offense").value,
    offense_date: document.getElementById("cr-date").value,
    status:       document.getElementById("cr-status").value,
    court_name:   document.getElementById("cr-court").value
  });
  if (r.ok) {
    toast("Criminal record added", "ok");
    acidLog(`CRIMINAL_RECORD ${r.data.record_id} added — ACID: INSERT + Audit_Log COMMIT`);
    loadCriminalRecords();
  } else toast("Error: " + r.data.error, "err");
}

// ── Watchlist ─────────────────────────────────────────────────────────────
async function loadWatchlist() {
  const r   = await req("GET", "/security/watchlist");
  const div = document.getElementById("watchlist-table");
  if (!r.ok) { div.innerHTML = `<p style="color:var(--danger)">${r.data.error || "Permission denied"}</p>`; return; }
  const rows = r.data.watchlist || [];
  if (!rows.length) { div.innerHTML = "<p style='margin-top:12px'>Watchlist is empty.</p>"; return; }
  div.innerHTML = `<table style="margin-top:14px">
    <tr><th>ID</th><th>Citizen</th><th>Type</th><th>Reason</th><th>Added</th><th>Expiry</th></tr>
    ${rows.map(w => `<tr>
      <td><code>${w.watchlist_id}</code></td>
      <td>${w.citizen_name} (${w.citizen_id})</td>
      <td><span class="badge warning">${w.watchlist_type}</span></td>
      <td>${w.reason}</td>
      <td>${String(w.added_date).substring(0,10)}</td>
      <td>${w.expiry_date ? String(w.expiry_date).substring(0,10) : "—"}</td>
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
    citizen_id:    parseInt(document.getElementById("wl-cid").value),
    reason:        document.getElementById("wl-reason").value,
    watchlist_type: document.getElementById("wl-type").value,
    ...(expiry ? { expiry_date: expiry } : {})
  });
  if (r.ok) {
    toast("Added to watchlist", "ok");
    acidLog(`WATCHLIST entry ${r.data.watchlist_id} added — type: ${document.getElementById("wl-type").value}`);
    loadWatchlist();
  } else toast("Error: " + r.data.error, "err");
}

// ── Update Requests ───────────────────────────────────────────────────────
async function submitUpdateRequest() {
  const r = await req("POST", "/update-requests/", {
    citizen_id: parseInt(document.getElementById("upd-cid").value),
    field_name: document.getElementById("upd-field").value,
    new_value:  document.getElementById("upd-value").value,
    reason:     document.getElementById("upd-reason").value
  });
  if (r.ok) {
    toast("Update request submitted (Pending)", "ok");
    acidLog("UPDATE_REQUEST submitted — awaiting officer approval (ACID: Pending state)");
    loadUpdateRequests();
  } else toast("Error: " + r.data.error, "err");
}

async function loadUpdateRequests() {
  const r   = await req("GET", "/update-requests/?status=Pending");
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
    toast("Request approved — citizen updated!", "ok");
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
  const video  = document.getElementById("cam-video");
  const canvas = document.getElementById("cam-canvas");
  canvas.getContext("2d").drawImage(video, 0, 0, 320, 240);
  const base64 = canvas.toDataURL("image/jpeg");
  const cid    = document.getElementById("cam-cid").value;
  const r      = await req("POST", "/camera/capture", {
    citizen_id: parseInt(cid), image: base64
  });
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

let bioStream = null;
async function startBioCamera() {
  bioStream = await navigator.mediaDevices.getUserMedia({ video: true });
  document.getElementById("bio-video").srcObject = bioStream;
}

async function verifyFace() {
  const video  = document.getElementById("bio-video");
  const canvas = document.createElement("canvas");
  canvas.width = 240; canvas.height = 180;
  canvas.getContext("2d").drawImage(video, 0, 0, 240, 180);
  const base64 = canvas.toDataURL("image/jpeg");
  const r = await req("POST", "/biometric/verify-face", {
    citizen_id: parseInt(document.getElementById("bio-cid").value),
    image: base64
  });
  const div = document.getElementById("bio-result");
  if (r.ok) {
    const v = r.data.verified;
    div.innerHTML = `<div class="msg-box ${v ? 'ok' : 'err'}" style="display:block;margin-top:10px">
      Face: <strong>${v ? "✅ VERIFIED" : "❌ NOT MATCHED"}</strong>
      ${r.data.confidence ? ` | Confidence: ${r.data.confidence}%` : ""}
      | Method: ${r.data.method}
    </div>`;
  }
}

// ── Complaints ────────────────────────────────────────────────────────────
async function submitComplaint() {
  const r = await req("POST", "/complaints/", {
    citizen_id:  parseInt(document.getElementById("comp-cid").value),
    subject:     document.getElementById("comp-subject").value,
    description: document.getElementById("comp-desc").value
  });
  if (r.ok) { toast("Complaint submitted", "ok"); loadComplaints(); }
  else toast("Error: " + r.data.error, "err");
}

async function loadComplaints() {
  const r   = await req("GET", "/complaints/");
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
      <td>${String(c.created_at).substring(0,10)}</td>
    </tr>`).join("")}
  </table>`;
}

// ── Notifications ─────────────────────────────────────────────────────────
async function loadUnreadCount() {
  const cid = document.getElementById("notif-cid").value;
  const url = cid ? `/notifications/unread-count?citizen_id=${cid}` : "/notifications/unread-count";
  const r   = await req("GET", url);
  document.getElementById("notif-count").innerHTML =
    `<span class="badge warning">Unread: ${r.data.unread_count ?? 0}</span>`;
}

async function loadNotifications() {
  const cid    = document.getElementById("notif-cid").value;
  const unread = document.getElementById("notif-unread").checked;
  let url = "/notifications/?";
  if (cid)    url += `citizen_id=${cid}&`;
  if (unread) url += "unread=1";
  const r   = await req("GET", url);
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
        ${String(n.created_at).substring(0,19)} &nbsp;·&nbsp;
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
  const r   = await req("GET", "/permissions/");
  const div = document.getElementById("perms-table");
  const rows = r.data.permissions || [];
  if (!rows.length) { div.innerHTML = "<p style='margin-top:12px'>No permissions granted yet.</p>"; return; }
  div.innerHTML = `<table style="margin-top:14px">
    <tr><th>Officer</th><th>Role</th><th>Permission</th><th>Granted At</th></tr>
    ${rows.map(p => `<tr>
      <td>${p.full_name} (${p.officer_id})</td>
      <td><span class="badge">${p.role_name}</span></td>
      <td><code>${p.permission_name}</code></td>
      <td>${String(p.granted_at).substring(0,16)}</td>
    </tr>`).join("")}
  </table>`;
}

async function myPermissions() {
  const r   = await req("GET", "/permissions/my-permissions");
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
    officer_id:      parseInt(document.getElementById("perm-oid").value),
    permission_name: document.getElementById("perm-name").value
  });
  if (r.ok) { toast("Permission granted", "ok"); loadPermissions(); }
  else toast("Error: " + r.data.error, "err");
}

async function revokePermission() {
  const r = await req("DELETE", "/permissions/revoke", {
    officer_id:      parseInt(document.getElementById("perm-oid").value),
    permission_name: document.getElementById("perm-name").value
  });
  if (r.ok) { toast("Permission revoked", "warn"); loadPermissions(); }
  else toast("Error: " + r.data.error, "err");
}

// ── Audit Log ─────────────────────────────────────────────────────────────
// NOTE: seed_2.sql renames the column from `timestamp` to `action_time`.
//       The backend audit_routes.py queries `al.action_time` accordingly.
async function loadAuditLog() {
  const oid    = document.getElementById("audit-officer").value;
  const tbl    = document.getElementById("audit-table").value;
  const action = document.getElementById("audit-action").value;
  let url = "/audit/?limit=30";
  if (oid)    url += `&officer_id=${oid}`;
  if (tbl)    url += `&table_name=${encodeURIComponent(tbl)}`;
  if (action) url += `&action_type=${action}`;
  const r   = await req("GET", url);
  const div = document.getElementById("audit-table-div");
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
      <td style="font-family:var(--font-mono);font-size:0.75rem">${String(l.action_time).substring(0,19)}</td>
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
      document.getElementById("user-role").textContent  = OFFICER.role_name;
      document.getElementById("user-info").classList.remove("hidden");
      document.querySelector("[data-tab='dashboard']").click();
      loadDashboard();
    } else {
      TOKEN = null;
      localStorage.removeItem("crida_token");
    }
  }
});