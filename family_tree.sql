-- ============================================================
--  family.sql
--  CRIDA — Family Relationship Seed Data
--
--  Run order:
--    1. seed_2.sql              (citizens + marriages created)
--    2. relationship_checks.sql (triggers installed)
--    3. THIS FILE               (triggers fire on each insert)
--
--  mysql -u crida_user -pcrida_pass CRID < family.sql
-- ============================================================
--
--  SEMANTIC RULE (UI / User Mental Model):
--    (citizen_id, related_citizen_id, relationship_type)
--    "For citizen_id, their relationship_type is related_citizen_id"
--    i.e. related_citizen_id IS the relationship_type.
--
--    (1, 2, 'Father')  → 2 is the Father of 1.
--    (2, 1, 'Son')     → 1 is the Son of 2.
--    (1, 3, 'Husband') → 3 is the Husband of 1.
--    (3, 1, 'Wife')    → 1 is the Wife of 3.
--
--  CITIZEN FACTS (from seed_2.sql formula):
--    Age    = 20 + (citizen_id % 40)
--    Gender : even citizen_id = Male, odd = Female
--    Citizens 95-99 are DECEASED — not used here.
--
--  ID  | Gender | Age     ID  | Gender | Age
--  ----+--------+----     ----+--------+----
--   36 | Male   |  56      37 | Female |  57
--   14 | Male   |  34      13 | Female |  33
--   16 | Male   |  36      15 | Female |  35
--   12 | Male   |  32      17 | Female |  37
--    2 | Male   |  22       1 | Female |  21
--   40 | Male   |  20
--   78 | Male   |  58      79 | Female |  59
--   50 | Male   |  30      51 | Female |  31
--   52 | Male   |  32      53 | Female |  33
--                          49 | Female |  29
--   70 | Male   |  50      71 | Female |  51
--   42 | Male   |  22      43 | Female |  23
--   74 | Male   |  54      75 | Female |  55
--   60 | Male   |  40      61 | Female |  41
--    6 | Male   |  26       5 | Female |  25
--    4 | Male   |  24       7 | Female |  27
--   66 | Male   |  46      67 | Female |  47
--   68 | Male   |  48      69 | Female |  49
--   10 | Male   |  30       9 | Female |  29
--    8 | Male   |  28      11 | Female |  31
-- ============================================================

USE CRID;

-- Clear existing rows first (FK checks off only for DELETE)
SET FOREIGN_KEY_CHECKS = 0;
DELETE FROM Family_Relationship;
SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
--  FAMILY 1 — Khan/Raza Clan (3 Generations)
--
--  Gen 1 (Grandparents):
--    36 (M, age 56)  married  37 (F, age 57)
--
--  Gen 2 (Children of 36 & 37):
--    16 (M, age 36): 56-36=20 ✓
--    14 (M, age 34): 56-34=22 ✓
--    13 (F, age 33): 56-33=23 ✓
--
--  Gen 2 spouses:
--    16 (M) ↔ 17 (F, age 37)
--    14 (M) ↔ 15 (F, age 35)
--    12 (M) ↔ 13 (F)
--
--  Gen 3 (Children of 16 & 17):
--     2 (M, age 22): 36-22=14 ✓
--     1 (F, age 21): 36-21=15 ✓
--
--  Gen 3 (Child of 14 & 15):
--    40 (M, age 20): 34-20=14 ✓
-- ============================================================

-- ── Gen 1 spouses ──────────────────────────────────────────
UPDATE Citizen SET marital_status = 'Married' WHERE citizen_id IN (36, 37);
INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(37, 36, 'Husband'),   -- For 37, 36 is the Husband
(36, 37, 'Wife');      -- For 36, 37 is the Wife

-- ── Gen 1 → Gen 2: 36 as Father ────────────────────────────
INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(16, 36, 'Father'),    -- For 16, 36 is the Father
(14, 36, 'Father'),    -- For 14, 36 is the Father
(13, 36, 'Father');    -- For 13, 36 is the Father

-- ── Gen 2 children of 36: reciprocal Son/Daughter ──────────
INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(36, 16, 'Son'),       -- For 36, 16 is the Son
(36, 14, 'Son'),       -- For 36, 14 is the Son
(36, 13, 'Daughter');  -- For 36, 13 is the Daughter

-- ── Gen 1 → Gen 2: 37 as Mother ────────────────────────────
INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(16, 37, 'Mother'),    -- For 16, 37 is the Mother
(14, 37, 'Mother'),    -- For 14, 37 is the Mother
(13, 37, 'Mother');    -- For 13, 37 is the Mother

