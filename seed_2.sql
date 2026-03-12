USE CRID;

SET FOREIGN_KEY_CHECKS = 0;

TRUNCATE TABLE Payment_Transaction;
TRUNCATE TABLE Audit_Log;
TRUNCATE TABLE Document;
TRUNCATE TABLE Appointment;
TRUNCATE TABLE Watchlist;
TRUNCATE TABLE Criminal_Record;
TRUNCATE TABLE Biometric_Data;
TRUNCATE TABLE Driving_License;
TRUNCATE TABLE Driving_License_Application;
TRUNCATE TABLE Passport;
TRUNCATE TABLE Passport_Application;
TRUNCATE TABLE CNIC_Card;
TRUNCATE TABLE CNIC_Application;
TRUNCATE TABLE Marriage_Registration;
TRUNCATE TABLE Death_Registration;
TRUNCATE TABLE Birth_Registration;
TRUNCATE TABLE Officer;
TRUNCATE TABLE Role;
TRUNCATE TABLE Family_Relationship;
TRUNCATE TABLE Citizen_Address_History;
TRUNCATE TABLE Hospital;
TRUNCATE TABLE Office;
TRUNCATE TABLE Address;
TRUNCATE TABLE Citizen;

SET FOREIGN_KEY_CHECKS = 1;

-- =========================
-- STATIC TABLES
-- =========================

INSERT INTO Role (role_name,description,access_level) VALUES
('Admin','System Admin',5),
('Registrar','Registrar',4),
('Passport_Officer','Passport Officer',3),
('License_Officer','License Officer',3),
('Security_Officer','Security Officer',4);

INSERT INTO Office (office_name,office_type,city,province,contact_number,address) VALUES
('CRIDA Head Office','Head Office','Islamabad','Islamabad','05111111111','Blue Area'),
('CRIDA Lahore','Regional','Lahore','Punjab','04222222222','Mall Road'),
('CRIDA Karachi','Regional','Karachi','Sindh','02133333333','Shahrah-e-Faisal'),
('CRIDA Peshawar','City','Peshawar','KPK','09144444444','University Road'),
('CRIDA Quetta','Tehsil','Quetta','Balochistan','08155555555','Jinnah Road');

INSERT INTO Hospital (name,city,province,contact_number) VALUES
('Jinnah Hospital','Lahore','Punjab','04298765432'),
('Civil Hospital','Karachi','Sindh','02198765432'),
('PIMS','Islamabad','Islamabad','05198765432');

-- =========================
-- SEQUENCE TABLE (1–100)
-- =========================

CREATE TEMPORARY TABLE seq (n INT PRIMARY KEY);

INSERT INTO seq (n)
SELECT a.N + b.N*10 + 1
FROM 
(SELECT 0 N UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 
 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) a,
(SELECT 0 N UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 
 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) b
WHERE a.N + b.N*10 < 100;

-- =========================
-- OFFICERS
-- =========================

INSERT INTO Officer (full_name,email,password_hash,role_id,office_id,employee_id)
SELECT 
CONCAT('Officer ',n),
CONCAT('officer',n,'@crida.pk'),
'hash',
(n % 5)+1,
(n % 5)+1,
CONCAT('EMP-',LPAD(n,4,'0'))
FROM seq;

-- =========================
-- CITIZENS
-- =========================

INSERT INTO Citizen
(national_id_number,first_name,last_name,dob,gender,marital_status,blood_group)
SELECT
LPAD(3000000000000+n,13,'0'),
CONCAT('First',n),
CONCAT('Last',n),
DATE_SUB(CURDATE(), INTERVAL (20 + (n % 40)) YEAR),
IF(n%2=0,'Male','Female'),
IF(n%3=0,'Married','Single'),
'A+'
FROM seq;

-- =========================
-- ADDRESSES
-- =========================

INSERT INTO Address (house_no,street,city,province,postal_code)
SELECT 
CONCAT(n,'-A'),
CONCAT('Street ',n),
'Lahore',
'Punjab',
'54000'
FROM seq;

INSERT INTO Citizen_Address_History (citizen_id,address_id,start_date,end_date)
SELECT citizen_id,citizen_id,'2015-01-01',NULL
FROM Citizen;

-- =========================
-- FAMILY RELATIONSHIPS (PAIRS)
-- =========================

INSERT INTO Family_Relationship (citizen_id,related_citizen_id,relationship_type)
SELECT c1.citizen_id,c2.citizen_id,'Brother'
FROM Citizen c1
JOIN Citizen c2 ON c2.citizen_id = c1.citizen_id + 1
WHERE c1.citizen_id % 10 = 1;

-- =========================
-- BIRTH REGISTRATIONS
-- =========================

INSERT INTO Birth_Registration
(citizen_id,hospital_id,registrar_officer_id,birth_certificate_number)
SELECT citizen_id,
(citizen_id % 3)+1,
1,
CONCAT('BIRTH-',citizen_id)
FROM Citizen
WHERE citizen_id <= 50;

-- =========================
-- MARRIAGES (VALID AGE/GENDER)
-- =========================

