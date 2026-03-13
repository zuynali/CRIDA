from fpdf import FPDF
import os
from db import execute_query
from datetime import date

LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "uploads", "crida_logo.png")


class CRIDAPDF(FPDF):
    def header(self):
        self.set_fill_color(31, 78, 121)
        self.rect(0, 0, 210, 22, "F")
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(255, 255, 255)
        self.set_xy(10, 5)
        self.cell(0, 12, "CRIDA - Citizen Registration & Identity Database Authority", ln=True)
        self.set_font("Helvetica", "", 8)
        self.set_xy(10, 15)
        self.cell(0, 5, "Government of Pakistan | Secure Document")
        self.set_text_color(0, 0, 0)
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5,
                  f"CRIDA Official Document | Generated: {date.today()} | Page {self.page_no()}",
                  align="C")

    def section_header(self, title):
        self.set_fill_color(46, 117, 182)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 8, f"  {title}", fill=True, ln=True)
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def field_row(self, label, value):
        self.set_font("Helvetica", "B", 9)
        self.cell(55, 7, label + ":", border="B")
        self.set_font("Helvetica", "", 9)
        self.cell(0, 7, str(value or "-"), border="B", ln=True)

    def add_citizen_photo(self, photo_path):
        if photo_path and os.path.exists(photo_path):
            try:
                self.image(photo_path, x=160, y=30, w=35, h=40)
            except Exception:
                pass


def generate_cnic_pdf(citizen_id):
    c = execute_query(
        "SELECT * FROM CitizenProfile_View WHERE citizen_id = %s LIMIT 1",
        (citizen_id,), fetch='one')
    if not c:
        raise ValueError("Citizen not found")

    # CNIC_Card schema: card_id, citizen_id, card_number, issue_date, expiry_date, card_status
    card = execute_query(
        "SELECT * FROM CNIC_Card WHERE citizen_id = %s ORDER BY card_id DESC LIMIT 1",
        (citizen_id,), fetch='one')

    pdf = CRIDAPDF()
    pdf.add_page()
    pdf.section_header("NATIONAL IDENTITY CARD (CNIC)")
    pdf.ln(2)

    photo = execute_query(
        "SELECT file_path FROM Document WHERE citizen_id=%s AND document_type='photo' LIMIT 1",
        (citizen_id,), fetch='one')
    if photo:
        pdf.add_citizen_photo(photo["file_path"])

    pdf.field_row("Full Name", c["full_name"])
    pdf.field_row("National ID", c["national_id_number"])
    pdf.field_row("Date of Birth", str(c["dob"]))
    pdf.field_row("Gender", c["gender"])
    pdf.field_row("Blood Group", c.get("blood_group") or "-")
    pdf.field_row("Marital Status", c["marital_status"])
    pdf.field_row("Current City", c.get("city") or "-")
    pdf.field_row("Province", c.get("province") or "-")

    if card:
        pdf.ln(4)
        pdf.section_header("CARD DETAILS")
        pdf.field_row("Card Number", card["card_number"])
        pdf.field_row("Issue Date", str(card["issue_date"]))
        pdf.field_row("Expiry Date", str(card["expiry_date"]))
        pdf.field_row("Card Status", card["card_status"])

    return bytes(pdf.output())


def generate_passport_pdf(citizen_id):
    c = execute_query(
        "SELECT * FROM CitizenProfile_View WHERE citizen_id = %s LIMIT 1",
        (citizen_id,), fetch='one')
    if not c:
        raise ValueError("Citizen not found")

    # Passport schema: passport_id, citizen_id, passport_number, issue_date, expiry_date, passport_status
    p = execute_query(
        "SELECT * FROM Passport WHERE citizen_id = %s ORDER BY passport_id DESC LIMIT 1",
        (citizen_id,), fetch='one')

    pdf = CRIDAPDF()
    pdf.add_page()
    pdf.section_header("PAKISTANI PASSPORT")
    pdf.field_row("Surname", c["full_name"].split()[-1])
    pdf.field_row("Given Names", " ".join(c["full_name"].split()[:-1]))
    pdf.field_row("National ID", c["national_id_number"])
    pdf.field_row("Date of Birth", str(c["dob"]))
    pdf.field_row("Gender", c["gender"])
    pdf.field_row("Nationality", "Pakistani")

    if p:
        pdf.ln(4)
        pdf.section_header("PASSPORT DETAILS")
        pdf.field_row("Passport No", p["passport_number"])
        pdf.field_row("Issue Date", str(p["issue_date"]))
        pdf.field_row("Expiry Date", str(p["expiry_date"]))
        pdf.field_row("Status", p.get("passport_status") or "Active")

    return bytes(pdf.output())


