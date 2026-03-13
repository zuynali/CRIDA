# CRIDA — Phase 2: Backend API

**Citizen Registration & Identity Database Authority**  
Advanced Database Management Course — 4th Semester CS

---

## Quick Start

```bash
# 1. Database setup (run ONCE as root — creates user + Phase 2 tables)
sudo mysql -u root -p CRID < backend/setup_database.sql
sudo mysql -u root -p CRID < seed_2.sql

# 2. Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # Edit DB credentials
python app.py              # → http://localhost:5000

# 3. Frontend
cd frontend
npm install
node server.js             # → http://localhost:3000
```

---

## Verification — Part 1

```bash
# With backend running:
curl http://localhost:5000/api/v1/health
# Expected: {"database": "connected", "service": "CRIDA Phase 2 API", "status": "ok"}
```

---

## Default Login

| Credential | Value |
|------------|-------|
| Email (seed) | `officer1@crida.pk` |
| Password (seed) | `hash` (legacy plaintext from seed_2.sql) |
| Email (setup_database.sql) | first Admin officer |
| Password | `admin123` (bcrypt hashed by setup_database.sql) |

---

## Project Structure (Part 1)

```
crida/
├── backend/
│   ├── app.py                  # Flask entry point — 17 blueprints registered
│   ├── config.py               # .env loader — DB, JWT, SMTP settings
│   ├── db.py                   # MySQL connection pool + ACID helpers
│   ├── requirements.txt        # Pinned dependencies
│   ├── .env                    # Secrets — NOT committed
│   ├── .env.example            # Safe template — committed
│   ├── setup_database.sql      # Creates crida_user + 4 Phase 2 tables
│   ├── routes/                 # 17 Blueprint modules (stubs in Part 1)
│   ├── middleware/
│   │   ├── auth.py             # @token_required — JWT validation
│   │   └── rbac.py             # @role_required, @permission_required
│   ├── utils/
│   │   └── validators.py       # Input validation helpers
│   └── uploads/photos/         # Processed citizen photos (runtime)
├── frontend/                   # Node.js SPA (Part 5)
└── media/                      # Rollback screenshots (Part 4)
```

---

## Features (implemented across Parts 2–5)

1. PDF Generation — CNIC, Passport, License, Birth/Death/Marriage Certs, Payment Slip  
2. Family Tree — recursive relationships from `Family_Relationship` table  
3. Criminal Records — view/add/update via Security Officer role  
4. Citizen Self-Update — atomic approval workflow (ACID transaction)  
5. Camera + BG Removal — face detection → rembg → Document table  
6. Biometric Verification — fingerprint hash + face_recognition  
7. Complaint System — full lifecycle (Open → In Progress → Resolved → Closed)  
8. Granular Permissions — 12 permission types per officer, Admin-granted  
9. Notifications + Email — in-DB storage + async SMTP on ACID commit  
10. Node.js Frontend — full SPA testing all 10 features  

---

## ACID Compliance

Transaction logs: `backend/app.log`  
Rollback evidence: `media/rollback_demo.png`

| Property | Implementation |
|----------|----------------|
| Atomicity | `execute_transaction_custom()` wraps all writes in BEGIN/COMMIT |
| Consistency | Phase 1 triggers + CHECK constraints enforce business rules |
| Isolation | `READ COMMITTED` isolation level prevents dirty reads |
| Durability | InnoDB WAL + explicit `conn.commit()` after every transaction |

---

## Roles & Permissions

| Role | Level | Key Access |
|------|-------|-----------|
| Admin | 5 | Everything |
| Registrar | 4 | Registrations, CNIC |
| Passport_Officer | 3 | Passports |
| License_Officer | 3 | Driving Licenses |
| Security_Officer | 4 | Watchlist, Criminal Records |

---

## Contact

Jalal Ahmed: bscs23134@itu.edu.pk  
Khadijah Farooqi: bscs23128@itu.edu.pk  
Office Hours: Monday & Thursday, 11:30 AM – 2:30 PM
