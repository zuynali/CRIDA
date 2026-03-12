USE CRID;
CREATE TABLE Citizen(
    citizen_id INT PRIMARY KEY AUTO_INCREMENT,
    national_id_number VARCHAR(13) UNIQUE NOT NULL,
    first_name VARCHAR(50) NOT NULL,  
    last_name VARCHAR(50) NOT NULL,   
    dob DATE NOT NULL,
    gender ENUM('Male','Female','Other') NOT NULL,  
    marital_status ENUM('Single','Married','Divorced','Widowed') DEFAULT 'Single',
    blood_group ENUM('A+','A-','B+','B-','AB+','AB-','O+','O-'),
    status ENUM('active','deceased','blacklisted') DEFAULT 'active',
    CONSTRAINT chk_id_length CHECK (national_id_number REGEXP '^[0-9]{13}$')
);


CREATE TABLE Address( 
    address_id INT AUTO_INCREMENT PRIMARY KEY,
    house_no VARCHAR(20),
    street VARCHAR(100),  
    city VARCHAR(50) NOT NULL,      
    province VARCHAR(50) NOT NULL, 
    postal_code VARCHAR(10) 
);


CREATE TABLE Hospital(
    hospital_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    city VARCHAR(50) NOT NULL,
    province VARCHAR(50) NOT NULL,
    contact_number VARCHAR(20),  
    CONSTRAINT chk_hospital_number CHECK (contact_number REGEXP '^[0-9]{11}$')
);

CREATE TABLE Office (
    office_id INT PRIMARY KEY AUTO_INCREMENT,
    office_name VARCHAR(100) NOT NULL,
    office_type ENUM('Head Office','Regional','City','Tehsil') NOT NULL,
    city VARCHAR(50) NOT NULL,
    province VARCHAR(50) NOT NULL,
    contact_number VARCHAR(20),
    address VARCHAR(200),
    CONSTRAINT chk_office_number CHECK (contact_number REGEXP '^[0-9]{11}$')
);