def generate_license_pdf(citizen_id):
    c = execute_query(
        "SELECT * FROM CitizenProfile_View WHERE citizen_id=%s LIMIT 1", (citizen_id,), fetch='one')
    if not c:
        raise ValueError("Citizen not found")

    # Driving_License schema: license_id, citizen_id, license_number, issue_date, expiry_date, license_type, status
    lic = execute_query(
        "SELECT * FROM Driving_License WHERE citizen_id=%s AND status='Valid' ORDER BY license_id DESC LIMIT 1",
        (citizen_id,), fetch='one')

    pdf = CRIDAPDF()
    pdf.add_page()
    pdf.section_header("DRIVING LICENSE")
    pdf.field_row("Full Name", c["full_name"])
    pdf.field_row("National ID", c["national_id_number"])
    pdf.field_row("Date of Birth", str(c["dob"]))

    if lic:
        pdf.ln(4)
        pdf.section_header("LICENSE DETAILS")
        pdf.field_row("License Number", lic["license_number"])
        pdf.field_row("License Type", lic["license_type"])
        pdf.field_row("Issue Date", str(lic["issue_date"]))
        pdf.field_row("Expiry Date", str(lic["expiry_date"]))
        pdf.field_row("Status", lic["status"])

    return bytes(pdf.output())


def generate_birth_certificate_pdf(citizen_id):
    b = execute_query(
        """SELECT br.*, c.first_name, c.last_name, c.dob, c.gender,
                  h.name AS hospital_name
           FROM Birth_Registration br
           JOIN Citizen c ON br.citizen_id = c.citizen_id
           LEFT JOIN Hospital h ON br.hospital_id = h.hospital_id
           WHERE br.citizen_id = %s LIMIT 1""",
        (citizen_id,), fetch='one')
    if not b:
        raise ValueError("Birth registration not found")

    pdf = CRIDAPDF()
    pdf.add_page()
    pdf.section_header("BIRTH CERTIFICATE")
    pdf.field_row("Child Name", f"{b['first_name']} {b['last_name']}")
    pdf.field_row("Date of Birth", str(b["dob"]))
    pdf.field_row("Gender", b["gender"])
    pdf.field_row("Hospital", b.get("hospital_name") or "-")
    pdf.field_row("Certificate No", b["birth_certificate_number"])
    pdf.field_row("Reg Date", str(b["registration_date"]))

    return bytes(pdf.output())


def generate_death_certificate_pdf(citizen_id):
    d = execute_query(
        """SELECT dr.*, c.first_name, c.last_name
           FROM Death_Registration dr
           JOIN Citizen c ON dr.citizen_id = c.citizen_id
           WHERE dr.citizen_id = %s LIMIT 1""",
        (citizen_id,), fetch='one')
    if not d:
        raise ValueError("Death registration not found")

    pdf = CRIDAPDF()
    pdf.add_page()
    pdf.section_header("DEATH CERTIFICATE")
    pdf.field_row("Deceased Name", f"{d['first_name']} {d['last_name']}")
    pdf.field_row("Date of Death", str(d["date_of_death"]))
    pdf.field_row("Cause of Death", d.get("cause_of_death") or "-")
    pdf.field_row("Place of Death", d.get("place_of_death") or "-")
    pdf.field_row("Certificate No", d["death_certificate_number"])

    return bytes(pdf.output())


def generate_marriage_certificate_pdf(marriage_id):
    m = execute_query(
        """SELECT mr.*,
                  CONCAT(h.first_name,' ',h.last_name) AS husband_name,
                  CONCAT(w.first_name,' ',w.last_name) AS wife_name
           FROM Marriage_Registration mr
           JOIN Citizen h ON mr.husband_id = h.citizen_id
           JOIN Citizen w ON mr.wife_id = w.citizen_id
           WHERE mr.marriage_id = %s""",
        (marriage_id,), fetch='one')
    if not m:
        raise ValueError("Marriage registration not found")

    pdf = CRIDAPDF()
    pdf.add_page()
    pdf.section_header("MARRIAGE CERTIFICATE")
    pdf.field_row("Husband", m["husband_name"])
    pdf.field_row("Wife", m["wife_name"])
    pdf.field_row("Marriage Date", str(m["marriage_date"]))
    pdf.field_row("Reg Date", str(m["registration_date"]))
    pdf.field_row("Certificate No", m["marriage_certificate_number"])

    return bytes(pdf.output())


def generate_payment_slip_pdf(payment_id):
    # Payment_Transaction schema: payment_id, citizen_id, service_type, cnic_app_id,
    # passport_app_id, dl_app_id, amount, payment_method, payment_status,
    # transaction_reference, payment_date
    pt = execute_query(
        """SELECT pt.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
           FROM Payment_Transaction pt
           JOIN Citizen c ON pt.citizen_id = c.citizen_id
           WHERE pt.payment_id = %s""",
        (payment_id,), fetch='one')
    if not pt:
        raise ValueError("Payment not found")

    pdf = CRIDAPDF()
    pdf.add_page()
    pdf.section_header("PAYMENT RECEIPT")
    pdf.field_row("Transaction Ref", pt["transaction_reference"])
    pdf.field_row("Citizen Name", pt["citizen_name"])
    pdf.field_row("Service Type", pt["service_type"])
    pdf.field_row("Amount (PKR)", str(pt["amount"]))
    pdf.field_row("Payment Method", pt["payment_method"])
    pdf.field_row("Status", pt["payment_status"])
    pdf.field_row("Date", str(pt["payment_date"]))

    return bytes(pdf.output())