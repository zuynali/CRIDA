-- ============================================================
-- relationship_checks.sql
-- Comprehensive relationship consistency & integrity checks
-- for the Family_Relationship table.
--
-- Run AFTER schema.sql (uses the CRID database and its tables).
-- ============================================================

USE CRID;

-- Drop any existing triggers first to ensure clean state
DROP TRIGGER IF EXISTS trk_validate_relationship_insert;
DROP TRIGGER IF EXISTS trk_validate_relationship_update;
DROP TRIGGER IF EXISTS trk_validate_marriage_family;
DROP TRIGGER IF EXISTS trk_sync_spouse_relationship;
DROP TRIGGER IF EXISTS trk_block_deceased_relationship;
DROP TRIGGER IF EXISTS trk_block_sibling_age_overlap;
DROP FUNCTION IF EXISTS fn_has_relationship;
DROP FUNCTION IF EXISTS fn_relationship_type;

-- ============================================================
-- HELPER STORED FUNCTION: fn_has_relationship
-- Returns 1 if a direct relationship of ANY of the given types
-- exists between two citizens (in either direction).
-- ============================================================

DELIMITER //

CREATE FUNCTION fn_has_relationship(
    p_a INT,
    p_b INT,
    p_types VARCHAR(500)   -- comma-separated list e.g. 'Father,Mother'
)
RETURNS TINYINT
READS SQL DATA
DETERMINISTIC
BEGIN
    DECLARE v_count INT DEFAULT 0;

    SELECT COUNT(*) INTO v_count
    FROM Family_Relationship
    WHERE (
        (citizen_id = p_a AND related_citizen_id = p_b)
        OR
        (citizen_id = p_b AND related_citizen_id = p_a)
    )
    AND FIND_IN_SET(relationship_type, p_types) > 0;

    RETURN IF(v_count > 0, 1, 0);
END//

DELIMITER ;


-- ============================================================
-- HELPER STORED FUNCTION: fn_relationship_type
-- Returns the relationship_type from A -> B (or NULL).
-- ============================================================

DELIMITER //

CREATE FUNCTION fn_relationship_type(p_from INT, p_to INT)
RETURNS VARCHAR(50)
READS SQL DATA
DETERMINISTIC
BEGIN
    DECLARE v_type VARCHAR(50);

    SELECT relationship_type INTO v_type
    FROM Family_Relationship
    WHERE citizen_id = p_from AND related_citizen_id = p_to
    LIMIT 1;

    RETURN v_type;
END//

DELIMITER ;


-- ============================================================
-- TRIGGER: trk_validate_relationship_insert
--
-- Fires BEFORE INSERT on Family_Relationship.
-- SEMANTIC RULE: related_citizen_id IS the relationship_type!
-- e.g. (1, 2, 'Father') means 2 is the Father of 1.
-- ============================================================

DELIMITER //

