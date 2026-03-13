import base64
import os
from flask import Blueprint, request, jsonify, current_app, g
from middleware.auth import token_required
from db import execute_query
from utils.validators import require_fields

camera_bp = Blueprint("camera", __name__)


@camera_bp.route("/capture", methods=["POST"])
@token_required
def capture_photo():
    """
    POST /api/v1/camera/capture
    Body: { "citizen_id": 1, "image": "<base64 JPEG string>" }
    Saves photo to uploads/photos/{citizen_id}.png and updates Document table.
    """
    data = request.json or {}
    ok, err = require_fields(data, "citizen_id", "image")
    if not ok:
        return jsonify({"error": err}), 400

    # Decode base64
    try:
        img_b64 = data["image"]
        if "," in img_b64:
            img_b64 = img_b64.split(",", 1)[1]
        img_data = base64.b64decode(img_b64)
    except Exception:
        return jsonify({"error": "Invalid base64 image data"}), 400

    citizen_id = int(data["citizen_id"])
    upload_dir = current_app.config["UPLOAD_DIR"]
    out_path = os.path.join(upload_dir, f"{citizen_id}.png")

    # Save image using PIL (convert to PNG)
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(img_data)).convert("RGB")
        img.save(out_path, "PNG")
    except ImportError:
        with open(out_path, "wb") as f:
            f.write(img_data)
    except Exception as e:
        return jsonify({"error": f"Image processing failed: {str(e)}"}), 500

    # Update Document table
    try:
        existing = execute_query(
            "SELECT document_id FROM Document "
            "WHERE citizen_id = %s AND document_type = 'photo'",
            (citizen_id,), fetch='one'
        )
        if existing:
            execute_query(
                "UPDATE Document "
                "SET file_path = %s, verification_status = 'pending', verified_by = NULL "
                "WHERE document_id = %s",
                (out_path, existing["document_id"])
            )
        else:
            execute_query(
                "INSERT INTO Document "
                "(citizen_id, document_type, file_path, verification_status, verified_by) "
                "VALUES (%s, 'photo', %s, 'pending', NULL)",
                (citizen_id, out_path)
            )
    except Exception as e:
        return jsonify({
            "message": "Photo saved (DB update failed)",
            "path": out_path,
            "face_count": None,
            "bg_removed": False,
            "db_warning": str(e)
        }), 200

    return jsonify({
        "message": "Photo captured and processed",
        "path": out_path,
        "face_count": None,
        "bg_removed": False
    }), 200