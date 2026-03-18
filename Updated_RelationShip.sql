-- First, let's see what we're about to change (optional preview)
SELECT 'Current relationships before reversal:' as '';
SELECT relationship_type, COUNT(*) FROM Family_Relationship GROUP BY relationship_type;

-- ============================================================
-- REVERSE ALL RELATIONSHIPS
-- ============================================================
UPDATE Family_Relationship SET relationship_type = 
    CASE relationship_type
        -- Parent/Child reversals
        WHEN 'Father' THEN 'Mother'
        WHEN 'Mother' THEN 'Father'
        WHEN 'Son' THEN 'Daughter'
        WHEN 'Daughter' THEN 'Son'
        
        -- Sibling reversals
        WHEN 'Brother' THEN 'Sister'
        WHEN 'Sister' THEN 'Brother'
        
        -- Spouse reversals
        WHEN 'Husband' THEN 'Wife'
        WHEN 'Wife' THEN 'Husband'
        
        -- Extended family reversals
        WHEN 'Nephew' THEN 'Niece'
        WHEN 'Niece' THEN 'Nephew'
        
        -- In-law reversals
        WHEN 'Brother-in-law' THEN 'Sister-in-law'
        WHEN 'Sister-in-law' THEN 'Brother-in-law'
        
        -- Keep Cousin unchanged (gender-neutral)
        ELSE relationship_type
    END;

-- ============================================================
-- VERIFY THE CHANGES
-- ============================================================
SELECT 'Relationships after reversal:' as '';
SELECT 
    relationship_type,
    COUNT(*) AS count
FROM Family_Relationship
GROUP BY relationship_type
ORDER BY count DESC;

-- ============================================================
-- SAMPLE CHECK: Show some reversed relationships
-- ============================================================
SELECT 'Sample of reversed relationships:' as '';
SELECT 
    citizen_id,
    related_citizen_id,
    relationship_type
FROM Family_Relationship
WHERE citizen_id IN (11, 21, 31, 41, 61)
ORDER BY citizen_id, related_citizen_id
LIMIT 20;