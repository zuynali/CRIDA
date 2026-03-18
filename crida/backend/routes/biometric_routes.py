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

# ── Resolve uploads directory relative to this file ──────────────────────
# backend/routes/biometric_routes.py  →  backend/uploads/
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_UPLOADS_DIR = os.path.join(_BACKEND_DIR, "uploads")


def _resolve_path(file_path: str) -> str:
    """
    Return an absolute path for a stored file_path value.
    Handles three cases:
      1. Already absolute              → use as-is
      2. Starts with 'uploads/'        → join with backend dir
      3. Just a filename               → join with uploads dir
    """
    if os.path.isabs(file_path):
        return file_path
    if file_path.startswith("uploads/") or file_path.startswith("uploads\\"):
        return os.path.join(_BACKEND_DIR, file_path)
    return os.path.join(_UPLOADS_DIR, file_path)


# ─────────────────────────────────────────────────────────────────────────
#  UPLOAD PHOTO  (called by enrollBiometric() before /biometric/enroll)
#
#  Accepts a base64 JPEG, saves it to disk, and inserts / replaces the
#  row in Document with document_type = 'photo'.
#
#  Schema respected:
#    Document.document_type  ENUM('photo','signature','supporting_doc')
#    Document.file_path      VARCHAR(255) NOT NULL
#    Document.citizen_id     FK → Citizen.citizen_id
#
#  This endpoint lives on the biometric blueprint for convenience.
#  If you prefer to move it to a documents blueprint, change the URL prefix.
# ─────────────────────────────────────────────────────────────────────────

@biometric_bp.route("/upload-photo", methods=["POST"])
@token_required
@permission_required("manage_biometric")
def upload_photo():
    """
    Body: { citizen_id: int, image: "data:image/jpeg;base64,…" }
    Saves the JPEG to uploads/citizen_<id>_photo.jpg and upserts Document.
    """
    import base64

    data = request.json or {}
    ok, err = require_fields(data, "citizen_id", "image")
    if not ok:
        return jsonify({"error": err}), 400

    cid = data["citizen_id"]

    # Validate citizen exists
    citizen = execute_query(
        "SELECT citizen_id FROM Citizen WHERE citizen_id = %s",
        (cid,), fetch="one")
    if not citizen:
        return jsonify({"error": "Citizen not found"}), 404

    # Decode base64
    raw = data["image"]
    if "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        img_bytes = base64.b64decode(raw)
    except Exception as e:
        return jsonify({"error": f"Could not decode image: {e}"}), 400

    if len(img_bytes) < 1000:
        return jsonify({"error": "Image too small — ensure camera is live"}), 400

    # Save to disk — one canonical file per citizen keeps things simple
    os.makedirs(_UPLOADS_DIR, exist_ok=True)
    filename  = f"citizen_{cid}_photo.jpg"
    full_path = os.path.join(_UPLOADS_DIR, filename)
    rel_path  = f"uploads/{filename}"   # stored in DB; _resolve_path() maps this back

    with open(full_path, "wb") as f:
        f.write(img_bytes)

    logger.info(f"upload_photo: saved {full_path} ({len(img_bytes)} bytes)")

    # Upsert Document row
    # Delete any existing 'photo' document for this citizen first so we
    # don't accumulate stale rows. The verify route takes the newest row
    # (ORDER BY document_id DESC LIMIT 1) so this is safe either way, but
    # deletion keeps things tidy.
    existing_doc = execute_query(
        "SELECT document_id FROM Document WHERE citizen_id = %s AND document_type = 'photo'",
        (cid,), fetch="one")

    if existing_doc:
        execute_query(
            "UPDATE Document SET file_path = %s, uploaded_at = CURRENT_TIMESTAMP, "
            "verification_status = 'pending' WHERE document_id = %s",
            (rel_path, existing_doc["document_id"]))
    else:
        execute_query(
            "INSERT INTO Document (citizen_id, document_type, file_path, verification_status) "
            "VALUES (%s, 'photo', %s, 'pending')",
            (cid, rel_path))

    return jsonify({
        "message":   "Photo saved",
        "file_path": rel_path
    }), 200


