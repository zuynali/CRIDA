-- Before Indexing
DROP INDEX  idx_citizen_national_id ON Citizen;

EXPLAIN ANALYZE
SELECT citizen_id, first_name, last_name, dob, status
FROM Citizen
WHERE national_id_number = '3000000000099';

-- Analysis
-- Rows fetched before execution  (cost=0..0 rows=1) (actual time=0.0022..0.0024 rows=1 loops=1)

 
 
 
 
-- AFTER INDEX (Index Seek)
CREATE INDEX idx_citizen_national_id ON Citizen(national_id_number);

EXPLAIN ANALYZE
SELECT citizen_id, first_name, last_name, dob, status
FROM Citizen
WHERE national_id_number = '3000000000099';
-- Analysis
-- Rows fetched before execution  (cost=0..0 rows=1) (actual time=600e-6..800e-6 rows=1 loops=1)
 



-- QUERY 2: Pending CNIC Applications for a Citizen


-- BEFORE INDEX (Full Table Scan)
DROP INDEX  idx_cnic_app_citizen ON CNIC_Application;
DROP INDEX  idx_cnic_app_status ON CNIC_Application;

EXPLAIN ANALYZE
SELECT application_id, application_type, submission_date, status
FROM CNIC_Application
WHERE citizen_id = 5 AND status IN ('Pending', 'Under Review');

-- Conclusion
--  Filter: (cnic_application.`status` in ('Pending','Under Review'))  (cost=0.3 rows=0.5) (actual time=0.0958..0.0958 rows=0 loops=1)
-- Index lookup on CNIC_Application using citizen_id (citizen_id = 5)  (cost=0.3 rows=1) (actual time=0.0814..0.0852...


-- AFTER INDEX (Index Seek + Filter)
CREATE INDEX idx_cnic_app_citizen ON CNIC_Application(citizen_id);
CREATE INDEX idx_cnic_app_status ON CNIC_Application(status);

EXPLAIN ANALYZE
SELECT application_id, application_type, submission_date, status
FROM CNIC_Application
WHERE citizen_id = 5 AND status IN ('Pending', 'Under Review');

-- Conclusion
-- Filter: (cnic_application.`status` in ('Pending','Under Review'))  (cost=0.255 rows=0.05) (actual time=0.0852..0.0852 rows=0 loops=1)
-- Index lookup on CNIC_Application using citizen_id (citizen_id = 5)  (cost=0.255 rows=1) (actual time=0.0733..0...




-- =====================================================
-- QUERY 3: Watchlist Check Before Document Issuance
-- =====================================================

-- BEFORE INDEX (Full Table Scan)
DROP INDEX  idx_watchlist_citizen ON Watchlist;

EXPLAIN ANALYZE
SELECT w.watchlist_id, w.reason, w.watchlist_type
FROM Watchlist w
WHERE w.citizen_id = 3 AND (w.expiry_date IS NULL OR w.expiry_date > CURDATE());
-- Conclusion
-- Rows fetched before execution  (cost=0..0 rows=1) (actual time=0.0011..0.0012 rows=1 loops=1)
 
-- AFTER INDEX (Index Seek)
CREATE INDEX idx_watchlist_citizen ON Watchlist(citizen_id);

EXPLAIN ANALYZE
SELECT w.watchlist_id, w.reason, w.watchlist_type
FROM Watchlist w
WHERE w.citizen_id = 3 AND (w.expiry_date IS NULL OR w.expiry_date > CURDATE());


-- Conclusion:
-- Rows fetched before execution  (cost=0..0 rows=1) (actual time=0.0013..0.0014 rows=1 loops=1)
 


    
