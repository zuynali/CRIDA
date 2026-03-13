from flask import Blueprint, jsonify
from db import execute_query
from middleware.auth import token_required

family_bp = Blueprint("family", __name__)

# Schema reference:
# Family_Relationship: (citizen_id, related_citizen_id, relationship_type, ...)
# Marriage_Registration: marriage_id, husband_id, wife_id, marriage_date,
#                        marriage_certificate_number, registration_date


@family_bp.route("/<int:cid>", methods=["GET"])
@token_required
def get_family_tree(cid):
    citizen = execute_query(
        """SELECT citizen_id, national_id_number,
                  CONCAT(first_name,' ',last_name) AS full_name,
                  dob, gender, status
           FROM Citizen WHERE citizen_id = %s""",
        (cid,), fetch='one')
    if not citizen:
        return jsonify({"error": "Citizen not found"}), 404

    # Forward relationships (this citizen is the primary)
    relationships = execute_query(
        """SELECT fr.relationship_type,
                  c.citizen_id, c.national_id_number,
                  CONCAT(c.first_name,' ',c.last_name) AS full_name,
                  c.dob, c.gender, c.status
           FROM Family_Relationship fr
           JOIN Citizen c ON fr.related_citizen_id = c.citizen_id
           WHERE fr.citizen_id = %s""",
        (cid,), fetch='all')

    # Reverse relationships (this citizen appears as related)
    rev_relationships = execute_query(
        """SELECT fr.relationship_type,
                  c.citizen_id, c.national_id_number,
                  CONCAT(c.first_name,' ',c.last_name) AS full_name,
                  c.dob, c.gender, c.status
           FROM Family_Relationship fr
           JOIN Citizen c ON fr.citizen_id = c.citizen_id
           WHERE fr.related_citizen_id = %s""",
        (cid,), fetch='all')

    # Spouse from Marriage_Registration
    spouse = execute_query(
        """SELECT mr.marriage_id, mr.marriage_date, mr.marriage_certificate_number,
                  CASE WHEN mr.husband_id = %s
                       THEN CONCAT(w.first_name,' ',w.last_name)
                       ELSE CONCAT(h.first_name,' ',h.last_name) END AS spouse_name,
                  CASE WHEN mr.husband_id = %s
                       THEN mr.wife_id ELSE mr.husband_id END AS spouse_id
           FROM Marriage_Registration mr
           JOIN Citizen h ON mr.husband_id = h.citizen_id
           JOIN Citizen w ON mr.wife_id = w.citizen_id
           WHERE mr.husband_id = %s OR mr.wife_id = %s
           ORDER BY mr.marriage_id DESC LIMIT 1""",
        (cid, cid, cid, cid), fetch='one')

    return jsonify({
        "citizen": citizen,
        "spouse": spouse,
        "relationships": relationships or [],
        "reverse_relations": rev_relationships or [],
        "tree_summary": {
            "total_relations": len(relationships or []) + len(rev_relationships or []),
            "has_spouse": bool(spouse)
        }
    }), 200