-- ── Gen 2 children of 37: reciprocal ───────────────────────
INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(37, 16, 'Son'),
(37, 14, 'Son'),
(37, 13, 'Daughter');

-- ── Gen 2 siblings: 16, 14, 13 ─────────────────────────────
INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(14, 16, 'Brother'),   -- For 14(M), 16(M) is the Brother
(16, 14, 'Brother'),   -- For 16(M), 14(M) is the Brother
(13, 16, 'Brother'),   -- For 13(F), 16(M) is the Brother
(16, 13, 'Sister'),    -- For 16(M), 13(F) is the Sister
(13, 14, 'Brother'),   -- For 13(F), 14(M) is the Brother
(14, 13, 'Sister');    -- For 14(M), 13(F) is the Sister

-- ── Gen 2 spouses ──────────────────────────────────────────
UPDATE Citizen SET marital_status = 'Married' WHERE citizen_id IN (16, 17, 14, 15, 12, 13);
INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(17, 16, 'Husband'),   -- For 17(F), 16(M) is the Husband
(16, 17, 'Wife'),      -- For 16(M), 17(F) is the Wife
(15, 14, 'Husband'),   -- For 15(F), 14(M) is the Husband
(14, 15, 'Wife'),      -- For 14(M), 15(F) is the Wife
(13, 12, 'Husband'),   -- For 13(F), 12(M) is the Husband
(12, 13, 'Wife');      -- For 12(M), 13(F) is the Wife

-- ── Gen 3: children of 16(M,36) + 17(F,37) ────────────────
INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(2,  16, 'Father'),    -- For 2, 16 is the Father
(1,  16, 'Father'),    -- For 1, 16 is the Father
(2,  17, 'Mother'),    -- For 2, 17 is the Mother
(1,  17, 'Mother'),    -- For 1, 17 is the Mother
(16, 2,  'Son'),       -- For 16, 2 is the Son
(16, 1,  'Daughter'),  -- For 16, 1 is the Daughter
(17, 2,  'Son'),       -- For 17, 2 is the Son
(17, 1,  'Daughter');  -- For 17, 1 is the Daughter

-- ── Gen 3 siblings: 2 + 1 ──────────────────────────────────
INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(1, 2, 'Brother'),     -- For 1(F), 2(M) is the Brother
(2, 1, 'Sister');      -- For 2(M), 1(F) is the Sister

-- ── Gen 3: child of 14(M,34) + 15(F,35) ───────────────────
INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(40, 14, 'Father'),    -- For 40, 14 is the Father
(40, 15, 'Mother'),    -- For 40, 15 is the Mother
(14, 40, 'Son'),       -- For 14, 40 is the Son
(15, 40, 'Son');       -- For 15, 40 is the Son


-- ============================================================
--  FAMILY 2 — Shah/Butt Lineage (2 Generations)
-- ============================================================

UPDATE Citizen SET marital_status = 'Married' WHERE citizen_id IN (78, 79);
INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(79, 78, 'Husband'),
(78, 79, 'Wife');

INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(50, 78, 'Father'),    -- For 50, 78 is the Father
(52, 78, 'Father'),    -- For 52, 78 is the Father
(49, 78, 'Father'),    -- For 49, 78 is the Father
(50, 79, 'Mother'),
(52, 79, 'Mother'),
(49, 79, 'Mother'),
(78, 50, 'Son'),
(78, 52, 'Son'),
(78, 49, 'Daughter'),
(79, 50, 'Son'),
(79, 52, 'Son'),
(79, 49, 'Daughter');

INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(52, 50, 'Brother'),   -- For 52, 50 is the Brother
(50, 52, 'Brother'),
(49, 50, 'Brother'),   -- For 49, 50 is the Brother
(50, 49, 'Sister'),
(49, 52, 'Brother'),   -- For 49, 52 is the Brother
(52, 49, 'Sister');

UPDATE Citizen SET marital_status = 'Married' WHERE citizen_id IN (50, 51, 52, 53);
INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(51, 50, 'Husband'),   -- For 51, 50 is the Husband
(50, 51, 'Wife'),
(53, 52, 'Husband'),   -- For 53, 52 is the Husband
(52, 53, 'Wife');


-- ============================================================
--  FAMILY 3 — Two Unrelated Couples, Kids Marry
-- ============================================================

UPDATE Citizen SET marital_status = 'Married' WHERE citizen_id IN (70, 71);
INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(71, 70, 'Husband'),
(70, 71, 'Wife'),
(42, 70, 'Father'),
(42, 71, 'Mother'),
(70, 42, 'Son'),
(71, 42, 'Son');

