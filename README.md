# CRIDA — Phase 2 Backend API

**Citizen Registration & Identity Database Authority**
Advanced Database Management Course — 4th Semester CS

Project-01
Phase-02

Group Members.
BSCS24041 Hasnain Javaid 
BSCS24115 Syed Zain Ali Kazmi
BSCS24097 Muhammad Zunair Khalid

---

## Project Structure

```
Phase-1/
├── crida/
│   ├── backend/
│   │   ├── app.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── requirements.txt
│   │   ├── .env                
│   │   ├── .env.example
│   │   ├── setup_database.sql
│   │   ├── routes/
│   │   ├── middleware/
│   │   └── utils/
│   └── frontend/
│       ├── server.js
│       ├── package.json
│       └── public/
├── seed_2.sql                  
└── SQL_Scripting.sql
```

---

## Setup (follow in exact order)

### Step 1 — Create DB user and Phase 2 tables

Run from the `Phase-1/` root directory:

```bash
sudo mysql -u root -p < crida/backend/setup_database.sql
```

Expected output: `setup_database.sql completed successfully.`

Verify the user was created:

```bash
sudo mysql -u root -p -e "SELECT user, host FROM mysql.user WHERE user='crida_user';"
```

Expected: one row showing `crida_user | localhost`

Verify the connection works:

```bash
mysql -u crida_user -pcrida_pass -e "USE CRID; SELECT 1;"
```

Expected: a table showing `1`.

---

### Step 2 — Create the .env file

**This step is required. Without it Flask cannot connect to MySQL.**

```bash
cat > crida/backend/.env << 'EOF'
DB_HOST=localhost
DB_PORT=3306
DB_USER=crida_user
DB_PASSWORD=crida_pass
DB_NAME=CRID
DB_POOL_SIZE=5
JWT_SECRET_KEY=crida-secret-key-change-this-in-production
JWT_EXPIRY_HOURS=24
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
SMTP_FROM=noreply@crida.pk
EOF
```

---

### Step 3 — Seed the database

Run from the `Phase-1/` root directory:

```bash
sudo mysql -u root -p CRID < seed_2.sql
```

---

### Step 4 — Start the backend

**Must be run from inside `crida/backend/` — not from Phase-1/ or crida/**

```bash
cd crida/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

The server starts at `http://localhost:5000`

Verify:

```bash
curl http://localhost:5000/api/v1/health
```

Expected:

```json
{"database": "connected", "service": "CRIDA Phase 2 API", "status": "ok"}
```

---

### Step 5 — Start the frontend

Open a new terminal:

```bash
cd crida/frontend
npm install
node server.js
```

Frontend runs at `http://localhost:3000`

---

## Default Login

| Email | Password | Role |
|-------|----------|------|
| `officer5@crida.pk` | `hash` | Admin |

> **Why officer5?** seed_2.sql assigns roles as `(n % 5) + 1`. Officer 5 → `role_id = 1` = Admin.
> After running `setup_database.sql`, officer5's password becomes `Admin@1234` (bcrypt hashed).

---

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Access denied for crida_user` | `.env` file missing or has wrong password | Create `.env` in `crida/backend/` with `DB_PASSWORD=crida_pass` |
| `database: error` from /health | `.env` not loaded — Flask started from wrong directory | Always run `python app.py` from inside `crida/backend/` |
| `Port 5000 is already in use` | Old Flask process still running | Run `kill $(lsof -ti:5000)` then restart |
| `seed_2.sql: No such file or directory` | Running seed from wrong directory | Run from `Phase-1/` root: `sudo mysql -u root -p CRID < seed_2.sql` |
| `ModuleNotFoundError` | Wrong venv activated | Activate the venv inside `crida/backend/venv/`, not the one in `Phase-1/` |

---

## Roles & Permissions

| Role | Access Level | Key Access |
|------|-------------|-----------|
| Admin | 5 | Everything |
| Registrar | 4 | Registrations, CNIC |
| Passport_Officer | 3 | Passports |
| License_Officer | 3 | Driving Licenses |
| Security_Officer | 4 | Watchlist, Criminal Records |