CREATE TRIGGER trk_validate_relationship_insert
BEFORE INSERT ON Family_Relationship
FOR EACH ROW
BEGIN
    -- ── working variables ────────────────────────────────────────
    DECLARE v_new_gender      VARCHAR(10);
    DECLARE v_related_gender  VARCHAR(10);
    DECLARE v_new_dob         DATE;
    DECLARE v_related_dob     DATE;
    DECLARE v_age_diff        INT;
    DECLARE v_marital_status_a VARCHAR(20);
    DECLARE v_marital_status_b VARCHAR(20);

    DECLARE v_existing_fwd    VARCHAR(50);
    DECLARE v_existing_rev    VARCHAR(50);

    DECLARE v_dup_count       INT DEFAULT 0;

    -- ── fetch citizen details ────────────────────────────────────
    SELECT gender, dob, marital_status INTO v_new_gender, v_new_dob, v_marital_status_a
    FROM Citizen WHERE citizen_id = NEW.citizen_id;

    SELECT gender, dob, marital_status INTO v_related_gender, v_related_dob, v_marital_status_b
    FROM Citizen WHERE citizen_id = NEW.related_citizen_id;

    -- ── fetch existing direct relationships ──────────────────────
    SET v_existing_fwd = fn_relationship_type(NEW.citizen_id,         NEW.related_citizen_id);
    SET v_existing_rev = fn_relationship_type(NEW.related_citizen_id, NEW.citizen_id);

    -- ────────────────────────────────────────────────────────────
    -- RULE 10: Duplicate entry guard
    -- ────────────────────────────────────────────────────────────
    SELECT COUNT(*) INTO v_dup_count
    FROM Family_Relationship
    WHERE citizen_id         = NEW.citizen_id
      AND related_citizen_id = NEW.related_citizen_id
      AND relationship_type  = NEW.relationship_type;

    IF v_dup_count > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Duplicate relationship: this exact entry already exists.';
    END IF;

    -- ────────────────────────────────────────────────────────────
    -- RULE 2: Gender constraints (Check the RELATED citizen)
    -- ────────────────────────────────────────────────────────────
    IF NEW.relationship_type IN ('Father','Husband','Son','Brother') AND v_related_gender != 'Male' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Gender mismatch: Father/Husband/Son/Brother must be Male.';
    END IF;

    IF NEW.relationship_type IN ('Mother','Wife','Daughter','Sister') AND v_related_gender != 'Female' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Gender mismatch: Mother/Wife/Daughter/Sister must be Female.';
    END IF;

    -- ────────────────────────────────────────────────────────────
    -- RULE: Marital status
    -- ────────────────────────────────────────────────────────────
    IF NEW.relationship_type IN ('Husband','Wife') THEN
        IF v_marital_status_a != 'Married' OR v_marital_status_b != 'Married' THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Cannot register spouse relationship: both citizens must be Married.';
        END IF;
    END IF;

    -- ────────────────────────────────────────────────────────────
    -- RULE 7: Spouse cannot be a direct ancestor or descendant
    -- ────────────────────────────────────────────────────────────
    IF NEW.relationship_type IN ('Husband','Wife') THEN
        IF v_existing_fwd IN ('Father','Mother','Son','Daughter')
        OR v_existing_rev IN ('Father','Mother','Son','Daughter') THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Invalid relationship: A person cannot marry their parent or child.';
        END IF;
        IF v_existing_fwd IN ('Brother','Sister')
        OR v_existing_rev IN ('Brother','Sister') THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Invalid relationship: Siblings cannot be spouses.';
        END IF;
    END IF;

    -- ────────────────────────────────────────────────────────────
    -- RULE 5 / 7: Father/Mother cannot also be Husband/Wife
    -- ────────────────────────────────────────────────────────────
    IF NEW.relationship_type IN ('Father','Mother') THEN
        IF v_existing_fwd IN ('Husband','Wife')
        OR v_existing_rev IN ('Husband','Wife') THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Invalid relationship: A parent cannot simultaneously be a spouse to the same person.';
        END IF;
    END IF;

    -- ────────────────────────────────────────────────────────────
    -- RULE 8: Cannot be sibling AND parent/child of the same person
    -- ────────────────────────────────────────────────────────────
    IF NEW.relationship_type IN ('Brother','Sister') THEN
        IF v_existing_fwd IN ('Father','Mother','Son','Daughter')
        OR v_existing_rev IN ('Father','Mother','Son','Daughter') THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Invalid relationship: A sibling cannot also be a parent or child to the same person.';
        END IF;
    END IF;

    IF NEW.relationship_type IN ('Son','Daughter') THEN
        IF v_existing_fwd IN ('Brother','Sister')
        OR v_existing_rev IN ('Brother','Sister') THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Invalid relationship: A child cannot also be a sibling to the same person.';
        END IF;
    END IF;

    -- ────────────────────────────────────────────────────────────
    -- RULE 3 & 1: Invalid combination checks (conflicting roles)
    -- ────────────────────────────────────────────────────────────
    IF v_existing_fwd IS NOT NULL AND v_existing_fwd != NEW.relationship_type THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Conflicting relationship: a different relationship already exists in this direction for this pair.';
    END IF;

    IF v_existing_rev IS NOT NULL THEN
        -- Parent ↔ Child inverse validation
        IF NEW.relationship_type = 'Father' AND v_existing_rev NOT IN ('Son','Daughter') THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Conflicting relationship: the reverse entry is not Son/Daughter for a Father.';
        END IF;
        IF NEW.relationship_type IN ('Son','Daughter') AND v_existing_rev NOT IN ('Father','Mother') THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Conflicting relationship: the reverse entry is not Father/Mother for a Son/Daughter.';
        END IF;
        IF NEW.relationship_type = 'Mother' AND v_existing_rev NOT IN ('Son','Daughter') THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Conflicting relationship: the reverse entry is not Son/Daughter for a Mother.';
        END IF;

        -- Spouse inverse validation
        IF NEW.relationship_type = 'Husband' AND v_existing_rev != 'Wife' THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Conflicting relationship: the reverse entry is not Wife for a Husband.';
        END IF;
        IF NEW.relationship_type = 'Wife' AND v_existing_rev != 'Husband' THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Conflicting relationship: the reverse entry is not Husband for a Wife.';
        END IF;

        -- Sibling inverse validation
        IF NEW.relationship_type IN ('Brother','Sister')
           AND v_existing_rev NOT IN ('Brother','Sister') THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Conflicting relationship: the reverse entry is not Brother/Sister for a sibling.';
        END IF;
    END IF;

    -- ────────────────────────────────────────────────────────────
    -- RULE 9: Age sanity for parent–child
    -- Parent must be at least 14 years older than child.
    -- ────────────────────────────────────────────────────────────
    IF NEW.relationship_type IN ('Father','Mother') THEN
        -- related_citizen is the parent, new_dob is the child
        SET v_age_diff = TIMESTAMPDIFF(YEAR, v_related_dob, v_new_dob);
        IF v_age_diff < 14 THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Age conflict: A parent must be at least 14 years older than their child.';
        END IF;
    END IF;

    IF NEW.relationship_type IN ('Son','Daughter') THEN
        -- related_citizen is the child, new_dob is the parent
        SET v_age_diff = TIMESTAMPDIFF(YEAR, v_new_dob, v_related_dob);
        IF v_age_diff < 14 THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Age conflict: A parent must be at least 14 years older than their child.';
        END IF;
    END IF;

