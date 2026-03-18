-- ============================================================
--  CRIDA — Rich Family Relationships Seed
--  Run: mysql -u crida_user -pcrida1234 CRID < family_seed.sql
-- ============================================================

SET FOREIGN_KEY_CHECKS = 0;

-- Clear existing family relationships to avoid duplicates
DELETE FROM Family_Relationship WHERE citizen_id BETWEEN 1 AND 100;

-- ============================================================
-- FAMILY A — Citizen 11 is the ROOT (Female, head of family)
-- Husband: 12 | Sons: 13,15,17 | Daughters: 14,16
-- Parents: 7 (Father), 8 (Mother)
-- Siblings: 9 (Brother), 10 (Sister)
-- Grandchildren via son 13: 23, 24
-- Grandchildren via son 15: 25, 26
-- ============================================================

INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
-- 11's children
(11, 13, 'Son'),
(11, 14, 'Daughter'),
(11, 15, 'Son'),
(11, 16, 'Daughter'),
(11, 17, 'Son'),
-- 11's parents
(11, 7,  'Father'),
(11, 8,  'Mother'),
-- 11's siblings
(11, 9,  'Brother'),
(11, 10, 'Sister'),
-- 12 (husband) also has children recorded
(12, 13, 'Son'),
(12, 14, 'Daughter'),
(12, 15, 'Son'),
(12, 16, 'Daughter'),
(12, 17, 'Son'),
-- 13's children (grandchildren of 11)
(13, 23, 'Son'),
(13, 24, 'Daughter'),
-- 15's children (grandchildren of 11)
(15, 25, 'Son'),
(15, 26, 'Daughter'),
-- 13 and 15 are siblings
(13, 15, 'Brother'),
(13, 16, 'Sister'),
(15, 13, 'Brother'),
-- 7 and 8 are parents of 11 and 9 and 10
(7,  11, 'Daughter'),
(7,  9,  'Son'),
(7,  10, 'Daughter'),
(8,  11, 'Daughter'),
(8,  9,  'Son'),
(8,  10, 'Daughter');

-- ============================================================
-- FAMILY B — Citizen 21 is the ROOT (Female)
-- Husband: 22 | Sons: 23,25 | Daughters: 24,26
-- Parents: 17 (Father), 18 (Mother)
-- Siblings: 19 (Brother), 20 (Sister)
-- Uncle/Aunt relations
-- ============================================================

INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(21, 23, 'Son'),
(21, 24, 'Daughter'),
(21, 25, 'Son'),
(21, 26, 'Daughter'),
(21, 17, 'Father'),
(21, 18, 'Mother'),
(21, 19, 'Brother'),
(21, 20, 'Sister'),
(22, 23, 'Son'),
(22, 24, 'Daughter'),
(22, 25, 'Son'),
(22, 26, 'Daughter'),
(17, 21, 'Daughter'),
(18, 21, 'Daughter'),
-- Uncle/Aunt
(19, 23, 'Nephew'),
(19, 24, 'Niece'),
(20, 23, 'Nephew'),
(20, 24, 'Niece');

-- ============================================================
-- FAMILY C — Citizen 31 is the ROOT (Female)
-- Husband: 32 | Children: 33,34,35
-- Grandchildren: 43,44
-- Great-grandchildren: 53,54
-- ============================================================

INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(31, 33, 'Son'),
(31, 34, 'Daughter'),
(31, 35, 'Son'),
(32, 33, 'Son'),
(32, 34, 'Daughter'),
(32, 35, 'Son'),
(33, 43, 'Son'),
(33, 44, 'Daughter'),
(34, 45, 'Son'),
(43, 53, 'Son'),
(43, 54, 'Daughter'),
-- Reverse (parent pointers)
(33, 31, 'Mother'),
(33, 32, 'Father'),
(43, 33, 'Father'),
(53, 43, 'Father');

-- ============================================================
-- FAMILY D — Extended family with cousins
-- Citizen 41 and 51 are cousins
-- ============================================================

INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(41, 42, 'Brother'),
(41, 43, 'Sister'),
(41, 51, 'Cousin'),
(42, 41, 'Brother'),
(42, 51, 'Cousin'),
(51, 41, 'Cousin'),
(51, 52, 'Brother'),
(51, 53, 'Sister'),
-- in-laws
(41, 62, 'Brother-in-law'),
(41, 63, 'Sister-in-law');

-- ============================================================
-- FAMILY E — Citizen 61, large family
-- ============================================================

INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(61, 62, 'Son'),
(61, 63, 'Daughter'),
(61, 64, 'Son'),
(61, 65, 'Daughter'),
(61, 66, 'Son'),
(61, 57, 'Father'),
(61, 58, 'Mother'),
(61, 59, 'Brother'),
(61, 60, 'Sister'),
(62, 71, 'Son'),
(62, 72, 'Daughter'),
(63, 73, 'Son'),
(64, 74, 'Son'),
(64, 75, 'Daughter');

SET FOREIGN_KEY_CHECKS = 1;

SELECT 'Family seed inserted successfully!' AS Status;

-- Quick verification
SELECT 
    relationship_type,
    COUNT(*) AS count
FROM Family_Relationship
GROUP BY relationship_type
ORDER BY count DESC;