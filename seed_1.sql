USE crid;

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

-- ROLES
INSERT INTO Role (role_name,description,access_level) VALUES
('Admin','CRIDA System Administrator',5),
('Registrar','Civil Registrar Officer',4),
('Passport_Officer','Passport Processing',3),
('License_Officer','Driving License Officer',3),
('Security_Officer','Security Monitoring Officer',4);

-- OFFICES
INSERT INTO Office (office_name,office_type,city,province,contact_number,address) VALUES
('CRIDA Head Office','Head Office','Islamabad','Islamabad','05111111111','Blue Area'),
('CRIDA Lahore Regional','Regional','Lahore','Punjab','04222222222','Mall Road'),
('CRIDA Karachi Regional','Regional','Karachi','Sindh','02133333333','Shahrah-e-Faisal'),
('CRIDA Peshawar City','City','Peshawar','KPK','09144444444','University Road'),
('CRIDA Quetta Tehsil','Tehsil','Quetta','Balochistan','08155555555','Jinnah Road');

-- OFFICERS
INSERT INTO Officer (full_name,email,password_hash,role_id,office_id,employee_id) VALUES
('Ali Khan','admin@crida.pk','h1',1,1,'EMP-001'),
('Sara Ahmed','registrar1@crida.pk','h2',2,2,'EMP-002'),
('Bilal Qureshi','registrar2@crida.pk','h3',2,3,'EMP-003'),
('Usman Raza','passport1@crida.pk','h4',3,3,'EMP-004'),
('Hina Malik','license1@crida.pk','h5',4,2,'EMP-005'),
('Faisal Noor','security@crida.pk','h6',5,1,'EMP-006'),
('Adeel Shah','passport2@crida.pk','h7',3,1,'EMP-007'),
('Mariam Tariq','license2@crida.pk','h8',4,4,'EMP-008');

-- HOSPITALS
INSERT INTO Hospital (name,city,province,contact_number) VALUES
('Jinnah Hospital','Lahore','Punjab','04298765432'),
('Civil Hospital','Karachi','Sindh','02198765432'),
('PIMS','Islamabad','Islamabad','05198765432');

-- ADDRESSES
INSERT INTO Address (house_no,street,city,province,postal_code) VALUES
('10-A','Model Town','Lahore','Punjab','54000'),
('22-B','Gulberg','Lahore','Punjab','54010'),
('33-C','Clifton','Karachi','Sindh','75000'),
('44-D','F-7','Islamabad','Islamabad','44000'),
('55-E','Hayatabad','Peshawar','KPK','25000'),
('66-F','Satellite Town','Quetta','Balochistan','87300');

-- CITIZENS (ALL AGE VALID)
INSERT INTO Citizen (national_id_number,first_name,last_name,dob,gender,marital_status,blood_group) VALUES
('3520212345601','Ahmed','Raza','1985-05-10','Male','Married','A+'),
('3520212345602','Fatima','Ahmed','1988-08-12','Female','Married','B+'),
('3520212345603','Hamza','Khan','1990-02-20','Male','Single','O+'),
('3520212345604','Ayesha','Malik','1993-12-01','Female','Single','AB+'),
('3520212345605','Imran','Shah','1975-03-12','Male','Married','O-'),
('3520212345606','Zara','Ali','1996-07-15','Female','Single','A-'),
('3520212345607','Tariq','Mehmood','1982-01-18','Male','Married','B-'),
('3520212345608','Sana','Tariq','1984-04-22','Female','Married','O+'),
('3520212345609','Usman','Butt','1991-09-09','Male','Single','AB-'),
('3520212345610','Hira','Rashid','1994-11-11','Female','Single','A+'),
('3520212345611','Noman','Iqbal','1978-03-30','Male','Married','B+'),
('3520212345612','Rabia','Noman','1980-06-25','Female','Married','O+');

-- ADDRESS HISTORY (CURRENT)
INSERT INTO Citizen_Address_History VALUES
(NULL,1,1,'2015-01-01',NULL),
(NULL,2,1,'2015-01-01',NULL),
(NULL,3,3,'2018-01-01',NULL),
(NULL,4,4,'2019-01-01',NULL),
(NULL,5,2,'2010-01-01',NULL),
(NULL,6,4,'2020-01-01',NULL),
(NULL,7,5,'2016-01-01',NULL),
(NULL,8,5,'2016-01-01',NULL),
(NULL,9,3,'2019-01-01',NULL),
(NULL,10,6,'2021-01-01',NULL),
(NULL,11,2,'2012-01-01',NULL),
(NULL,12,2,'2012-01-01',NULL);

-- MARRIAGES
INSERT INTO Marriage_Registration (husband_id,wife_id,marriage_date,registrar_officer_id,marriage_certificate_number) VALUES
(1,2,'2010-06-15',2,'MARR-1001'),
(7,8,'2012-09-10',3,'MARR-1002'),
(11,12,'2005-04-20',2,'MARR-1003');

-- CNIC APPLICATIONS (mixed status)
INSERT INTO CNIC_Application (citizen_id,application_type,status,office_id) VALUES
(1,'New','Approved',1),
(2,'New','Approved',2),
(3,'New','Under Review',1),
(4,'New','Pending',3),
(5,'Renewal','Approved',1),
(6,'New','Approved',4),
(7,'New','Approved',2),
(8,'New','Approved',2),
(9,'New','Rejected',3),
(10,'New','Approved',5),
(11,'Renewal','Approved',1),
(12,'New','Approved',1);

