# CRIDA — Citizen Registration & Identity Database Authority

## 1. Project Overview

CRIDA is a citizen registration and identity management platform built for a government-style identity authority. It supports officer login, citizen registration, CNIC/passport/license application workflows, biometric enrollment, security watchlist checks, certificate generation, notifications, and audit logging.

Target domain: public identity management and civil registry systems.

Problem solved:
- Centralises citizen records and application workflows
- Enforces role-based officer access for sensitive services
- Supports biometric verification and document issuance
- Uses transactional database logic and triggers to maintain data integrity

Team members:
- BSCS24041 Hasnain Javaid
- BSCS24115 Syed Zain Ali Kazmi
- BSCS24097 Muhammad Zunair Khalid

Group: Project-01 Phase-02

## 2. Tech Stack

Backend
- Python 3.10+ (recommended)
- Flask 3.0.3
- mysql-connector-python 8.3.0
- Flask-CORS
- Flask-Bcrypt
- PyJWT
- python-dotenv
- fpdf2, Pillow, reportlab for PDF generation
- OpenCV (`opencv-python`) for biometric face processing
- NumPy, rembg, requests

Frontend
- Node.js / Express static server
- Vanilla HTML/CSS/JavaScript
- FontAwesome icons (CDN)
- Chart.js for dashboard charts

Database
- MySQL / MariaDB compatible engine
- Schema with triggers, foreign keys, check constraints, indexes

Authentication
- JWT tokens (`Authorization: Bearer ...`)
- Officer authentication via email/password
- Citizen portal login via NID/CNIC + citizen_id

Third-party services
- SMTP configuration supported for notifications
- No external API dependencies required for local evaluation

## 3. System Architecture

The application is a three-tier system:
1. Frontend: static pages served by `crida/frontend/server.js` and browser JS in `public/`
2. Backend: Flask API in `crida/backend/app.py` with blueprint-mounted routes under `/api/v1/`
3. Database: MySQL stores all citizen, officer, application, biometric, audit, payment, and notification data

Interaction flow:
- Browser requests `officerportal.html`, `citizen.html`, or `chatbot.html`
- JS sends API calls to `http://localhost:5000/api/v1/...`
- Backend validates JWT, applies RBAC, writes/reads data
- Database transactions and triggers protect consistency

## 4. UI Examples

### 4.1 Login / Officer Portal
- Page: `crida/frontend/public/officerportal.html`
- Purpose: authenticate officers, display role-based menus, and restrict access
- Required because it gates all administrative workflows and enables audit tracking

### 4.2 Dashboard & Citizen Search
- Page: `crida/frontend/public/officerportal.html` (dashboard tab)
- Purpose: show citizen/application stats, allow quick lookup of citizen records
- Required because it provides oversight and fast navigation for officers

### 4.3 Biometric Enrollment & Verification
- Page: `crida/frontend/public/officerportal.html` (biometric tab)
- Purpose: enroll face/fingerprint hashes, upload photos, verify biometric data
- Required because biometric identity proof is a central project feature

> Note: screenshot files are not included in the repository. Evaluators can capture these pages after running the app.

## 5. Setup & Installation

### Prerequisites
- Node.js 18+ installed
- Python 3.10+ installed
- MySQL 8.0 / compatible engine installed
- `mysql` CLI available

### Backend installation

```bash
cd crida/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Frontend installation

```bash
cd crida/frontend
npm install
```

### Configure `.env`

Copy the example file and update values:

```bash
cd crida/backend
cp .env.example .env
```

`.env` variables:
- `DB_HOST` — database host, usually `localhost`
- `DB_PORT` — database port, usually `3306`
- `DB_USER` — application DB user (`crida_user`)
- `DB_PASSWORD` — application DB password (`crida_pass`)
- `DB_NAME` — database name (`CRID`)
- `DB_POOL_SIZE` — connection pool size
- `JWT_SECRET_KEY` — secret used to sign JWT tokens
- `JWT_EXPIRY_HOURS` — token expiration time in hours
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM` — optional email settings

Example `.env`:

```text
DB_HOST=localhost
DB_PORT=3306
DB_USER=crida_user
DB_PASSWORD=crida_pass
DB_NAME=CRID
DB_POOL_SIZE=5
JWT_SECRET_KEY=replace_with_a_secure_random_string
JWT_EXPIRY_HOURS=24
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
SMTP_FROM=noreply@crida.pk
```

### Initialize the database

