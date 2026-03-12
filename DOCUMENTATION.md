# CRIDA — Phase 2 Complete Documentation

## Citizen Registration & Identity Database Authority  
**Government-Grade Identity Management System**

---

## Table of Contents

1. [System Overview](#1-system-overview)  
2. [Technology Stack](#2-technology-stack)  
3. [Setup & Installation](#3-setup--installation)  
4. [Database Architecture](#4-database-architecture)  
5. [Feature 1: PDF Generation](#5-feature-1-pdf-generation)  
6. [Feature 2: Family Tree](#6-feature-2-family-tree)  
7. [Feature 3: Criminal Records](#7-feature-3-criminal-records)  
8. [Feature 4: Citizen Self-Update](#8-feature-4-citizen-self-update)  
9. [Feature 5: Camera + Background Removal](#9-feature-5-camera--background-removal)  
10. [Feature 6: Biometric Verification](#10-feature-6-biometric-verification)  
11. [Feature 7: Complaint System](#11-feature-7-complaint-system)  
12. [Feature 8: Granular Permissions](#12-feature-8-granular-permissions)  
13. [Feature 9: Notifications + Email](#13-feature-9-notifications--email)  
14. [Feature 10: Node.js Frontend](#14-feature-10-nodejs-frontend)  
15. [API Reference](#15-api-reference)  
16. [Security Architecture](#16-security-architecture)

---

## 1. System Overview

CRIDA is a full-stack government identity management system. Phase 1 built the foundational schema (20+ tables), triggers, views, and constraints. Phase 2 adds 10 major features on top:

```
┌─────────────────────────────────────────────┐
│                CRIDA Frontend               │
│         (Node.js Express.js SPA)            │
│     HTML / CSS / Vanilla JavaScript         │
├─────────────────────────────────────────────┤
│              REST API Layer                 │
│         Flask + JWT + RBAC + CORS           │
│         18 Blueprint Modules                │
├─────────────────────────────────────────────┤
│            MySQL Database (CRID)            │
│   25+ Tables │ Triggers │ Views │ Indexes   │
└─────────────────────────────────────────────┘
```

## 2. Technology Stack

| Layer      | Technology                                     |
|------------|------------------------------------------------|
| Backend    | Python 3.12, Flask, flask-cors, flask-bcrypt   |
| Database   | MySQL 8.0, mysql-connector-python              |
| Auth       | JWT (PyJWT), bcrypt password hashing           |
| PDF        | fpdf2 (pure Python PDF generation)             |
| Images     | Pillow, face_recognition (optional), rembg     |
| Frontend   | Node.js, Express.js, Vanilla JS + CSS          |
| Email      | smtplib (built-in Python SMTP)                 |

## 3. Setup & Installation

### Step 1: Database Setup  
```bash
# Start MySQL
sudo systemctl start mysql

# Run the safe one-shot setup (creates user + tables)
sudo mysql -u root -p < backend/setup_database.sql

# Seed data (first-time only)
sudo mysql -u root -p CRID < seed_2.sql
```

### Step 2: Backend  
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```
Backend runs on **http://localhost:5000**

### Step 3: Frontend  
```bash
cd frontend/public
python3 -m http.server 3000
```
Frontend runs on **http://localhost:3000**

### Environment Variables (.env)
```
DB_HOST=localhost
DB_PORT=3306
DB_USER=crida_user
DB_PASSWORD=crida_pass
DB_NAME=CRID
JWT_SECRET_KEY=your-super-secret-key
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=   (optional)
SMTP_PASS=   (optional)
SMTP_FROM=   (optional)
```

---

## 5. Feature 1: PDF Generation

### Internal Working
Uses `fpdf2` to generate government-standard PDF documents with no external API calls.

**File:** `backend/utils/pdf_generator.py`  
**Routes:** `backend/routes/pdf_routes.py`

### Process Flow
```
1. Frontend sends GET /api/v1/pdf/{type}/{citizen_id}
2. Backend queries the relevant tables (Citizen, CNIC_Card, Passport, etc.)
3. PDFGenerator class creates a PDF with:
   - CRIDA header + logo
   - Citizen photo (if available from camera capture)
   - Document-specific data (ID numbers, dates, etc.)
   - Official formatting and borders
4. PDF is returned as a file download
```

### Supported Documents
| Endpoint | Document |
|----------|----------|
| `GET /api/v1/pdf/cnic/{cid}` | CNIC Card |
| `GET /api/v1/pdf/passport/{cid}` | Passport |
| `GET /api/v1/pdf/license/{cid}` | Driving License |
| `GET /api/v1/pdf/birth-certificate/{cid}` | Birth Certificate |
| `GET /api/v1/pdf/death-certificate/{cid}` | Death Certificate |
| `GET /api/v1/pdf/marriage-certificate/{mid}` | Marriage Certificate |
| `GET /api/v1/pdf/payment-slip/{pid}` | Payment Slip |

---

## 6. Feature 2: Family Tree

### Internal Working
Recursively builds a citizen's family hierarchy from the `Family_Relationship` and `Marriage_Registration` tables.

**File:** `backend/routes/family_tree_routes.py`

### Process Flow
```
1. Frontend sends GET /api/v1/family-tree/{citizen_id}
2. Backend queries Family_Relationship for all related citizens
3. Checks Marriage_Registration for spouse connection
4. Returns structured JSON with:
   - citizen: Primary citizen details
   - spouse: Spouse details (if married)
   - relationships: Array of related citizens with types
     (Father, Mother, Son, Daughter, Brother, Sister, etc.)
```

### SQL Queries Used
- `Family_Relationship` joined with `Citizen` for each relative
- `Marriage_Registration` for husband-wife links
- Recursive lookup across multiple relationship levels

---

## 7. Feature 3: Criminal Records

### Internal Working
Displays criminal records from the `Criminal_Record` table, filterable by citizen.

**File:** `backend/routes/security_routes.py`

### Endpoints
| Endpoint | Action |
|----------|--------|
| `GET /api/v1/criminal-records` | List all (filterable by citizen_id) |
| `POST /api/v1/criminal-records` | Add new record |
| `PUT /api/v1/criminal-records/{id}` | Update record status |

### Data Fields
- case_number, offense, offense_date, conviction_date, sentence, status, court_name
- Status tracking: Charged → On Trial → Convicted/Acquitted

---

## 8. Feature 4: Citizen Self-Update

### Internal Working
Citizens request changes; officers approve/reject. Approved changes are applied **transactionally** using `execute_transaction_custom()`.

**File:** `backend/routes/update_request_routes.py`  
**Table:** `Update_Request`

### Process Flow
```
1. Citizen submits POST /api/v1/update-requests
   { citizen_id, field_name, new_value, reason }
2. Backend stores request with status='Pending'
3. Officer reviews and calls:
   PUT /api/v1/update-requests/{id}/approve  — or —
   PUT /api/v1/update-requests/{id}/reject
4. On approval:
   a. Wraps in execute_transaction_custom (ACID)
   b. Updates Citizen table with new value
   c. Sets Update_Request status to 'Approved'
   d. Sends notification to citizen
   e. All steps commit or all rollback
```

### ACID Properties
- **Atomicity:** Transaction wraps both the citizen update and request status change
- **Consistency:** Only allowed fields can be updated
- **Isolation:** MySQL InnoDB row-level locking
- **Durability:** Committed to disk via InnoDB write-ahead log

---

## 9. Feature 5: Camera + Background Removal

### Internal Working
Captures a webcam image, detects a single person, removes the background, saves the processed image.

**File:** `backend/routes/camera_routes.py`

### Process Flow
```
1. Frontend captures webcam frame → base64 JPEG
2. POST /api/v1/camera/capture { citizen_id, image }
3. Backend decodes base64 → PIL Image
4. face_recognition library detects face locations
   - Rejects if 0 faces (no person) or 2+ faces (multiple people)
5. rembg removes background → transparent PNG
6. Saves to backend/uploads/photos/{citizen_id}.png
7. Updates Citizen.photo_path in database
8. Photo is now available for PDF generation
```

### Graceful Fallback
If `face_recognition` or `rembg` are not installed, the route still works:
- Skips face detection (accepts any image)
- Skips background removal (saves original)
- Logs a warning for the operator

---

## 10. Feature 6: Biometric Verification

### Internal Working
Two modes of verification: facial recognition and fingerprint hash matching.

**File:** `backend/routes/biometric_routes.py`  
**Table:** `Biometric_Data`

### Facial Recognition
```
1. POST /api/v1/biometric/verify-face { citizen_id, image }
2. Loads citizen's stored photo from photo_path
3. Uses face_recognition to encode both faces
4. Computes face_distance between encodings
5. Returns verified=true/false with confidence score
```

### Fingerprint Verification
```
1. POST /api/v1/biometric/verify-fingerprint { citizen_id, fingerprint_hash }
2. Queries Biometric_Data for stored fingerprint_hash
3. Compares hashes (constant-time comparison for security)
4. Returns verified=true/false
```

### Enrollment
```
POST /api/v1/biometric/enroll { citizen_id, fingerprint_hash, facial_scan_hash }
- Inserts or updates Biometric_Data record
```

---

## 11. Feature 7: Complaint System

### Internal Working
Full CRUD complaint lifecycle with officer assignment and resolution tracking.

**File:** `backend/routes/complaint_routes.py`  
**Table:** `Complaint`

### Endpoints
| Method | Endpoint | Action |
|--------|----------|--------|
| GET | `/api/v1/complaints` | List all complaints (paginated) |
| POST | `/api/v1/complaints` | Submit new complaint |
| GET | `/api/v1/complaints/{id}` | Get single complaint |
| PUT | `/api/v1/complaints/{id}` | Update status/assign/resolve |
| DELETE | `/api/v1/complaints/{id}` | Delete complaint |

### Lifecycle
```
Open → In Progress → Resolved → Closed
```
- Officers can assign complaints to themselves
- Resolution notes are recorded
- Notifications sent to citizen on status change

---

## 12. Feature 8: Granular Permissions

### Internal Working
Beyond role-based access (Admin, Registrar, etc.), individual officers can be granted specific permissions.

**File:** `backend/middleware/rbac.py`  
**Table:** `Permission`

### Available Permissions (12)
```
manage_citizens, manage_cnic, manage_passport, manage_license,
manage_registrations, manage_security, manage_complaints,
view_reports, manage_officers, manage_payments,
generate_pdf, manage_biometric
```

### How It Works
```python
@token_required
@permission_required('manage_citizens', 'manage_cnic')
def my_endpoint():
    # Only officers with BOTH permissions can access
    ...
```

1. Admin role always bypasses permission checks
2. For other roles, the decorator queries the Permission table
3. If the officer has at least one of the listed permissions, access is granted

---

## 13. Feature 9: Notifications + Email

### Internal Working
In-app notifications stored in the database + automated SMTP emails.

**File:** `backend/utils/notifications.py`  
**File:** `backend/routes/notification_routes.py`  
**Table:** `Notification`

### In-App Notifications
```
1. Any operation (complaint resolved, update approved, etc.)
   calls send_notification(citizen_id, title, message, type, category)
2. Notification stored in Notification table with is_read=false
3. Frontend polls GET /api/v1/notifications?citizen_id=X
4. User marks as read via PUT /api/v1/notifications/{id}/read
```

### Email Notifications
```
1. When SMTP is configured in .env, send_email() sends via smtplib
2. Uses TLS encryption on port 587
3. If SMTP not configured, silently skips (no crash)
4. Email sending is non-blocking (doesn't slow down the API response)
```

### ACID Integration
When transactions complete successfully (e.g., citizen update approved), the system:
1. Commits the database transaction
2. Sends in-app notification
3. Attempts email notification (if SMTP configured)
4. Returns success to the client

---

## 14. Feature 10: Node.js Frontend

### Architecture
A single-page application (SPA) built with vanilla HTML, CSS, and JavaScript, served via Express.js or Python's http.server.

### Pages
| Page | Features |
|------|----------|
| Dashboard | Stats overview, feature quick-links |
| Citizens | View all citizens, quick-actions |
| Family Tree | Enter citizen ID → visual tree |
| Criminal Records | Search and view criminal history |
| PDF Generation | Select document type → download |
| Photo Capture | Webcam → face detect → BG removal |
| Biometric Auth | Face recognition / fingerprint verify |
| Complaints | Submit and manage complaints |
| Update Requests | Submit / approve / reject changes |
| Notifications | View citizen notifications |
| Permissions | View permission system overview |

### Design System
- Dark mode with glassmorphism effects
- Font Awesome icons
- Responsive CSS grid layouts
- Toast notification system
- Status badges with semantic colors

---

## 15. API Reference

### Authentication
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /api/v1/auth/login | None | Login, get JWT |
| GET | /api/v1/auth/me | JWT | Get profile |
| PUT | /api/v1/auth/change-password | JWT | Change password |

### Citizens
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /api/v1/citizens | JWT | List citizens |
| GET | /api/v1/citizens/{id} | JWT | Get citizen |
| POST | /api/v1/citizens | JWT | Create citizen |
| PUT | /api/v1/citizens/{id} | JWT | Update citizen |

### Documents (PDF)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /api/v1/pdf/cnic/{cid} | JWT | Generate CNIC PDF |
| GET | /api/v1/pdf/passport/{cid} | JWT | Generate Passport PDF |
| GET | /api/v1/pdf/license/{cid} | JWT | Generate License PDF |
| GET | /api/v1/pdf/birth-certificate/{cid} | JWT | Birth Certificate |
| GET | /api/v1/pdf/death-certificate/{cid} | JWT | Death Certificate |
| GET | /api/v1/pdf/marriage-certificate/{mid} | JWT | Marriage Certificate |
| GET | /api/v1/pdf/payment-slip/{pid} | JWT | Payment Slip |

### Family & Security
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /api/v1/family-tree/{cid} | JWT | Get family tree |
| GET | /api/v1/criminal-records | JWT | List criminal records |
| POST | /api/v1/criminal-records | JWT+Role | Add criminal record |

### Services
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /api/v1/camera/capture | JWT | Capture & process photo |
| POST | /api/v1/biometric/verify-face | JWT | Face verification |
| POST | /api/v1/biometric/verify-fingerprint | JWT | Fingerprint verification |
| GET/POST | /api/v1/complaints | JWT | List / create complaints |
| PUT | /api/v1/complaints/{id} | JWT | Update complaint |
| GET/POST | /api/v1/update-requests | JWT | List / submit update requests |
| PUT | /api/v1/update-requests/{id}/approve | JWT | Approve request |
| PUT | /api/v1/update-requests/{id}/reject | JWT | Reject request |
| GET | /api/v1/notifications | JWT | List notifications |
| PUT | /api/v1/notifications/{id}/read | JWT | Mark notification as read |

---

## 16. Security Architecture

### Authentication
- Password hashing: bcrypt (with legacy plaintext fallback for seed data)
- JWT tokens with configurable expiration (default: 24 hours)
- Token validated on every request via `@token_required` decorator

### Authorization (3 layers)
1. **Role-Based (RBAC):** Admin, Registrar, Passport_Officer, License_Officer, Security_Officer
2. **Access Level:** Numeric levels 1-5 for hierarchical access
3. **Granular Permissions:** 12 specific permissions per officer

### Data Protection
- All SQL queries use parameterized placeholders (%s) — no string concatenation
- Input validation on all endpoints
- CORS enabled for development (configurable for production)
- Audit logging for all significant actions

### Database Constraints
- Foreign keys with ON DELETE RESTRICT / CASCADE
- CHECK constraints on critical fields (age, dates, amounts)
- Triggers for business logic enforcement (age validation, auto-expire, watchlist blocks)
- UNIQUE constraints on IDs and references