END//

DELIMITER ;


-- ============================================================
-- TRIGGER: trk_validate_relationship_update
-- ============================================================

DELIMITER //

CREATE TRIGGER trk_validate_relationship_update
BEFORE UPDATE ON Family_Relationship
FOR EACH ROW
BEGIN
    DECLARE v_new_gender      VARCHAR(10);
    DECLARE v_related_gender  VARCHAR(10);
    DECLARE v_new_dob         DATE;
    DECLARE v_related_dob     DATE;
    DECLARE v_age_diff        INT;
    DECLARE v_existing_fwd    VARCHAR(50);
    DECLARE v_existing_rev    VARCHAR(50);
    DECLARE v_dup_count       INT DEFAULT 0;

    SELECT gender, dob INTO v_new_gender, v_new_dob
    FROM Citizen WHERE citizen_id = NEW.citizen_id;

    SELECT gender, dob INTO v_related_gender, v_related_dob
    FROM Citizen WHERE citizen_id = NEW.related_citizen_id;

    SELECT COUNT(*) INTO v_dup_count
    FROM Family_Relationship
    WHERE citizen_id         = NEW.citizen_id
      AND related_citizen_id = NEW.related_citizen_id
      AND relationship_type  = NEW.relationship_type
      AND relationship_id   != OLD.relationship_id;

    IF v_dup_count > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Duplicate relationship: this exact entry already exists.';
    END IF;

    IF NEW.relationship_type IN ('Father','Husband','Son','Brother') AND v_related_gender != 'Male' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Gender mismatch: Father/Husband/Son/Brother must be Male.';
    END IF;

    IF NEW.relationship_type IN ('Mother','Wife','Daughter','Sister') AND v_related_gender != 'Female' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Gender mismatch: Mother/Wife/Daughter/Sister must be Female.';
    END IF;

    IF NEW.relationship_type IN ('Husband','Wife') THEN
        SELECT relationship_type INTO v_existing_fwd
        FROM Family_Relationship
        WHERE citizen_id = NEW.citizen_id AND related_citizen_id = NEW.related_citizen_id
          AND relationship_id != OLD.relationship_id LIMIT 1;

        SELECT relationship_type INTO v_existing_rev
        FROM Family_Relationship
        WHERE citizen_id = NEW.related_citizen_id AND related_citizen_id = NEW.citizen_id
          AND relationship_id != OLD.relationship_id LIMIT 1;

        IF v_existing_fwd IN ('Father','Mother','Son','Daughter')
        OR v_existing_rev IN ('Father','Mother','Son','Daughter') THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Invalid relationship: A person cannot marry their parent or child.';
        END IF;

        IF v_existing_fwd IN ('Brother','Sister')
        OR v_existing_rev IN ('Brother','Sister') THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Invalid relationship: Siblings cannot be spouses.';
        END IF;
    END IF;

    IF NEW.relationship_type IN ('Father','Mother') THEN
        SET v_age_diff = TIMESTAMPDIFF(YEAR, v_related_dob, v_new_dob);
        IF v_age_diff < 14 THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Age conflict: A parent must be at least 14 years older than their child.';
        END IF;
    END IF;

    IF NEW.relationship_type IN ('Son','Daughter') THEN
        SET v_age_diff = TIMESTAMPDIFF(YEAR, v_new_dob, v_related_dob);
        IF v_age_diff < 14 THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Age conflict: A parent must be at least 14 years older than their child.';
        END IF;
    END IF;