From repository root:

```bash
sudo mysql -u root -p < crida/backend/setup_database.sql
sudo mysql -u root -p CRID < seed_2.sql
```

### Start the servers

Backend:

```bash
cd crida/backend
source venv/bin/activate
python app.py
```

Frontend:

```bash
cd crida/frontend
node server.js
```

Open `http://localhost:3000` in the browser.

## 6. User Roles

### Seeded roles and credentials

`seed_2.sql` creates 100 officers. Role assignment is `(n % 5) + 1`.

| Role | Example email(s) | Password | Notes |
|------|------------------|----------|-------|
| Admin | `officer5@crida.pk`, `officer10@crida.pk`, ... | `Admin@1234` for first Admin (`officer5`); others use `hash` | role_id = 1 |
| Registrar | `officer1@crida.pk`, `officer6@crida.pk`, ... | `hash` | role_id = 2 |
| Passport_Officer | `officer2@crida.pk`, `officer7@crida.pk`, ... | `hash` | role_id = 3 |
| License_Officer | `officer3@crida.pk`, `officer8@crida.pk`, ... | `hash` | role_id = 4 |
| Security_Officer | `officer4@crida.pk`, `officer9@crida.pk`, ... | `hash` | role_id = 5 |

The `hash` string is accepted by the login routine for seeded demo accounts.

## 7. Feature Walkthrough

### Authentication
- Officer login: `/api/v1/auth/login`
- Citizen portal login: `/api/v1/auth/citizen-login`
- Profile: `/api/v1/auth/me`
- Password change: `/api/v1/auth/change-password`

### Citizen management
- Citizen search/listing: `/api/v1/citizens/`
- Dashboard stats: `/api/v1/citizens/stats`

### Registration services
- Birth registration: `/api/v1/registrations/birth`
- Death registration: `/api/v1/registrations/death`
- Marriage registration: `/api/v1/registrations/marriage`

### Document lifecycle
- CNIC applications: `/api/v1/cnic/`
- Passport applications: `/api/v1/passports/`
- Driving license applications: `/api/v1/licenses/`

### Biometric workflows
- Upload photo: `/api/v1/biometric/upload-photo`
- Enroll biometric data: `/api/v1/biometric/enroll`
- Verify fingerprint: `/api/v1/biometric/verify-fingerprint`
- Verify face: `/api/v1/biometric/verify-face`

### Security workflows
- Criminal records: `/api/v1/security/criminal-records`
- Watchlist: `/api/v1/security/watchlist`

## 8. Transaction Scenarios

### Change password
- Trigger: `PUT /api/v1/auth/change-password`
- Bundled operations: `UPDATE Officer`, `INSERT Audit_Log`
- Rollback: any error rolls back both operations
- Code: `crida/backend/routes/auth_routes.py`

### Birth registration
- Trigger: `POST /api/v1/registrations/birth`
- Bundled operations: `INSERT Birth_Registration`, `INSERT Audit_Log`
- Rollback: failure in either operation reverts the transaction
- Code: `crida/backend/routes/registration_routes.py`

### Death registration
- Trigger: `POST /api/v1/registrations/death`
- Bundled operations: `INSERT Death_Registration`, `INSERT Audit_Log`, trigger updates `Citizen.status`
- Rollback: any failure reverts the registration and status change
- Code: `crida/backend/routes/registration_routes.py`

### Marriage registration
- Trigger: `POST /api/v1/registrations/marriage`
- Bundled operations: `INSERT Marriage_Registration`, update two `Citizen.marital_status`, `INSERT Audit_Log`
- Rollback: failure in any step reverts all associated writes
- Code: `crida/backend/routes/registration_routes.py`

### CNIC approval
- Trigger: `PUT /api/v1/cnic/<id>/approve`
- Bundled operations: create or update `CNIC_Card`, update `CNIC_Application`, `INSERT Audit_Log`
- Rollback: if any write fails, the application approval and card issuance are rolled back
- Code: `crida/backend/routes/cnic_routes.py`

### Criminal record creation
- Trigger: `POST /api/v1/security/criminal-records`
- Bundled operations: `INSERT Criminal_Record`, `INSERT Audit_Log`
- Rollback: failure reverts both inserts
- Code: `crida/backend/routes/security_routes.py`

## 9. ACID Compliance