# ─────────────────────────────────────────────────────────────────────────
#  ENROLL
#
#  FIX: The original UPDATE overwrote BOTH columns unconditionally.
#  This caused enrollFingerprint() (which sends facial_scan_hash = "")
#  to blank-out the facial hash that was set by enrollBiometric().
#
#  New behaviour:
#    • Only update a column if the submitted value is non-empty.
#    • If BOTH are empty on an existing row, return a 400.
#    • On INSERT both values are required (fingerprint_hash has NOT NULL
#      in the schema, so we default to "" if truly absent).
# ─────────────────────────────────────────────────────────────────────────

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
        (data["citizen_id"],), fetch="one")
    if not citizen:
        return jsonify({"error": "Citizen not found"}), 404

    fp_hash   = (data.get("fingerprint_hash") or "").strip()
    face_hash = (data.get("facial_scan_hash")  or "").strip()

    existing = execute_query(
        "SELECT biometric_id, fingerprint_hash, facial_scan_hash "
        "FROM Biometric_Data WHERE citizen_id = %s",
        (data["citizen_id"],), fetch="one")

    if existing:
        # Partial update: only overwrite columns that have new non-empty values.
        # This lets enrollFingerprint() and enrollBiometric() be called
        # independently without clobbering each other's data.
        new_fp   = fp_hash   if fp_hash   else existing["fingerprint_hash"]
        new_face = face_hash if face_hash else existing["facial_scan_hash"]

        if not new_fp and not new_face:
            return jsonify({"error": "Nothing to update — provide at least one hash"}), 400

        execute_query(
            "UPDATE Biometric_Data SET fingerprint_hash = %s, facial_scan_hash = %s "
            "WHERE citizen_id = %s",
            (new_fp, new_face, data["citizen_id"]))
        return jsonify({"message": "Biometric data updated"}), 200
    else:
        # INSERT — Biometric_Data.fingerprint_hash is NOT NULL in the schema
        # Default to empty string if caller only enrolled a face this time.
        execute_query(
            "INSERT INTO Biometric_Data (citizen_id, fingerprint_hash, facial_scan_hash) "
            "VALUES (%s, %s, %s)",
            (data["citizen_id"], fp_hash, face_hash))
        return jsonify({"message": "Biometric data enrolled"}), 201


# ─────────────────────────────────────────────────────────────────────────
#  VERIFY FINGERPRINT
# ─────────────────────────────────────────────────────────────────────────

@biometric_bp.route("/verify-fingerprint", methods=["POST"])
@token_required
def verify_fingerprint():
    data = request.json or {}
    ok, err = require_fields(data, "citizen_id", "fingerprint_hash")
    if not ok:
        return jsonify({"error": err}), 400

    record = execute_query(
        "SELECT fingerprint_hash FROM Biometric_Data WHERE citizen_id = %s",
        (data["citizen_id"],), fetch="one")
    if not record:
        return jsonify({"error": "No biometric data enrolled for this citizen"}), 404

    stored    = str(record["fingerprint_hash"] or "")
    submitted = str(data["fingerprint_hash"]   or "")

    if not stored:
        return jsonify({"error": "No fingerprint hash enrolled — use Enroll Fingerprint first"}), 404

    # Constant-time comparison prevents timing attacks
    match = hmac.compare_digest(stored, submitted)
    return jsonify({"verified": match, "method": "fingerprint"}), 200


# ─────────────────────────────────────────────────────────────────────────
#  VERIFY FACE
#  (Unchanged — reads from Document table which upload_photo() now fills)
# ─────────────────────────────────────────────────────────────────────────

