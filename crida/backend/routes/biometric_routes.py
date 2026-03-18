import os
import hmac
import logging
from flask import Blueprint, request, jsonify, g
from middleware.auth import token_required
from middleware.rbac import permission_required
from db import execute_query
from utils.validators import require_fields

logger = logging.getLogger(__name__)
biometric_bp = Blueprint("biometric", __name__)


# Schema reference:
# Biometric_Data: biometric_id, citizen_id, fingerprint_hash, facial_scan_hash


@biometric_bp.route("/enroll", methods=["POST"])
@token_required
@permission_required("manage_biometric")
def enroll():
    data = request.json or {}
    ok, err = require_fields(data, "citizen_id")
    if not ok:
        return jsonify({"error": err}), 400

    citizen = execute_query(
        "SELECT citizen_id FROM Citizen WHERE citizen_id = %s",
        (data["citizen_id"],), fetch='one')
    if not citizen:
        return jsonify({"error": "Citizen not found"}), 404

    existing = execute_query(
        "SELECT biometric_id FROM Biometric_Data WHERE citizen_id = %s",
        (data["citizen_id"],), fetch='one')
    if existing:
        execute_query(
            """UPDATE Biometric_Data
               SET fingerprint_hash = %s, facial_scan_hash = %s
               WHERE citizen_id = %s""",
            (data.get("fingerprint_hash", ""),
             data.get("facial_scan_hash", ""),
             data["citizen_id"]))
        return jsonify({"message": "Biometric data updated"}), 200
    else:
        execute_query(
            """INSERT INTO Biometric_Data
               (citizen_id, fingerprint_hash, facial_scan_hash)
               VALUES (%s, %s, %s)""",
            (data["citizen_id"],
             data.get("fingerprint_hash", ""),
             data.get("facial_scan_hash", "")))
        return jsonify({"message": "Biometric data enrolled"}), 201


@biometric_bp.route("/verify-fingerprint", methods=["POST"])
@token_required
def verify_fingerprint():
    data = request.json or {}
    ok, err = require_fields(data, "citizen_id", "fingerprint_hash")
    if not ok:
        return jsonify({"error": err}), 400

    record = execute_query(
        "SELECT fingerprint_hash FROM Biometric_Data WHERE citizen_id = %s",
        (data["citizen_id"],), fetch='one')
    if not record:
        return jsonify({"error": "No biometric data enrolled for this citizen"}), 404

    # Constant-time comparison prevents timing attacks
    match = hmac.compare_digest(
        str(record["fingerprint_hash"]),
        str(data["fingerprint_hash"]))

    return jsonify({"verified": match, "method": "fingerprint"}), 200


@biometric_bp.route("/verify-face", methods=["POST"])
@token_required
def verify_face():
    """
    Compare submitted base64 image against stored photo.
    Uses face_recognition if available; falls back to hash comparison.
    """
    data = request.json or {}
    ok, err = require_fields(data, "citizen_id", "image")
    if not ok:
        return jsonify({"error": err}), 400

    doc = execute_query(
        "SELECT file_path FROM Document WHERE citizen_id = %s AND document_type = 'photo' LIMIT 1",
        (data["citizen_id"],), fetch='one')
    if not doc or not os.path.exists(doc["file_path"]):
        return jsonify({"error": "No stored photo for this citizen"}), 404

    import base64
    import io
    try:
        img_bytes = base64.b64decode(data["image"].split(",")[-1])

        try:
            import face_recognition
            import numpy as np
            known = face_recognition.load_image_file(doc["file_path"])
            known_enc = face_recognition.face_encodings(known)
            if not known_enc:
                return jsonify({"error": "No face found in stored photo"}), 400

            unknown = face_recognition.load_image_file(io.BytesIO(img_bytes))
            unknown_enc = face_recognition.face_encodings(unknown)
            if not unknown_enc:
                return jsonify({"verified": False, "reason": "No face in submitted image"}), 200

            distance = face_recognition.face_distance([known_enc[0]], unknown_enc[0])[0]
            verified = bool(distance < 0.6)
            return jsonify({
                "verified": verified,
                "confidence": round((1 - float(distance)) * 100, 1),
                "method": "face_recognition"
            }), 200

        except ImportError:
            # Fallback: hash comparison against Biometric_Data
            import hashlib
            submitted_hash = hashlib.sha256(img_bytes).hexdigest()
            record = execute_query(
                "SELECT facial_scan_hash FROM Biometric_Data WHERE citizen_id = %s",
                (data["citizen_id"],), fetch='one')
            if not record:
                return jsonify({"error": "No biometric data enrolled"}), 404
            match = hmac.compare_digest(
                str(record["facial_scan_hash"]), submitted_hash)
            return jsonify({"verified": match, "method": "hash_fallback"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    