END//

DELIMITER ;


-- ============================================================
-- TRIGGER: trk_validate_marriage_family
-- ============================================================
DELIMITER //

CREATE TRIGGER trk_validate_marriage_family
BEFORE INSERT ON Marriage_Registration
FOR EACH ROW
BEGIN
    DECLARE v_direct_rel    VARCHAR(50);
    DECLARE v_reverse_rel   VARCHAR(50);
    DECLARE v_uncle_count   INT DEFAULT 0;
    DECLARE v_aunt_count    INT DEFAULT 0;
    DECLARE v_gp_count      INT DEFAULT 0;

    SET v_direct_rel  = fn_relationship_type(NEW.husband_id, NEW.wife_id);
    SET v_reverse_rel = fn_relationship_type(NEW.wife_id,    NEW.husband_id);

    IF v_direct_rel IN ('Father','Son') OR v_reverse_rel IN ('Mother','Daughter') THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Marriage blocked: Husband and Wife share a parent-child relationship.';
    END IF;

    IF v_direct_rel IN ('Mother','Daughter') OR v_reverse_rel IN ('Father','Son') THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Marriage blocked: Husband and Wife share a parent-child relationship.';
    END IF;

    IF v_direct_rel IN ('Brother','Sister') OR v_reverse_rel IN ('Brother','Sister') THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Marriage blocked: Husband and Wife are siblings.';
    END IF;

    -- Uncle check (Husband is Brother to Wife's Parent)
    SELECT COUNT(*) INTO v_uncle_count
    FROM Family_Relationship AS wparent
    JOIN Family_Relationship AS husbrother
      ON husbrother.citizen_id         = NEW.husband_id
     AND husbrother.related_citizen_id = wparent.related_citizen_id
     AND husbrother.relationship_type  = 'Brother'
    WHERE wparent.citizen_id         = NEW.wife_id
      AND wparent.relationship_type  IN ('Father','Mother');

    IF v_uncle_count > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Marriage blocked: Husband is an uncle of the Wife.';
    END IF;

    -- Aunt check
    SELECT COUNT(*) INTO v_aunt_count
    FROM Family_Relationship AS hparent
    JOIN Family_Relationship AS wifesister
      ON wifesister.citizen_id         = NEW.wife_id
     AND wifesister.related_citizen_id = hparent.related_citizen_id
     AND wifesister.relationship_type  = 'Sister'
    WHERE hparent.citizen_id          = NEW.husband_id
      AND hparent.relationship_type   IN ('Father','Mother');

    IF v_aunt_count > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Marriage blocked: Wife is an aunt of the Husband.';
    END IF;

    -- Nephew / Niece checks reverse these
    SELECT COUNT(*) INTO v_aunt_count
    FROM Family_Relationship AS hparent
    JOIN Family_Relationship AS wifesister
      ON wifesister.citizen_id         = NEW.wife_id
     AND wifesister.related_citizen_id  = hparent.citizen_id
     AND wifesister.relationship_type   = 'Sister'
    WHERE hparent.related_citizen_id   = NEW.husband_id
      AND hparent.relationship_type    IN ('Father','Mother');

    IF v_aunt_count > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Marriage blocked: Wife is an aunt (via nephew) of the Husband.';
    END IF;

    SELECT COUNT(*) INTO v_uncle_count
    FROM Family_Relationship AS wparent
    JOIN Family_Relationship AS husbrother
      ON husbrother.citizen_id         = NEW.husband_id
     AND husbrother.related_citizen_id  = wparent.citizen_id
     AND husbrother.relationship_type   = 'Brother'
    WHERE wparent.related_citizen_id   = NEW.wife_id
      AND wparent.relationship_type    IN ('Father','Mother');

    IF v_uncle_count > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Marriage blocked: Husband is an uncle (via niece) of the Wife.';
    END IF;

    -- Grandparent checks
    SELECT COUNT(*) INTO v_gp_count
    FROM Family_Relationship AS mid_h
    JOIN Family_Relationship AS to_wife
      ON to_wife.related_citizen_id = mid_h.related_citizen_id
     AND to_wife.citizen_id         = NEW.wife_id
     AND to_wife.relationship_type  IN ('Father','Mother')
    WHERE mid_h.citizen_id          = NEW.husband_id
      AND mid_h.relationship_type   IN ('Father','Mother');

    IF v_gp_count > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Marriage blocked: Husband is a grandparent of the Wife.';
    END IF;

    SELECT COUNT(*) INTO v_gp_count
    FROM Family_Relationship AS mid_w
    JOIN Family_Relationship AS to_husb
      ON to_husb.related_citizen_id = mid_w.related_citizen_id
     AND to_husb.citizen_id         = NEW.husband_id
     AND to_husb.relationship_type  IN ('Father','Mother')
    WHERE mid_w.citizen_id          = NEW.wife_id
      AND mid_w.relationship_type   IN ('Father','Mother');

    IF v_gp_count > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Marriage blocked: Wife is a grandparent of the Husband.';
    END IF;

    -- Step-parent checks
    SELECT COUNT(*) INTO v_uncle_count
    FROM Marriage_Registration AS mr
    JOIN Family_Relationship   AS fr
      ON fr.citizen_id         = NEW.wife_id
     AND fr.related_citizen_id = mr.wife_id
     AND fr.relationship_type  = 'Mother'
    WHERE mr.husband_id = NEW.husband_id;

    IF v_uncle_count > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Marriage blocked: Husband is a step-father of the Wife.';
    END IF;

    SELECT COUNT(*) INTO v_aunt_count
    FROM Marriage_Registration AS mr
    JOIN Family_Relationship   AS fr
      ON fr.citizen_id         = NEW.husband_id
     AND fr.related_citizen_id = mr.husband_id
     AND fr.relationship_type  = 'Father'
    WHERE mr.wife_id = NEW.wife_id;

    IF v_aunt_count > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Marriage blocked: Wife is a step-mother of the Husband.';
    END IF;

END//

DELIMITER ;


-- ============================================================
-- TRIGGER: trk_sync_spouse_relationship
-- ============================================================

DELIMITER //

CREATE TRIGGER trk_sync_spouse_relationship
AFTER INSERT ON Marriage_Registration
FOR EACH ROW
BEGIN
    UPDATE Citizen SET marital_status = 'Married'
    WHERE citizen_id IN (NEW.husband_id, NEW.wife_id);

    -- For Wife, her Husband is NEW.husband_id
    IF fn_relationship_type(NEW.wife_id, NEW.husband_id) IS NULL THEN
        INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type)
        VALUES (NEW.wife_id, NEW.husband_id, 'Husband');
    END IF;

    -- For Husband, his Wife is NEW.wife_id
    IF fn_relationship_type(NEW.husband_id, NEW.wife_id) IS NULL THEN
        INSERT INTO Family_Relationship (citizen_id, related_citizen_id, relationship_type)
        VALUES (NEW.husband_id, NEW.wife_id, 'Wife');
    END IF;