UPDATE Citizen SET marital_status = 'Married' WHERE citizen_id IN (74, 75);
INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(75, 74, 'Husband'),
(74, 75, 'Wife'),
(43, 74, 'Father'),
(43, 75, 'Mother'),
(74, 43, 'Daughter'),
(75, 43, 'Daughter');

UPDATE Citizen SET marital_status = 'Married' WHERE citizen_id IN (42, 43);
INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(43, 42, 'Husband'),   -- For 43(F), 42(M) is the Husband
(42, 43, 'Wife');


-- ============================================================
--  FAMILY 4 — Young Parents (2 Generations)
-- ============================================================

UPDATE Citizen SET marital_status = 'Married' WHERE citizen_id IN (60, 61);
INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(61, 60, 'Husband'),
(60, 61, 'Wife'),
(6,  60, 'Father'),
(5,  60, 'Father'),
(6,  61, 'Mother'),
(5,  61, 'Mother'),
(60, 6,  'Son'),
(60, 5,  'Daughter'),
(61, 6,  'Son'),
(61, 5,  'Daughter');

INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(5, 6, 'Brother'),     -- For 5(F), 6(M) is the Brother
(6, 5, 'Sister');      -- For 6(M), 5(F) is the Sister

UPDATE Citizen SET marital_status = 'Married' WHERE citizen_id IN (6, 7, 4, 5);
INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(7, 6, 'Husband'),     -- For 7(F), 6(M) is the Husband
(6, 7, 'Wife'),
(5, 4, 'Husband'),     -- For 5(F), 4(M) is the Husband
(4, 5, 'Wife');


-- ============================================================
--  FAMILY 5 — Cousin Marriage Demonstration
-- ============================================================

INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(68, 66, 'Brother'),   -- For 68(M), 66(M) is the Brother
(66, 68, 'Brother');

UPDATE Citizen SET marital_status = 'Married' WHERE citizen_id IN (66, 67, 68, 69);
INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(67, 66, 'Husband'),
(66, 67, 'Wife'),
(69, 68, 'Husband'),
(68, 69, 'Wife');

-- Children of 66+67
INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(10, 66, 'Father'),    -- For 10, 66 is the Father
(9,  66, 'Father'),    
(10, 67, 'Mother'),    
(9,  67, 'Mother'),    
(66, 10, 'Son'),
(66,  9, 'Daughter'),
(67, 10, 'Son'),
(67,  9, 'Daughter');

-- Children of 68+69
INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(8,  68, 'Father'),    
(11, 68, 'Father'),    
(8,  69, 'Mother'),    
(11, 69, 'Mother'),    
(68,  8, 'Son'),
(68, 11, 'Daughter'),
(69,  8, 'Son'),
(69, 11, 'Daughter');

-- Siblings within each family
INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(9,  10, 'Brother'),   -- For 9(F), 10(M) is the Brother
(10,  9, 'Sister'),    -- For 10(M), 9(F) is the Sister
(11,  8, 'Brother'),   -- For 11(F), 8(M) is the Brother
(8,  11, 'Sister');    -- For 8(M), 11(F) is the Sister

-- Cousin marriages
UPDATE Citizen SET marital_status = 'Married' WHERE citizen_id IN (10, 11);
INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(11, 10, 'Husband'),   -- For 11(F), 10(M) is the Husband
(10, 11, 'Wife');      -- For 10(M), 11(F) is the Wife

UPDATE Citizen SET marital_status = 'Married' WHERE citizen_id IN (8, 9);
INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type) VALUES
(9,  8,  'Husband'),   -- For 9(F), 8(M) is the Husband
(8,  9,  'Wife');      -- For 8(M), 9(F) is the Wife


-- ============================================================
--  VERIFICATION
-- ============================================================

SELECT 'Total relationships inserted:' AS info, COUNT(*) AS total
FROM Family_Relationship;

SELECT
    CONCAT(c1.first_name, ' (', c1.citizen_id, ', ', TIMESTAMPDIFF(YEAR,c1.dob,CURDATE()), 'yr, ', c1.gender, ')') AS citizen,
    'has' AS _,
    fr.relationship_type AS relationship,
    CONCAT(c2.first_name, ' (', c2.citizen_id, ', ', TIMESTAMPDIFF(YEAR,c2.dob,CURDATE()), 'yr, ', c2.gender, ')') AS related_citizen
FROM Family_Relationship fr
JOIN Citizen c1 ON c1.citizen_id = fr.citizen_id
JOIN Citizen c2 ON c2.citizen_id = fr.related_citizen_id
ORDER BY fr.citizen_id, fr.related_citizen_id;

-- Should return 0 rows
SELECT 'Conflict rows (should be 0):' AS check_name, COUNT(*) AS count
FROM FamilyRelationshipConflicts_View;
