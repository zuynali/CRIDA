from flask import Blueprint, send_file, jsonify, g
from io import BytesIO
from middleware.auth import token_required
from middleware.rbac import permission_required
from utils.pdf_generator import (
    generate_cnic_pdf, generate_passport_pdf, generate_license_pdf,
    generate_birth_certificate_pdf, generate_death_certificate_pdf,
    generate_marriage_certificate_pdf, generate_payment_slip_pdf,
    generate_placeholder_pdf
)

pdf_bp = Blueprint("pdf", __name__)


def _send_pdf(data_bytes, filename):
    return send_file(
        BytesIO(data_bytes), mimetype="application/pdf",
        as_attachment=True, download_name=filename
    )


@pdf_bp.route("/cnic/<int:cid>", methods=["GET"])
@token_required
@permission_required("generate_pdf", "manage_cnic")
def cnic_pdf(cid):
    try:
        return _send_pdf(generate_cnic_pdf(cid), f"CNIC_{cid}.pdf")
    except ValueError as e:
        return _send_pdf(generate_placeholder_pdf(str(e)), f"CNIC_{cid}.pdf")
    except Exception as e:
        return jsonify({"error": f"PDF generation failed: {str(e)}"}), 500


@pdf_bp.route("/passport/<int:cid>", methods=["GET"])
@token_required
@permission_required("generate_pdf", "manage_passport")
def passport_pdf(cid):
    try:
        return _send_pdf(generate_passport_pdf(cid), f"Passport_{cid}.pdf")
    except ValueError as e:
        return _send_pdf(generate_placeholder_pdf(str(e)), f"Passport_{cid}.pdf")
    except Exception as e:
        return jsonify({"error": f"PDF generation failed: {str(e)}"}), 500


@pdf_bp.route("/license/<int:cid>", methods=["GET"])
@token_required
@permission_required("generate_pdf", "manage_license")
def license_pdf(cid):
    try:
        return _send_pdf(generate_license_pdf(cid), f"DrivingLicense_{cid}.pdf")
    except ValueError as e:
        return _send_pdf(generate_placeholder_pdf(str(e)), f"DrivingLicense_{cid}.pdf")
    except Exception as e:
        return jsonify({"error": f"PDF generation failed: {str(e)}"}), 500


@pdf_bp.route("/birth-certificate/<int:cid>", methods=["GET"])
@token_required
def birth_cert_pdf(cid):
    try:
        return _send_pdf(generate_birth_certificate_pdf(cid), f"BirthCert_{cid}.pdf")
    except ValueError as e:
        return _send_pdf(generate_placeholder_pdf(str(e)), f"BirthCert_{cid}.pdf")
    except Exception as e:
        return jsonify({"error": f"PDF generation failed: {str(e)}"}), 500


@pdf_bp.route("/death-certificate/<int:cid>", methods=["GET"])
@token_required
def death_cert_pdf(cid):
    try:
        return _send_pdf(generate_death_certificate_pdf(cid), f"DeathCert_{cid}.pdf")
    except ValueError as e:
        return _send_pdf(generate_placeholder_pdf(str(e)), f"DeathCert_{cid}.pdf")
    except Exception as e:
        return jsonify({"error": f"PDF generation failed: {str(e)}"}), 500


@pdf_bp.route("/marriage-certificate/<int:mid>", methods=["GET"])
@token_required
def marriage_cert_pdf(mid):
    try:
        return _send_pdf(generate_marriage_certificate_pdf(mid), f"MarriageCert_{mid}.pdf")
    except ValueError as e:
        return _send_pdf(generate_placeholder_pdf(str(e)), f"MarriageCert_{mid}.pdf")
    except Exception as e:
        return jsonify({"error": f"PDF generation failed: {str(e)}"}), 500


@pdf_bp.route("/payment-slip/<int:pid>", methods=["GET"])
@token_required
def payment_slip_pdf(pid):
    try:
        return _send_pdf(generate_payment_slip_pdf(pid), f"PaymentSlip_{pid}.pdf")
    except ValueError as e:
        return _send_pdf(generate_placeholder_pdf(str(e)), f"PaymentSlip_{pid}.pdf")
    except Exception as e:
        return jsonify({"error": f"PDF generation failed: {str(e)}"}), 500