END//

DELIMITER ;


-- ============================================================
-- TRIGGER: trk_block_deceased_relationship
-- ============================================================

DELIMITER //

CREATE TRIGGER trk_block_deceased_relationship
BEFORE INSERT ON Family_Relationship
FOR EACH ROW
BEGIN
    DECLARE v_status_a VARCHAR(20);
    DECLARE v_status_b VARCHAR(20);

    SELECT status INTO v_status_a FROM Citizen WHERE citizen_id = NEW.citizen_id;
    SELECT status INTO v_status_b FROM Citizen WHERE citizen_id = NEW.related_citizen_id;

    IF v_status_a = 'deceased' OR v_status_b = 'deceased' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Cannot add relationship: citizen is deceased.';
    END IF;
END//

DELIMITER ;


-- ============================================================
-- TRIGGER: trk_block_sibling_age_overlap
-- ============================================================

DELIMITER //

CREATE TRIGGER trk_block_sibling_age_overlap
BEFORE INSERT ON Family_Relationship
FOR EACH ROW
BEGIN
    DECLARE v_dob_a DATE;
    DECLARE v_dob_b DATE;
    DECLARE v_gap   INT;

    IF NEW.relationship_type IN ('Brother','Sister') THEN
        SELECT dob INTO v_dob_a FROM Citizen WHERE citizen_id = NEW.citizen_id;
        SELECT dob INTO v_dob_b FROM Citizen WHERE citizen_id = NEW.related_citizen_id;

        SET v_gap = ABS(TIMESTAMPDIFF(YEAR, v_dob_a, v_dob_b));

        IF v_gap > 50 THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Age conflict: Siblings cannot be more than 50 years apart in age.';
        END IF;
    END IF;