-- PASSPORT APPLICATIONS
INSERT INTO Passport_Application (citizen_id,application_type,status,office_id,fee_paid) VALUES
(1,'New','Approved',3,TRUE),
(3,'New','Under Review',3,TRUE),
(5,'Renewal','Approved',1,TRUE),
(7,'New','Approved',2,TRUE),
(9,'New','Rejected',3,FALSE);

-- PASSPORTS (expiry = issue + 10 years)
INSERT INTO Passport VALUES
(NULL,1,'PK10001','2023-01-01','2033-01-01','Valid'),
(NULL,5,'PK10002','2022-05-01','2032-05-01','Valid'),
(NULL,7,'PK10003','2023-06-01','2033-06-01','Valid');

-- DRIVING LICENSE APPLICATIONS
INSERT INTO Driving_License_Application 
(citizen_id,license_type,status,test_result,test_date,office_id) VALUES
(1,'Car','Test Passed','Pass','2023-05-01',2),
(3,'Motorcycle','Test Failed','Fail','2023-06-01',2),
(5,'Commercial','Test Passed','Pass','2023-07-01',1),
(7,'Car','Approved',NULL,NULL,2),
(9,'Motorcycle','Pending',NULL,NULL,3);

-- DRIVING LICENSES
INSERT INTO Driving_License VALUES
(NULL,1,'DL1001','2023-06-01','2033-06-01','Car','Valid'),
(NULL,5,'DL1002','2023-07-01','2033-07-01','Commercial','Valid');

-- BIOMETRIC
INSERT INTO Biometric_Data (citizen_id,fingerprint_hash,facial_scan_hash) VALUES
(1,'fp1','face1'),
(2,'fp2','face2'),
(3,'fp3','face3'),
(4,'fp4','face4'),
(5,'fp5','face5'),
(6,'fp6','face6');

-- CRIMINAL RECORDS
INSERT INTO Criminal_Record 
(citizen_id,case_number,offense,offense_date,status,court_name) VALUES
(5,'CR-001','Fraud Case','2022-01-01','On Trial','Lahore High Court'),
(9,'CR-002','Cyber Crime','2023-03-15','Charged','Karachi Court');

-- WATCHLIST (NO PASSPORT INSERTED FOR THESE)
INSERT INTO Watchlist (citizen_id,reason,added_by,watchlist_type,expiry_date) VALUES
(9,'Cyber Investigation',6,'Security','2027-01-01'),
(5,'Financial Monitoring',6,'Fraud','2026-05-01');

-- APPOINTMENTS (future safe)
INSERT INTO Appointment 
(citizen_id,office_id,service_type,appointment_date,status,officer_id) VALUES
(4,2,'CNIC',DATE_ADD(NOW(),INTERVAL 3 DAY),'Scheduled',2),
(6,3,'Passport',DATE_ADD(NOW(),INTERVAL 5 DAY),'Scheduled',4),
(10,5,'Driving License',DATE_ADD(NOW(),INTERVAL 10 DAY),'Scheduled',8);

-- DOCUMENTS
INSERT INTO Document (citizen_id,document_type,file_path,verification_status,verified_by) VALUES
(1,'photo','/docs/1_photo.jpg','approved',1),
(1,'signature','/docs/1_sign.jpg','approved',1),
(3,'supporting_doc','/docs/3_doc.pdf','pending',NULL),
(5,'photo','/docs/5_photo.jpg','approved',1);

-- PAYMENTS
INSERT INTO Payment_Transaction
(citizen_id,service_type,cnic_app_id,passport_app_id,dl_app_id,amount,payment_method,payment_status,transaction_reference)
VALUES
(1,'CNIC',1,NULL,NULL,2500,'Online','Completed','TX-1001'),
(1,'Passport',NULL,1,NULL,5000,'Credit Card','Completed','TX-1002'),
(5,'Driving License',NULL,NULL,3,8000,'Cash','Completed','TX-1003'),
(3,'CNIC',3,NULL,NULL,2500,'Debit Card','Pending','TX-1004');

-- AUDIT LOGS
INSERT INTO Audit_Log (officer_id,action_type,table_name,record_id,new_values,ip_address) VALUES
(1,'INSERT','Citizen',1,'New citizen added','192.168.1.1'),
(2,'UPDATE','CNIC_Application',1,'Status Approved','192.168.1.2'),
(6,'VIEW','Watchlist',NULL,'Viewed Watchlist','192.168.1.3');

-- DEATH REGISTRATION (trigger will mark citizen 11 deceased)
INSERT INTO Death_Registration
(citizen_id,cause_of_death,date_of_death,place_of_death,registrar_officer_id,death_certificate_number)
VALUES
(11,'Cardiac Arrest','2024-01-01','Lahore',2,'DEATH-1001');

SELECT * FROM Citizen;

SELECT * FROM Passport;

DELETE  FROM Passport
WHERE passport_id = 1;
SELECT * FROM Address;

SELECT * FROM CitizenProfile_View WHERE citizen_id = 1;
SELECT * FROM CitizenProfile_View WHERE citizen_id = 5;

SELECT * FROM Family_Relationship
where citizen_id = 8;
SELECT * FROM Family_Relationship;
