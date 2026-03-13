import base64
import os
import logging
from flask import Blueprint, request, jsonify, current_app, g
from middleware.auth import token_required
from db import execute_query
from utils.validators import require_fields

logger = logging.getLogger(__name__)
camera_bp = Blueprint("camera", __name__)

# Schema reference:
# Document: document_id, citizen_id, document_type, file_path,
#           verification_status, verified_by


@camera_bp.route("/capture", methods=["POST"])
@token_required
def capture_photo():
    """
    POST /api/v1/camera/capture
    Body: { "citizen_id": 1, "image": "<base64 JPEG string>" }
    Steps:
    1. Decode base64 → PIL Image
    2. face_recognition: detect exactly 1 face (gracefully skips if not installed)
    3. rembg: remove background (gracefully skips if not installed)
    4. Save to uploads/photos/{citizen_id}.png
    5. Update/insert Document table record
    """
    data = request.json or {}
    ok, err = require_fields(data, "citizen_id", "image")
    if not ok:
        return jsonify({"error": err}), 400

    citizen = execute_query(
        "SELECT citizen_id FROM Citizen WHERE citizen_id = %s",
        (data["citizen_id"],), fetch='one')
    if not citizen:
        return jsonify({"error": "Citizen not found"}), 404

    # Decode base64 (handle data:image/jpeg;base64,... prefix)
    try:
        img_data = base64.b64decode(data["image"].split(",")[-1])
    except Exception:
        return jsonify({"error": "Invalid base64 image data"}), 400

    upload_dir = current_app.config.get("UPLOAD_DIR",
        os.path.join(os.path.dirname(__file__), "..", "uploads", "photos"))
    os.makedirs(upload_dir, exist_ok=True)

    citizen_id = data["citizen_id"]
    out_path = os.path.join(upload_dir, f"{citizen_id}.png")
    face_count = None
    bg_removed = False

    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(img_data)).convert("RGB")

        # Step 2: face detection (graceful degradation)
        try:
            import face_recognition
            import numpy as np
            img_array = np.array(img)
            face_locations = face_recognition.face_locations(img_array)
            face_count = len(face_locations)
            if face_count == 0:
                return jsonify({"error": "No person detected. Please capture a clear photo."}), 400
            if face_count > 1:
                return jsonify({"error": f"{face_count} faces detected. Only one person allowed."}), 400
        except ImportError:
            logger.info("face_recognition not installed — skipping face detection")

        # Step 3: background removal (graceful degradation)
        try:
            from rembg import remove
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="PNG")
            removed = remove(img_bytes.getvalue())
            with open(out_path, "wb") as f:
                f.write(removed)
            bg_removed = True
        except ImportError:
            logger.info("rembg not installed — saving original image")
            img.save(out_path, "PNG")

    except ImportError:
        # Absolute fallback: save raw bytes
        with open(out_path, "wb") as f:
            f.write(img_data)

    # Step 5: update/insert Document record
    existing = execute_query(
        "SELECT document_id FROM Document WHERE citizen_id = %s AND document_type = 'photo'",
        (citizen_id,), fetch='one')
    if existing:
        execute_query(
            """UPDATE Document
               SET file_path = %s, verification_status = 'pending', verified_by = NULL
               WHERE document_id = %s""",
            (out_path, existing["document_id"]))
    else:
        execute_query(
            """INSERT INTO Document
               (citizen_id, document_type, file_path, verification_status, verified_by)
               VALUES (%s, 'photo', %s, 'pending', NULL)""",
            (citizen_id, out_path))

    return jsonify({
        "message": "Photo captured and processed",
        "path": out_path,
        "face_count": face_count,
        "bg_removed": bg_removed
    }), 200