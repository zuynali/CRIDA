# CRIDA — Phase 2 Backend API

**Citizen Registration & Identity Database Authority**
Advanced Database Management Course — 4th Semester CS

---

## Setup

### Step 1 — Database (run as root, no database name on command line)

```bash
sudo mysql -u root -p < backend/setup_database.sql
```

> The script sets `validate_password.policy = LOW` automatically so
> `crida_pass` is accepted. Do **not** add `CRID` after `-p` on this
> command — the script contains `USE CRID` internally.

Then seed the data:

```bash
sudo mysql -u root -p CRID < seed_2.sql
```

---

### Step 2 — Backend (Linux / macOS)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

### Step 2 — Backend (Windows)

```bat
cd CRIDA\Phase-1\crida\backend

python -m venv venv

:: Command Prompt:
venv\Scripts\activate
:: PowerShell:
.\venv\Scripts\Activate

pip install -r requirements.txt
copy .env.example .env
python app.py
```

---

### Step 3 — Frontend

```bash
cd frontend
npm install
node server.js
```

Open http://localhost:3000 in your browser.

---

### Step 4 — Verify Backend

```bash
curl http://localhost:5000/api/v1/health
# Expected: {"database": "connected", "service": "CRIDA Phase 2 API", "status": "ok"}
```

---

## Default Login

| Email | Password | Role |
|-------|----------|------|
| `officer5@crida.pk` | `hash` | Admin (seed_2.sql legacy) |

---

## Biometric Setup

The biometric module (face verification + fingerprint) requires OpenCV.
It is already listed in `requirements.txt` and installs automatically with `pip install -r requirements.txt`.

### Face Verification
- Uses **OpenCV ORB** feature matching (installed automatically)
- Optional: **face_recognition** (ML-based, more accurate) — requires Python ≤ 3.12
  - Not supported on Python 3.13 — OpenCV fallback is used automatically

### Fingerprint Verification
- Uses **WebAuthn** (Windows Hello / Touch ID / Android fingerprint)
- Requires HTTPS or `localhost`
- Device must have a fingerprint sensor enrolled in OS settings
- Falls back to manual hash entry if no sensor is available

### Face Enroll & Verify Flow
1. Go to **Biometric** tab
2. Enter a Citizen ID
3. Click **Start Camera**
4. Click **Enroll Biometric** — saves live photo + hash
5. Click **Verify Face** — compares live camera against stored photo

> **Important:** Enroll and Verify must be done in the same backend venv.
> Run `pip install -r requirements.txt` inside the correct venv
> (`crida/backend/venv/`) to ensure OpenCV is available to Flask.

---

## Known Issues Fixed

| Error | Cause | Fix Applied |
|-------|-------|-------------|
| `smtplib2==0.2.1 not found` | Package doesn't exist on PyPI | Removed from requirements.txt; stdlib `smtplib` used instead |
| `ERROR 1819 — password policy` | MySQL validate_password plugin rejects `crida_pass` | setup_database.sql now runs `SET GLOBAL validate_password.policy = LOW` first |
| `ModuleNotFoundError: flask` | pip aborted before installing anything due to smtplib2 error | Fixed by removing smtplib2 — pip now completes fully |
| `No face comparison library available` | OpenCV installed in wrong venv | Install with `crida/backend/venv/bin/pip install opencv-python` |
| `Identifier 'bioStream' has already been declared` | Duplicate biometric code after git pull | Fixed in app.js — all duplicates removed |
| `Failed to fetch` on photo upload | Wrong URL `/documents/upload-photo` | Fixed to `/biometric/upload-photo` |
| `face_recognition` fails on Python 3.13 | Library not compatible with Python 3.13 | Uninstall it — OpenCV fallback handles verification automatically |

---

## Roles & Permissions

| Role | Level | Key Access |
|------|-------|------------|
| Admin | 5 | Everything |
| Registrar | 4 | Registrations, CNIC |
| Passport_Officer | 3 | Passports |
| License_Officer | 3 | Driving Licenses |
| Security_Officer | 4 | Watchlist, Criminal Records |

---

## Project Structure

```
CRIDA/
├── crida/
│   ├── backend/
│   │   ├── venv/                  ← Python venv (use THIS one for pip installs)
│   │   ├── routes/
│   │   │   └── biometric_routes.py
│   │   ├── uploads/               ← Face photos saved here
│   │   ├── requirements.txt
│   │   └── app.py
│   └── frontend/
│       └── public/
│           └── app.js
├── setup_database.sql
└── seed_2.sql
```

---

## Troubleshooting

**Flask can't find opencv / cv2**
```bash
# Always use the backend venv, not the root one
~/Downloads/CRIDA/crida/backend/venv/bin/pip install opencv-python
```

**Face verify returns 404 "No photo on file"**
- You must click **Enroll Biometric** (with camera on) before verifying
- The enroll step saves the photo to the `Document` table
- Re-enroll after any database reset

**Fingerprint shows QR code popup**
- Your device doesn't have a fingerprint sensor recognised by the browser
- Use your phone to scan the QR code, or enter a manual hash in the field above the Verify Fingerprint button

**git pull breaks the app**
- Run `pip install -r requirements.txt` after every pull to catch new dependencies
- If JS errors appear after a pull, hard-refresh the browser (Ctrl+Shift+R)