| Property | Implementation |
|---------|----------------|
| Atomicity | `execute_transaction_custom()` in `crida/backend/db.py` wraps related SQL operations and rolls back on error |
| Consistency | database constraints and triggers enforce valid values; e.g. `validate_marriage_requirements`, `validate_cnic_applicant_age`, `update_citizen_status_on_death` |
| Isolation | transactions use `READ COMMITTED` in `crida/backend/db.py` |
| Durability | committed MySQL writes persist; audit logs capture key actions |

## 10. Indexing & Performance

Indexes defined in `schema.sql`:
- `idx_citizen_national_id` on `Citizen(national_id_number)`
- `idx_officer_email` on `Officer(email)`
- `idx_cnic_app_citizen` on `CNIC_Application(citizen_id)`
- `idx_passport_app_citizen` on `Passport_Application(citizen_id)`
- `idx_dl_app_citizen` on `Driving_License_Application(citizen_id)`
- `idx_payment_citizen` on `Payment_Transaction(citizen_id)`
- `idx_cnic_app_status` on `CNIC_Application(status)`
- `idx_passport_app_status` on `Passport_Application(status)`
- `idx_dl_app_status` on `Driving_License_Application(status)`
- `idx_watchlist_citizen` on `Watchlist(citizen_id)`

Why these indexes exist:
- speed up citizen lookup and login validation
- accelerate application queries by citizen and status
- improve watchlist and payment lookups
- speed up officer login by email

Performance notes:
- no `performance.sql` script was present in the repository, so before/after timings are not available from that file

## 11. API Reference

| Method | Route | Auth | Purpose |
|--------|-------|------|---------|
| GET | `/api/v1/health` | no | health check |
| POST | `/api/v1/auth/login` | no | officer login |
| POST | `/api/v1/auth/citizen-login` | no | citizen portal login |
| GET | `/api/v1/auth/me` | yes | current profile |
| PUT | `/api/v1/auth/change-password` | yes | password update |
| GET | `/api/v1/citizens/` | yes | list/search citizens |
| POST | `/api/v1/registrations/birth` | yes | register birth |
| POST | `/api/v1/registrations/death` | yes | register death |
| POST | `/api/v1/registrations/marriage` | yes | register marriage |
| POST | `/api/v1/cnic/` | yes | submit CNIC application |
| PUT | `/api/v1/cnic/<id>/approve` | yes | approve CNIC application |
| PUT | `/api/v1/cnic/<id>/reject` | yes | reject CNIC application |
| GET | `/api/v1/cnic/card/<citizen_id>` | yes | retrieve CNIC card |
| POST | `/api/v1/biometric/upload-photo` | yes | save citizen photo |
| POST | `/api/v1/biometric/enroll` | yes | enroll biometric data |
| POST | `/api/v1/biometric/verify-fingerprint` | yes | verify fingerprint |
| POST | `/api/v1/biometric/verify-face` | yes | verify face image |
| GET | `/api/v1/security/criminal-records` | yes | list criminal records |
| POST | `/api/v1/security/criminal-records` | yes | add criminal record |
| GET | `/api/v1/security/watchlist` | yes | list watchlist entries |
| POST | `/api/v1/security/watchlist` | yes | add watchlist entry |

> `swagger.yaml` is not present in the repository.

## 12. Known Issues & Limitations

- `swagger.yaml` missing from the repo.
- `performance.sql` missing, so measured query benchmarks are unavailable.
- Many seeded officers use the placeholder password `hash` for demo login.
- Frontend is static vanilla JS/HTML and does not use a modern SPA framework.
- Biometric features require `localhost` or HTTPS secure context to work correctly.
- PDF generation and biometric modules require installed Python dependencies; missing packages can break functionality.

## Scripts

Backend:
- `pip install -r requirements.txt` — install backend dependencies
- `python app.py` — start Flask backend

Frontend:
- `npm install` — install frontend dependencies
- `node server.js` — start static frontend server
- `npm run dev` — run server with `nodemon` if available

## Important files

- `crida/backend/app.py` — Flask application and blueprint registration
- `crida/backend/db.py` — connection pool, query helpers, transaction helpers
- `crida/backend/config.py` — environment configuration
- `crida/backend/routes/` — API endpoint implementations
- `crida/backend/middleware/` — JWT authentication and RBAC enforcement
- `crida/backend/utils/` — PDFs, notifications, validators
- `crida/frontend/public/` — UI markup and portal scripts
- `schema.sql` — database schema, triggers, indexes
- `seed_2.sql` — seeded demo data and test users