END//

DELIMITER ;


-- ============================================================
-- VIEW: FamilyRelationshipConflicts_View
-- ============================================================

CREATE OR REPLACE VIEW FamilyRelationshipConflicts_View AS

-- 1. Gender mismatches (checks related_citizen_id gender)
SELECT
    fr.relationship_id,
    fr.citizen_id,
    fr.related_citizen_id,
    fr.relationship_type,
    'Gender mismatch' AS conflict_type
FROM Family_Relationship fr
JOIN Citizen c ON c.citizen_id = fr.related_citizen_id
WHERE
    (fr.relationship_type IN ('Father','Husband','Son','Brother') AND c.gender != 'Male')
 OR (fr.relationship_type IN ('Mother','Wife','Daughter','Sister') AND c.gender != 'Female')

UNION ALL

-- 2. Self-relationships
SELECT
    relationship_id, citizen_id, related_citizen_id,
    relationship_type, 'Self-relationship'
FROM Family_Relationship
WHERE citizen_id = related_citizen_id

UNION ALL

-- 3. Parent younger than child (related_citizen is parent, citizen is child)
SELECT
    fr.relationship_id, fr.citizen_id, fr.related_citizen_id,
    fr.relationship_type, 'Parent younger than child'
FROM Family_Relationship fr
JOIN Citizen c_a ON c_a.citizen_id = fr.citizen_id
JOIN Citizen c_b ON c_b.citizen_id = fr.related_citizen_id
WHERE fr.relationship_type IN ('Father','Mother')
  AND TIMESTAMPDIFF(YEAR, c_b.dob, c_a.dob) < 14

UNION ALL

-- 3b. Parent younger than child (related_citizen is child, citizen is parent)
SELECT
    fr.relationship_id, fr.citizen_id, fr.related_citizen_id,
    fr.relationship_type, 'Parent younger than child'
FROM Family_Relationship fr
JOIN Citizen c_a ON c_a.citizen_id = fr.citizen_id
JOIN Citizen c_b ON c_b.citizen_id = fr.related_citizen_id
WHERE fr.relationship_type IN ('Son','Daughter')
  AND TIMESTAMPDIFF(YEAR, c_a.dob, c_b.dob) < 14

UNION ALL

-- 4. Siblings with > 50 year gap
SELECT
    fr.relationship_id, fr.citizen_id, fr.related_citizen_id,
    fr.relationship_type, 'Sibling age gap > 50 years'
FROM Family_Relationship fr
JOIN Citizen ca ON ca.citizen_id = fr.citizen_id
JOIN Citizen cb ON cb.citizen_id = fr.related_citizen_id
WHERE fr.relationship_type IN ('Brother','Sister')
  AND ABS(TIMESTAMPDIFF(YEAR, ca.dob, cb.dob)) > 50

UNION ALL

-- 5. Duplicate entries
SELECT
    fr.relationship_id, fr.citizen_id, fr.related_citizen_id,
    fr.relationship_type, 'Duplicate entry'
FROM Family_Relationship fr
WHERE (
    SELECT COUNT(*)
    FROM Family_Relationship fr2
    WHERE fr2.citizen_id         = fr.citizen_id
      AND fr2.related_citizen_id = fr.related_citizen_id
      AND fr2.relationship_type  = fr.relationship_type
) > 1;

-- ============================================================
-- END OF relationship_checks.sql
-- ============================================================
