# CRIDA — Phase 2 Backend API

**Citizen Registration & Identity Database Authority**
Advanced Database Management Course — 4th Semester CS

---

## Setup (corrected — fixes all known errors)

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
```bash
mysql -u crida_user -pcrida1234 CRID < family_seed.sql
```
### Step 2 — Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt  
cp .env.example .env              
python app.py                     

### Step 3 — Verify

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

## Known Issues Fixed

| Error | Cause | Fix Applied |
|-------|-------|-------------|
| `smtplib2==0.2.1 not found` | Package doesn't exist on PyPI | Removed from requirements.txt; stdlib `smtplib` used instead |
| `ERROR 1819 — password policy` | MySQL validate_password plugin rejects `crida_pass` | setup_database.sql now runs `SET GLOBAL validate_password.policy = LOW` first |
| `ModuleNotFoundError: flask` | pip aborted before installing anything due to smtplib2 error | Fixed by removing smtplib2 — pip now completes fully |

---

## Roles & Permissions

| Role | Level | Key Access |
|------|-------|-----------|
| Admin | 5 | Everything |
| Registrar | 4 | Registrations, CNIC |
| Passport_Officer | 3 | Passports |
| License_Officer | 3 | Driving Licenses |
| Security_Officer | 4 | Watchlist, Criminal Records |






# For Windows
# 1. Navigate to the backend directory
cd CRIDA\Phase-1\crida\backend

# 2. Create a Python virtual environment
python -m venv venv

# 3. Activate the virtual environment
#    For Command Prompt:
venv\Scripts\activate
#    For PowerShell:
.\venv\Scripts\Activate

# 4. Install the required Python packages
pip install -r requirements.txt

# 5. Run the Flask application
python app.py