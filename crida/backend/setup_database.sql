-- ============================================================
-- setup_database.sql
-- Run ONCE as root: sudo mysql -u root -p CRID < setup_database.sql
-- Creates crida_user and adds the 4 Phase 2 tables only.
-- Phase 1 tables are NEVER modified.
-- ============================================================

-- 1. Create application user
CREATE USER IF NOT EXISTS 'crida_user'@'localhost'
    IDENTIFIED BY 'crida_pass';
GRANT ALL PRIVILEGES ON CRID.* TO 'crida_user'@'localhost';
FLUSH PRIVILEGES;

USE CRID;

-- ----------------------------------------------------------------
-- 2. Permission table
--    Granular per-officer permissions (beyond role-based access).
--    Admin role always bypasses; other roles need explicit entries.
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Permission (
    permission_id   INT PRIMARY KEY AUTO_INCREMENT,
    officer_id      INT NOT NULL,
    permission_name ENUM(
        'manage_citizens', 'manage_cnic', 'manage_passport',
        'manage_license', 'manage_registrations', 'manage_security',
        'manage_complaints', 'view_reports', 'manage_officers',
        'manage_payments', 'generate_pdf', 'manage_biometric'
    ) NOT NULL,
    granted_by  INT NULL,
    granted_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_officer_perm (officer_id, permission_name),

    FOREIGN KEY (officer_id)  REFERENCES Officer(officer_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (granted_by)  REFERENCES Officer(officer_id)
        ON DELETE SET NULL ON UPDATE CASCADE
);

-- ----------------------------------------------------------------
-- 3. Notification table
--    Stores in-app notifications + tracks whether email was sent.
--    Supports both citizen-facing and officer-facing notifications.
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Notification (
    notification_id   INT PRIMARY KEY AUTO_INCREMENT,
    citizen_id        INT NULL,
    officer_id        INT NULL,
    title             VARCHAR(200) NOT NULL,
    message           TEXT NOT NULL,
    notification_type ENUM('info', 'success', 'warning', 'error') DEFAULT 'info',
    category          ENUM('transaction', 'document', 'security', 'system', 'appointment') DEFAULT 'system',
    is_read           BOOLEAN DEFAULT FALSE,
    email_sent        BOOLEAN DEFAULT FALSE,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (citizen_id) REFERENCES Citizen(citizen_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (officer_id) REFERENCES Officer(officer_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- ----------------------------------------------------------------
-- 4. Update_Request table
--    Citizens submit field-change requests; officers approve/reject.
--    Approval uses ACID transaction: citizen update + status change.
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Update_Request (
    request_id       INT PRIMARY KEY AUTO_INCREMENT,
    citizen_id       INT NOT NULL,
    field_name       VARCHAR(100) NOT NULL,
    old_value        TEXT NULL,
    new_value        TEXT NOT NULL,
    reason           TEXT NULL,
    status           ENUM('Pending', 'Approved', 'Rejected') DEFAULT 'Pending',
    reviewed_by      INT NULL,
    reviewed_at      DATETIME NULL,
    rejection_reason TEXT NULL,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (citizen_id)  REFERENCES Citizen(citizen_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (reviewed_by) REFERENCES Officer(officer_id)
        ON DELETE SET NULL ON UPDATE CASCADE
);

-- ----------------------------------------------------------------
-- 5. Complaint table
--    Full lifecycle: Open → In Progress → Resolved → Closed.
--    Assigned officer and resolution notes are tracked.
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Complaint (
    complaint_id INT PRIMARY KEY AUTO_INCREMENT,
    citizen_id   INT NOT NULL,
    subject      VARCHAR(200) NOT NULL,
    description  TEXT NOT NULL,
    status       ENUM('Open', 'In Progress', 'Resolved', 'Closed') DEFAULT 'Open',
    assigned_to  INT NULL,
    resolution   TEXT NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (citizen_id)  REFERENCES Citizen(citizen_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (assigned_to) REFERENCES Officer(officer_id)
        ON DELETE SET NULL ON UPDATE CASCADE
);

-- ----------------------------------------------------------------
-- 6. Seed default Admin password (bcrypt hash of 'admin123')
--    Only updates the first Admin-role officer from Phase 1 seed.
-- ----------------------------------------------------------------
UPDATE Officer
SET password_hash = '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4oHH1bxRUi'
WHERE role_id = 1
LIMIT 1;

SELECT 'setup_database.sql executed successfully.' AS status;
