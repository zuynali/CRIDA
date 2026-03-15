

import os
import logging

from flask import Flask, jsonify
from flask_cors import CORS
from flask_bcrypt import Bcrypt

from db import test_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})  
bcrypt = Bcrypt(app)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads", "photos")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.config["UPLOAD_DIR"] = UPLOAD_DIR

from routes.auth_routes        import auth_bp
from routes.citizen_routes     import citizen_bp
from routes.cnic_routes        import cnic_bp
from routes.passport_routes    import passport_bp
from routes.license_routes     import license_bp
from routes.registration_routes import reg_bp
from routes.pdf_routes         import pdf_bp
from routes.family_tree_routes import family_bp
from routes.security_routes    import security_bp
from routes.update_request_routes import update_bp
from routes.camera_routes      import camera_bp
from routes.biometric_routes   import biometric_bp
from routes.complaint_routes   import complaint_bp
from routes.permission_routes  import permission_bp
from routes.notification_routes import notification_bp
from routes.payment_routes     import payment_bp
from routes.audit_routes       import audit_bp

blueprints = [
    (auth_bp,         "/api/v1/auth"),
    (citizen_bp,      "/api/v1/citizens"),
    (cnic_bp,         "/api/v1/cnic"),
    (passport_bp,     "/api/v1/passports"),
    (license_bp,      "/api/v1/licenses"),
    (reg_bp,          "/api/v1/registrations"),
    (pdf_bp,          "/api/v1/pdf"),
    (family_bp,       "/api/v1/family-tree"),
    (security_bp,     "/api/v1/security"),
    (update_bp,       "/api/v1/update-requests"),
    (camera_bp,       "/api/v1/camera"),
    (biometric_bp,    "/api/v1/biometric"),
    (complaint_bp,    "/api/v1/complaints"),
    (permission_bp,   "/api/v1/permissions"),
    (notification_bp, "/api/v1/notifications"),
    (payment_bp,      "/api/v1/payments"),
    (audit_bp,        "/api/v1/audit"),
]

for bp, prefix in blueprints:
    app.register_blueprint(bp, url_prefix=prefix)

@app.route("/api/v1/health")
def health():
    db_ok = test_connection()
    return jsonify({
        "status":   "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "error",
        "service":  "CRIDA Phase 2 API"
    }), 200 if db_ok else 503


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found", "status": 404}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error", "status": 500}), 500



if __name__ == "__main__":
    logger.info("Starting CRIDA API on http://localhost:5000")
    for rule in app.url_map.iter_rules():
        print(rule)
    app.run(debug=True, host="0.0.0.0", port=5000)