@biometric_bp.route("/verify-face", methods=["POST"])
@token_required
def verify_face():
    """
    Compare a submitted base64 JPEG against the citizen's stored photo.

    Priority:
      1. face_recognition  (ML-based, most accurate)
      2. opencv ORB        (feature matching, good fallback)
      3. Returns a clear error — does NOT silently return false
    """
    data = request.json or {}
    ok, err = require_fields(data, "citizen_id", "image")
    if not ok:
        return jsonify({"error": err}), 400

    # ── 1. Find stored photo ─────────────────────────────────────────────
    doc = execute_query(
        "SELECT file_path FROM Document "
        "WHERE citizen_id = %s AND document_type = 'photo' "
        "ORDER BY document_id DESC LIMIT 1",
        (data["citizen_id"],), fetch="one")

    if not doc:
        return jsonify({
            "error": "No photo on file for this citizen. "
                     "Use the Enroll Biometric button (with camera on) to upload one first."
        }), 404

    stored_path = _resolve_path(doc["file_path"])
    logger.info(f"verify_face: stored_path={stored_path}, exists={os.path.exists(stored_path)}")

    if not os.path.exists(stored_path):
        return jsonify({
            "error": f"Photo file not found on disk: {doc['file_path']}. "
                     "Re-enroll via the Enroll Biometric button."
        }), 404

    # ── 2. Decode submitted image ────────────────────────────────────────
    import base64
    import io
    try:
        raw = data["image"]
        if "," in raw:
            raw = raw.split(",", 1)[1]
        img_bytes = base64.b64decode(raw)
    except Exception as e:
        return jsonify({"error": f"Could not decode image: {e}"}), 400

    if len(img_bytes) < 1000:
        return jsonify({"error": "Image too small — make sure camera is on"}), 400

    # ── 3a. Try face_recognition (dlib) ──────────────────────────────────
    try:
        import face_recognition
        import numpy as np

        known_img  = face_recognition.load_image_file(stored_path)
        known_encs = face_recognition.face_encodings(known_img)
        if not known_encs:
            return jsonify({
                "error": "No face detected in the stored photo. "
                         "Re-enroll with a clearer front-facing photo."
            }), 400

        unknown_img  = face_recognition.load_image_file(io.BytesIO(img_bytes))
        unknown_encs = face_recognition.face_encodings(unknown_img)
        if not unknown_encs:
            return jsonify({
                "verified": False,
                "reason":   "No face detected in the camera frame. "
                            "Ensure good lighting and face the camera directly.",
                "method":   "face_recognition"
            }), 200

        distance   = face_recognition.face_distance([known_encs[0]], unknown_encs[0])[0]
        verified   = bool(distance < 0.55)
        confidence = round((1.0 - float(distance)) * 100, 1)

        logger.info(f"face_recognition: distance={distance:.3f}, verified={verified}")
        return jsonify({
            "verified":   verified,
            "confidence": confidence,
            "distance":   round(float(distance), 4),
            "method":     "face_recognition"
        }), 200

    except Exception as _e:
        logger.warning("face_recognition not installed — falling back to OpenCV ORB")

    # ── 3b. Fallback: OpenCV ORB feature matching ─────────────────────────
    try:
        import cv2
        import numpy as np

        known_bgr = cv2.imread(stored_path)
        if known_bgr is None:
            return jsonify({"error": "Could not read stored photo file"}), 500

        nparr       = np.frombuffer(img_bytes, np.uint8)
        unknown_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if unknown_bgr is None:
            return jsonify({"error": "Could not decode submitted image"}), 400

        known_gray   = cv2.cvtColor(known_bgr,   cv2.COLOR_BGR2GRAY)
        unknown_gray = cv2.cvtColor(unknown_bgr, cv2.COLOR_BGR2GRAY)

        h = 300
        def resize_h(img, height):
            ratio = height / img.shape[0]
            return cv2.resize(img, (int(img.shape[1] * ratio), height))

        known_gray   = resize_h(known_gray,   h)
        unknown_gray = resize_h(unknown_gray, h)

        orb = cv2.ORB_create(nfeatures=500)
        kp1, des1 = orb.detectAndCompute(known_gray,   None)
        kp2, des2 = orb.detectAndCompute(unknown_gray, None)

        if des1 is None or des2 is None or len(des1) < 10 or len(des2) < 10:
            return jsonify({
                "verified": False,
                "reason":   "Not enough facial features detected. "
                            "Ensure good lighting and face the camera.",
                "method":   "opencv_orb"
            }), 200

        bf      = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = bf.match(des1, des2)
        matches = sorted(matches, key=lambda m: m.distance)

        good     = [m for m in matches if m.distance < 50]
        score    = len(good) / max(len(matches), 1)
        verified = score > 0.15

        confidence = round(min(score * 200, 100), 1)
        logger.info(f"OpenCV ORB: good={len(good)}, total={len(matches)}, score={score:.3f}")

        return jsonify({
            "verified":   verified,
            "confidence": confidence,
            "method":     "opencv_orb",
            "note":       "Install face_recognition for better accuracy"
        }), 200

    except Exception as _e:
        return jsonify({"error": f"OpenCV failed: {_e}"}), 500

    # ── 3c. Neither library available ────────────────────────────────────
    return jsonify({
        "error": (
            "No face comparison library available on the server. "
            "Install one of: face_recognition (best) or opencv-python (fallback).\n"
            "Run: pip install face_recognition  OR  pip install opencv-python"
        )
    }), 501


# ─────────────────────────────────────────────────────────────────────────
#  DEBUG  (dev only — remove in production)
# ─────────────────────────────────────────────────────────────────────────

@biometric_bp.route("/debug/<int:citizen_id>", methods=["GET"])
@token_required
def debug_citizen(citizen_id):
    bio = execute_query(
        "SELECT * FROM Biometric_Data WHERE citizen_id = %s",
        (citizen_id,), fetch="one")

    doc = execute_query(
        "SELECT document_id, file_path, verification_status, uploaded_at "
        "FROM Document "
        "WHERE citizen_id = %s AND document_type = 'photo' "
        "ORDER BY document_id DESC LIMIT 1",
        (citizen_id,), fetch="one")

    photo_info = None
    if doc:
        resolved = _resolve_path(doc["file_path"])
        photo_info = {
            "db_path":    doc["file_path"],
            "resolved":   resolved,
            "exists":     os.path.exists(resolved),
            "size_bytes": os.path.getsize(resolved) if os.path.exists(resolved) else None,
            "status":     doc["verification_status"],
            "uploaded":   str(doc["uploaded_at"])
        }

    return jsonify({
        "citizen_id":    citizen_id,
        "biometric_row": dict(bio) if bio else None,
        "photo":         photo_info,
        "uploads_dir":   _UPLOADS_DIR,
        "backend_dir":   _BACKEND_DIR
    }), 200