CREATE TABLE Citizen_Address_History(
    history_id INT AUTO_INCREMENT PRIMARY KEY,
    citizen_id INT NOT NULL,
    address_id INT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NULL,  
    FOREIGN KEY (citizen_id) REFERENCES Citizen(citizen_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (address_id) REFERENCES Address(address_id) ON DELETE RESTRICT ON UPDATE CASCADE
);


CREATE TABLE Family_Relationship(
    relationship_id INT AUTO_INCREMENT PRIMARY KEY,
    citizen_id INT NOT NULL,
    related_citizen_id INT NOT NULL,
    relationship_type ENUM('Father','Mother','Son','Daughter','Husband','Wife','Brother','Sister') NOT NULL,
    FOREIGN KEY (citizen_id) REFERENCES Citizen(citizen_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (related_citizen_id) REFERENCES Citizen(citizen_id) ON DELETE RESTRICT ON UPDATE CASCADE
);


DELIMITER //
CREATE TRIGGER trk_not_self
BEFORE INSERT ON Family_Relationship
FOR EACH ROW
BEGIN
    IF NEW.citizen_id = NEW.related_citizen_id THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Error: A citizen cannot be related to themselves!';
    END IF;
END //
DELIMITER ;



CREATE TABLE Role (
    role_id INT PRIMARY KEY AUTO_INCREMENT,
    role_name ENUM('Admin','Registrar','Passport_Officer','License_Officer','Security_Officer') UNIQUE NOT NULL,
    description VARCHAR(200),
    access_level INT NOT NULL CHECK (access_level BETWEEN 1 AND 5)
);


CREATE TABLE Officer (
    officer_id INT PRIMARY KEY AUTO_INCREMENT,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    role_id INT NOT NULL,
    office_id INT NOT NULL,
    employee_id VARCHAR(50) UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (role_id) REFERENCES Role(role_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (office_id) REFERENCES Office(office_id) ON DELETE RESTRICT ON UPDATE CASCADE
);


CREATE TABLE Birth_Registration (
    birth_id INT PRIMARY KEY AUTO_INCREMENT,
    citizen_id INT NOT NULL,
    hospital_id INT,
    registrar_officer_id INT NOT NULL,
    registration_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    birth_certificate_number VARCHAR(30) UNIQUE,
    FOREIGN KEY (citizen_id) REFERENCES Citizen(citizen_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (hospital_id) REFERENCES Hospital(hospital_id) ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY (registrar_officer_id) REFERENCES Officer(officer_id) ON DELETE RESTRICT ON UPDATE CASCADE
);


CREATE TABLE Death_Registration (
    death_id INT PRIMARY KEY AUTO_INCREMENT,
    citizen_id INT NOT NULL,
    cause_of_death VARCHAR(200),
    date_of_death DATE NOT NULL,
    place_of_death VARCHAR(100),
    registrar_officer_id INT NOT NULL,
    death_certificate_number VARCHAR(30) UNIQUE,
    FOREIGN KEY (citizen_id) REFERENCES Citizen(citizen_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (registrar_officer_id) REFERENCES Officer(officer_id) ON DELETE RESTRICT ON UPDATE CASCADE
);


CREATE TABLE Marriage_Registration (
    marriage_id INT PRIMARY KEY AUTO_INCREMENT,
    husband_id INT NOT NULL,
    wife_id INT NOT NULL,
    marriage_date DATE NOT NULL,
    registration_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    registrar_officer_id INT NOT NULL,
    marriage_certificate_number VARCHAR(30) UNIQUE,
    FOREIGN KEY (husband_id) REFERENCES Citizen(citizen_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (wife_id) REFERENCES Citizen(citizen_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (registrar_officer_id) REFERENCES Officer(officer_id) ON DELETE RESTRICT ON UPDATE CASCADE
);


CREATE TABLE CNIC_Application (
    application_id INT PRIMARY KEY AUTO_INCREMENT,
    citizen_id INT NOT NULL,
    application_type ENUM('New','Renewal','Replacement') NOT NULL,
    submission_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status ENUM('Pending','Under Review','Approved','Rejected') DEFAULT 'Pending',
    office_id INT NOT NULL,
    rejection_reason VARCHAR(200),
    FOREIGN KEY (citizen_id) REFERENCES Citizen(citizen_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (office_id) REFERENCES Office(office_id) ON DELETE RESTRICT ON UPDATE CASCADE
);


CREATE TABLE CNIC_Card (
    card_id INT PRIMARY KEY AUTO_INCREMENT,
    citizen_id INT UNIQUE NOT NULL,
    card_number VARCHAR(20) UNIQUE NOT NULL,
    issue_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    card_status ENUM('Active','Expired','Blocked','Damaged') DEFAULT 'Active',
    fingerprint_verified BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (citizen_id) REFERENCES Citizen(citizen_id) ON DELETE RESTRICT ON UPDATE CASCADE
);


CREATE TABLE Passport_Application (
    passport_app_id INT PRIMARY KEY AUTO_INCREMENT,
    citizen_id INT NOT NULL,
    application_type ENUM('New','Renewal','Lost Replacement') NOT NULL,
    submission_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status ENUM('Draft','Submitted','Under Review','Approved','Rejected','Ready for Collection','Collected') DEFAULT 'Draft',
    office_id INT NOT NULL,
    fee_paid BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (citizen_id) REFERENCES Citizen(citizen_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (office_id) REFERENCES Office(office_id) ON DELETE RESTRICT ON UPDATE CASCADE
);


CREATE TABLE Passport (
    passport_id INT PRIMARY KEY AUTO_INCREMENT,
    citizen_id INT NOT NULL,
    passport_number VARCHAR(20) UNIQUE NOT NULL,
    issue_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    passport_status ENUM('Valid','Expired','Cancelled','Reported Lost') DEFAULT 'Valid',
    FOREIGN KEY (citizen_id) REFERENCES Citizen(citizen_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_passport_expiry CHECK (expiry_date = DATE_ADD(issue_date, INTERVAL 10 YEAR))  -- ADDED
);


CREATE TABLE Driving_License_Application (
    dl_app_id INT PRIMARY KEY AUTO_INCREMENT,
    citizen_id INT NOT NULL,
    license_type ENUM('Motorcycle','Car','Commercial','Heavy Vehicle') NOT NULL,
    submission_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status ENUM('Pending','Test Scheduled','Test Passed','Test Failed','Approved','Rejected') DEFAULT 'Pending',
    test_result ENUM('Pass','Fail') NULL,
    test_date DATE NULL,
    office_id INT NOT NULL,
    FOREIGN KEY (citizen_id) REFERENCES Citizen(citizen_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (office_id) REFERENCES Office(office_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_test_result_consistency CHECK (
        (status IN ('Test Passed', 'Test Failed') AND test_result IS NOT NULL AND test_date IS NOT NULL)
        OR (status NOT IN ('Test Passed', 'Test Failed') AND test_result IS NULL)
    )
);

CREATE TABLE Driving_License (
    license_id INT PRIMARY KEY AUTO_INCREMENT,
    citizen_id INT NOT NULL,
    license_number VARCHAR(20) UNIQUE NOT NULL,
    issue_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    license_type ENUM('Motorcycle','Car','Commercial','Heavy Vehicle') NOT NULL,
    status ENUM('Valid','Expired','Suspended','Revoked') DEFAULT 'Valid',
    FOREIGN KEY (citizen_id) REFERENCES Citizen(citizen_id) ON DELETE RESTRICT ON UPDATE CASCADE
);


CREATE TABLE Biometric_Data (
    biometric_id INT PRIMARY KEY AUTO_INCREMENT,
    citizen_id INT UNIQUE NOT NULL,
    fingerprint_hash VARCHAR(256) NOT NULL,
    facial_scan_hash VARCHAR(256) NOT NULL,
    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (citizen_id) REFERENCES Citizen(citizen_id) ON DELETE RESTRICT ON UPDATE CASCADE
);


CREATE TABLE Criminal_Record (
    record_id INT PRIMARY KEY AUTO_INCREMENT,
    citizen_id INT NOT NULL,
    case_number VARCHAR(50) UNIQUE,
    offense VARCHAR(200) NOT NULL,
    offense_date DATE NOT NULL,
    conviction_date DATE NULL,
    sentence VARCHAR(200),
    status ENUM('Charged','On Trial','Convicted','Acquitted') NOT NULL,
    court_name VARCHAR(100),
    FOREIGN KEY (citizen_id) REFERENCES Citizen(citizen_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_conviction_after_offense CHECK (conviction_date >= offense_date OR conviction_date IS NULL)
);

CREATE TABLE Watchlist (
    watchlist_id INT PRIMARY KEY AUTO_INCREMENT,
    citizen_id INT UNIQUE NOT NULL,
    reason VARCHAR(200) NOT NULL,
    added_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    added_by INT NOT NULL,
    watchlist_type ENUM('Security','Fraud','Immigration','Court Order') NOT NULL,
    expiry_date DATE NULL,
    FOREIGN KEY (citizen_id) REFERENCES Citizen(citizen_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (added_by) REFERENCES Officer(officer_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_expiry_after_add CHECK (expiry_date >= DATE(added_date) OR expiry_date IS NULL)
);


CREATE TABLE Appointment (
    appointment_id INT PRIMARY KEY AUTO_INCREMENT,
    citizen_id INT NOT NULL,
    office_id INT NOT NULL,
    service_type ENUM('CNIC','Passport','Driving License','Birth Registration',
                      'Death Registration','Marriage Registration') NOT NULL,
    appointment_date DATETIME NOT NULL,
    status ENUM('Scheduled','Completed','Cancelled','No Show') DEFAULT 'Scheduled',
    officer_id INT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (citizen_id) REFERENCES Citizen(citizen_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (office_id) REFERENCES Office(office_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (officer_id) REFERENCES Officer(officer_id) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT chk_appointment_future CHECK (appointment_date >= created_at)
);


CREATE TABLE Document (
    document_id INT PRIMARY KEY AUTO_INCREMENT,
    citizen_id INT NOT NULL,
    application_id INT NULL,
    document_type ENUM('photo','signature','supporting_doc') NOT NULL,  -- FIXED: Added NOT NULL
    file_path VARCHAR(255) NOT NULL,  -- FIXED: Added NOT NULL
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    verification_status ENUM('pending','approved','rejected') DEFAULT 'pending',  -- FIXED: Added DEFAULT
    verified_by INT NULL,
    FOREIGN KEY (citizen_id) REFERENCES Citizen(citizen_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (verified_by) REFERENCES Officer(officer_id) ON DELETE SET NULL ON UPDATE CASCADE
);


CREATE TABLE Audit_Log (
    log_id INT PRIMARY KEY AUTO_INCREMENT,
    officer_id INT NOT NULL,
    action_type ENUM('INSERT','UPDATE','DELETE','VIEW','LOGIN','LOGOUT') NOT NULL,
    table_name VARCHAR(50) NOT NULL,
    record_id INT NULL,
    old_values TEXT NULL,
    new_values TEXT NULL,
    ip_address VARCHAR(45) NULL,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (officer_id) REFERENCES Officer(officer_id) ON DELETE RESTRICT ON UPDATE CASCADE
);


CREATE TABLE Payment_Transaction (
    payment_id INT PRIMARY KEY AUTO_INCREMENT,
    citizen_id INT NOT NULL,
    service_type ENUM('CNIC','Passport','Driving License','Birth Certificate',
                      'Death Certificate','Marriage Certificate') NOT NULL,
    
    cnic_app_id INT NULL,
    passport_app_id INT NULL,
    dl_app_id INT NULL,
    
    amount DECIMAL(10,2) NOT NULL,
    payment_method ENUM('Cash','Credit Card','Debit Card','Bank Transfer','Online') NOT NULL,
    payment_status ENUM('Pending','Completed','Failed','Refunded') DEFAULT 'Pending',
    transaction_reference VARCHAR(100) UNIQUE,
    payment_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (citizen_id) REFERENCES Citizen(citizen_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (cnic_app_id) REFERENCES CNIC_Application(application_id) ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY (passport_app_id) REFERENCES Passport_Application(passport_app_id) ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY (dl_app_id) REFERENCES Driving_License_Application(dl_app_id) ON DELETE SET NULL ON UPDATE CASCADE,
    
    CONSTRAINT chk_amount_positive CHECK (amount > 0)
);







CREATE INDEX idx_citizen_national_id ON Citizen(national_id_number);


CREATE INDEX idx_cnic_app_citizen ON CNIC_Application(citizen_id);
CREATE INDEX idx_passport_app_citizen ON Passport_Application(citizen_id);
CREATE INDEX idx_dl_app_citizen ON Driving_License_Application(citizen_id);
CREATE INDEX idx_payment_citizen ON Payment_Transaction(citizen_id);


CREATE INDEX idx_cnic_app_status ON CNIC_Application(status);
CREATE INDEX idx_passport_app_status ON Passport_Application(status);
CREATE INDEX idx_dl_app_status ON Driving_License_Application(status);


CREATE INDEX idx_watchlist_citizen ON Watchlist(citizen_id);

CREATE INDEX idx_officer_email ON Officer(email);




DELIMITER //

CREATE TRIGGER update_citizen_status_on_death
AFTER INSERT ON Death_Registration
FOR EACH ROW
BEGIN
    UPDATE Citizen 
    SET status = 'deceased' 
    WHERE citizen_id = NEW.citizen_id;
END//

DELIMITER ;



DELIMITER //

CREATE TRIGGER create_cnic_card_on_approval
AFTER UPDATE ON CNIC_Application
FOR EACH ROW
BEGIN
    IF NEW.status = 'Approved' AND OLD.status != 'Approved' THEN
        INSERT INTO CNIC_Card (
            citizen_id, 
            card_number, 
            issue_date, 
            expiry_date
        ) VALUES (
            NEW.citizen_id,
            CONCAT('CNIC-', NEW.application_id, '-', DATE_FORMAT(NOW(), '%Y')),
            CURDATE(),
            DATE_ADD(CURDATE(), INTERVAL 10 YEAR)
        );
    END IF;
END//

DELIMITER ;


DELIMITER //

CREATE TRIGGER block_watchlist_documents
BEFORE INSERT ON Passport
FOR EACH ROW
BEGIN
    DECLARE watchlist_count INT;
    
    -- Check if citizen is on watchlist
    SELECT COUNT(*) INTO watchlist_count
    FROM Watchlist WHERE citizen_id = NEW.citizen_id;
    
    -- Block if on watchlist
    IF watchlist_count > 0 THEN
        SIGNAL SQLSTATE '45000' 
        SET MESSAGE_TEXT = 'Cannot issue passport to watchlisted citizen';
    END IF;
END//

DELIMITER ;




DELIMITER //

CREATE TRIGGER auto_expire_driving_license
BEFORE UPDATE ON Driving_License
FOR EACH ROW
BEGIN
    -- Auto-expire if expiry date has passed
    IF NEW.expiry_date < CURDATE() AND NEW.status = 'Valid' THEN
        SET NEW.status = 'Expired';
    END IF;
END//

DELIMITER ;




DELIMITER //

CREATE TRIGGER validate_marriage_requirements
BEFORE INSERT ON Marriage_Registration
FOR EACH ROW
BEGIN
    DECLARE husband_age INT;
    DECLARE wife_age INT;
    DECLARE husband_gender VARCHAR(10);
    DECLARE wife_gender VARCHAR(10);
    
    
    SELECT TIMESTAMPDIFF(YEAR, dob, CURDATE()), gender 
    INTO husband_age, husband_gender
    FROM Citizen WHERE citizen_id = NEW.husband_id;
    
    
    SELECT TIMESTAMPDIFF(YEAR, dob, CURDATE()), gender 
    INTO wife_age, wife_gender
    FROM Citizen WHERE citizen_id = NEW.wife_id;
    
    
    IF husband_gender != 'Male' THEN
        SIGNAL SQLSTATE '45000' 
        SET MESSAGE_TEXT = 'Husband must be Male';
    END IF;
    
    IF wife_gender != 'Female' THEN
        SIGNAL SQLSTATE '45000' 
        SET MESSAGE_TEXT = 'Wife must be Female';
    END IF;
    
    
    IF husband_age < 18 THEN
        SIGNAL SQLSTATE '45000' 
        SET MESSAGE_TEXT = 'Husband must be at least 18 years old';
    END IF;
    
    IF wife_age < 18 THEN
        SIGNAL SQLSTATE '45000' 
        SET MESSAGE_TEXT = 'Wife must be at least 18 years old';
    END IF;
END//

DELIMITER ;

DELIMITER //

CREATE TRIGGER validate_cnic_applicant_age
BEFORE INSERT ON CNIC_Application
FOR EACH ROW
BEGIN
    DECLARE applicant_age INT;
    
    -- Calculate age from date of birth
    SELECT TIMESTAMPDIFF(YEAR, dob, CURDATE()) INTO applicant_age
    FROM Citizen WHERE citizen_id = NEW.citizen_id;
    
    -- Check if under 18
    IF applicant_age < 18 THEN
        SIGNAL SQLSTATE '45000' 
        SET MESSAGE_TEXT = 'CNIC applicant must be 18 years or older';
    END IF;
END//

-- Also add for updates (in case someone changes citizen_id)
CREATE TRIGGER validate_cnic_applicant_age_update
BEFORE UPDATE ON CNIC_Application
FOR EACH ROW
BEGIN
    DECLARE applicant_age INT;
    
    -- Only validate if citizen_id is being changed
    IF NEW.citizen_id != OLD.citizen_id THEN
        SELECT TIMESTAMPDIFF(YEAR, dob, CURDATE()) INTO applicant_age
        FROM Citizen WHERE citizen_id = NEW.citizen_id;
        
        IF applicant_age < 18 THEN
            SIGNAL SQLSTATE '45000' 
            SET MESSAGE_TEXT = 'CNIC applicant must be 18 years or older';
        END IF;
    END IF;
END//

DELIMITER ;





DELIMITER //

CREATE TRIGGER validate_driving_license_age
BEFORE INSERT ON Driving_License_Application
FOR EACH ROW
BEGIN
    DECLARE applicant_age INT;
    
    -- Calculate age from date of birth in Citizen table
    SELECT TIMESTAMPDIFF(YEAR, dob, CURDATE()) INTO applicant_age
    FROM Citizen 
    WHERE citizen_id = NEW.citizen_id;
    
    -- Age validation based on license type
    IF NEW.license_type = 'Motorcycle' AND applicant_age < 18 THEN
        SIGNAL SQLSTATE '45000' 
        SET MESSAGE_TEXT = 'Motorcycle license requires minimum age 18';
        
    ELSEIF NEW.license_type = 'Car' AND applicant_age < 18 THEN
        SIGNAL SQLSTATE '45000' 
        SET MESSAGE_TEXT = 'Car license requires minimum age 18';
        
    ELSEIF NEW.license_type = 'Commercial' AND applicant_age < 21 THEN
        SIGNAL SQLSTATE '45000' 
        SET MESSAGE_TEXT = 'Commercial license requires minimum age 21';
        
    ELSEIF NEW.license_type = 'Heavy Vehicle' AND applicant_age < 21 THEN
        SIGNAL SQLSTATE '45000' 
        SET MESSAGE_TEXT = 'Heavy Vehicle license requires minimum age 21';
    END IF;
END//

DELIMITER ;



CREATE VIEW CitizenProfile_View AS
SELECT 
    c.citizen_id,
    c.national_id_number,
    CONCAT(c.first_name, ' ', c.last_name) AS full_name,
    c.dob,
    TIMESTAMPDIFF(YEAR, c.dob, CURDATE()) AS age,
    c.gender,
    c.marital_status,
    c.blood_group,
    c.status,
    -- Current address
    a.house_no,
    a.street,
    a.city,
    a.province,
    a.postal_code,
    -- Document status
    CASE WHEN cn.card_id IS NOT NULL AND cn.card_status = 'Active' THEN 'Yes' ELSE 'No' END AS has_active_cnic,
    CASE WHEN p.passport_id IS NOT NULL AND p.passport_status = 'Valid' THEN 'Yes' ELSE 'No' END AS has_valid_passport,
    CASE WHEN dl.license_id IS NOT NULL AND dl.status = 'Valid' THEN 'Yes' ELSE 'No' END AS has_valid_license,
    -- Security status
    CASE WHEN w.watchlist_id IS NOT NULL THEN 'ON WATCHLIST' ELSE 'Clear' END AS security_status
FROM Citizen c
LEFT JOIN (
    SELECT cah.citizen_id, a.house_no, a.street, a.city, a.province, a.postal_code
    FROM Citizen_Address_History cah
    JOIN Address a ON cah.address_id = a.address_id
    WHERE cah.end_date IS NULL  -- Current address only
) a ON c.citizen_id = a.citizen_id
LEFT JOIN CNIC_Card cn ON c.citizen_id = cn.citizen_id AND cn.card_status = 'Active'
LEFT JOIN Passport p ON c.citizen_id = p.citizen_id AND p.passport_status = 'Valid'
LEFT JOIN Driving_License dl ON c.citizen_id = dl.citizen_id AND dl.status = 'Valid'
LEFT JOIN Watchlist w ON c.citizen_id = w.citizen_id;



CREATE VIEW ApplicationStatus_View AS
SELECT 
    'CNIC' AS service_type,
    application_id AS application_id,
    citizen_id,
    application_type,
    submission_date,
    status,
    DATEDIFF(CURDATE(), DATE(submission_date)) AS days_pending,
    NULL AS test_status,
    office_id
FROM CNIC_Application

UNION ALL

SELECT 
    'Passport',
    passport_app_id,
    citizen_id,
    application_type,
    submission_date,
    status,
    DATEDIFF(CURDATE(), DATE(submission_date)),
    NULL,
    office_id
FROM Passport_Application

UNION ALL

SELECT 
    'Driving License',
    dl_app_id,
    citizen_id,
    license_type,
    submission_date,
    status,
    DATEDIFF(CURDATE(), DATE(submission_date)),
    test_result,
    office_id
FROM Driving_License_Application

ORDER BY days_pending DESC;


CREATE VIEW OfficePerformance_View AS
SELECT 
    o.office_id,
    o.office_name,
    o.office_type,
    o.city,
    o.province,
    -- Appointment stats
    COUNT(DISTINCT a.appointment_id) AS total_appointments,
    COUNT(DISTINCT CASE WHEN a.status = 'Scheduled' THEN a.appointment_id END) AS upcoming_appointments,
    COUNT(DISTINCT CASE WHEN a.status = 'Completed' THEN a.appointment_id END) AS completed_appointments,
    -- Application stats
    COUNT(DISTINCT cnic.application_id) AS cnic_applications,
    COUNT(DISTINCT pa.passport_app_id) AS passport_applications,
    COUNT(DISTINCT dla.dl_app_id) AS driving_license_applications,
    -- Pending applications
    COUNT(DISTINCT CASE WHEN cnic.status IN ('Pending', 'Under Review') THEN cnic.application_id END) AS pending_cnic,
    COUNT(DISTINCT CASE WHEN pa.status IN ('Submitted', 'Under Review') THEN pa.passport_app_id END) AS pending_passport,
    COUNT(DISTINCT CASE WHEN dla.status IN ('Pending', 'Test Scheduled') THEN dla.dl_app_id END) AS pending_dl,
    -- Officer count
    COUNT(DISTINCT ofc.officer_id) AS total_officers
FROM Office o
LEFT JOIN Appointment a ON o.office_id = a.office_id
LEFT JOIN CNIC_Application cnic ON o.office_id = cnic.office_id
LEFT JOIN Passport_Application pa ON o.office_id = pa.office_id
LEFT JOIN Driving_License_Application dla ON o.office_id = dla.office_id
LEFT JOIN Officer ofc ON o.office_id = ofc.office_id
GROUP BY o.office_id, o.office_name, o.office_type, o.city, o.province;