INSERT INTO Marriage_Registration
(husband_id,wife_id,marriage_date,registrar_officer_id,marriage_certificate_number)
SELECT c1.citizen_id,
       c2.citizen_id,
       '2015-01-01',
       1,
       CONCAT('MARR-',c1.citizen_id)
FROM Citizen c1
JOIN Citizen c2 ON c2.citizen_id = c1.citizen_id + 1
WHERE c1.gender='Male'
AND c2.gender='Female'
AND c1.citizen_id <= 50;

-- =========================
-- CNIC APPLICATIONS
-- =========================

INSERT INTO CNIC_Application
(citizen_id,application_type,status,office_id)
SELECT citizen_id,'New','Approved',(citizen_id % 5)+1
FROM Citizen;

-- =========================
-- PASSPORT APPLICATIONS
-- =========================

INSERT INTO Passport_Application
(citizen_id,application_type,status,office_id,fee_paid)
SELECT citizen_id,'New','Approved',(citizen_id % 5)+1,TRUE
FROM Citizen;

INSERT INTO Passport
(citizen_id,passport_number,issue_date,expiry_date)
SELECT citizen_id,
CONCAT('PK',LPAD(citizen_id,6,'0')),
CURDATE(),
DATE_ADD(CURDATE(), INTERVAL 10 YEAR)
FROM Citizen
WHERE citizen_id <= 70;

-- =========================
-- DRIVING LICENSE APPLICATIONS
-- =========================

INSERT INTO Driving_License_Application
(citizen_id,license_type,status,test_result,test_date,office_id)
SELECT citizen_id,
'Car',
'Test Passed',
'Pass',
CURDATE(),
(citizen_id % 5)+1
FROM Citizen;

INSERT INTO Driving_License
(citizen_id,license_number,issue_date,expiry_date,license_type,status)
SELECT citizen_id,
CONCAT('DL',LPAD(citizen_id,6,'0')),
CURDATE(),
DATE_ADD(CURDATE(), INTERVAL 10 YEAR),
'Car',
'Valid'
FROM Citizen
WHERE citizen_id <= 60;

-- =========================
-- BIOMETRIC
-- =========================

INSERT INTO Biometric_Data
(citizen_id,fingerprint_hash,facial_scan_hash)
SELECT citizen_id,
CONCAT('fp',citizen_id),
CONCAT('face',citizen_id)
FROM Citizen;

-- =========================
-- CRIMINAL RECORDS
-- =========================

INSERT INTO Criminal_Record
(citizen_id,case_number,offense,offense_date,status,court_name)
SELECT citizen_id,
CONCAT('CR-',citizen_id),
'Fraud Case',
'2022-01-01',
'On Trial',
'Lahore High Court'
FROM Citizen
WHERE citizen_id <= 30;

-- =========================
-- WATCHLIST
-- =========================

INSERT INTO Watchlist
(citizen_id,reason,added_by,watchlist_type,expiry_date)
SELECT citizen_id,
'Security Monitoring',
1,
'Security',
DATE_ADD(CURDATE(), INTERVAL 3 YEAR)
FROM Citizen
WHERE citizen_id <= 20;

-- =========================
-- APPOINTMENTS
-- =========================

INSERT INTO Appointment
(citizen_id,office_id,service_type,appointment_date,status,officer_id)
SELECT citizen_id,
(citizen_id % 5)+1,
'CNIC',
DATE_ADD(NOW(), INTERVAL 7 DAY),
'Scheduled',
1
FROM Citizen;

-- =========================
-- DOCUMENTS
-- =========================

INSERT INTO Document
(citizen_id,document_type,file_path,verification_status,verified_by)
SELECT citizen_id,
'photo',
CONCAT('/docs/',citizen_id,'.jpg'),
'approved',
1
FROM Citizen;

-- =========================
-- PAYMENTS
-- =========================

INSERT INTO Payment_Transaction
(citizen_id,service_type,cnic_app_id,amount,payment_method,payment_status,transaction_reference)
SELECT citizen_id,
'CNIC',
citizen_id,
2500,
'Online',
'Completed',
CONCAT('TX-',citizen_id)
FROM Citizen;

-- =========================
-- AUDIT LOG
-- =========================

INSERT INTO Audit_Log
(officer_id,action_type,table_name,record_id,new_values,ip_address)
SELECT 1,
'INSERT',
'Citizen',
citizen_id,
'Bulk Insert',
'127.0.0.1'
FROM Citizen;

-- =========================
-- DEATH REGISTRATION
-- =========================

INSERT INTO Death_Registration
(citizen_id,cause_of_death,date_of_death,place_of_death,registrar_officer_id,death_certificate_number)
SELECT citizen_id,
'Natural Causes',
DATE_SUB(CURDATE(), INTERVAL 1 YEAR),
'Lahore',
1,
CONCAT('DEATH-',citizen_id)
FROM (SELECT citizen_id FROM Citizen WHERE citizen_id BETWEEN 95 AND 99) AS tmp;

DROP TEMPORARY TABLE seq;


SELECT * FROM Family_Relationship
where related_citizen_id = 12;

SELECT * FROM CitizenProfile_View;
SELECT * FROM CNIC_Application;


DESCRIBE audit_log;
ALTER TABLE Audit_Log 
CHANGE COLUMN timestamp action_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP;
