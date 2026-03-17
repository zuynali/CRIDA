"""
pdf.py  –  CRIDA PDF generator (drop-in replacement)
All functions return bytes, identical signatures to the original.
"""

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white
from reportlab.lib.units import mm
from datetime import date, datetime
from io import BytesIO
import math
import os

# ── try importing db; if running standalone it won't exist ──────────────────
try:
    from db import execute_query
except ImportError:
    execute_query = None

# ── colour palette ───────────────────────────────────────────────────────────
PK_GREEN   = HexColor('#01411C')
DARK_NAVY  = HexColor('#1a2744')
CARD_BG    = HexColor('#F5F7FA')
FIELD_LINE = HexColor('#CCCCCC')
LIGHT_GRAY = HexColor('#888888')
PAGE_BG    = HexColor('#E8ECF2')
ACCENT     = HexColor('#AACCEE')
MID_BLUE   = HexColor('#6688AA')


# ═══════════════════════════════════════════════════════════════════════════
#  SHARED DRAWING HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _draw_star(c, cx, cy, outer_r, inner_r, points=5):
    path = c.beginPath()
    for i in range(points * 2):
        angle = math.pi / points * i - math.pi / 2
        r = outer_r if i % 2 == 0 else inner_r
        px, py = cx + r * math.cos(angle), cy + r * math.sin(angle)
        if i == 0: path.moveTo(px, py)
        else:      path.lineTo(px, py)
    path.close()
    c.drawPath(path, stroke=0, fill=1)


def _draw_pakistan_flag(c, cx, cy, radius):
    c.setFillColor(PK_GREEN)
    c.circle(cx, cy, radius, stroke=0, fill=1)
    c.setFillColor(white)
    c.rect(cx - radius, cy - radius, radius * 0.5, radius * 2, stroke=0, fill=1)
    c.circle(cx - radius * 0.05, cy, radius * 0.62, stroke=0, fill=1)
    c.setFillColor(PK_GREEN)
    c.circle(cx + radius * 0.12, cy, radius * 0.5, stroke=0, fill=1)
    c.setFillColor(white)
    _draw_star(c, cx + radius * 0.3, cy + radius * 0.2, radius * 0.18, radius * 0.07)


def _field(c, label, value, lx, ly, width):
    """Single label+value+underline block."""
    c.setFont("Helvetica", 6.5)
    c.setFillColor(LIGHT_GRAY)
    c.drawString(lx, ly, label)
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(DARK_NAVY)
    c.drawString(lx, ly - 4 * mm, str(value) if value else "-")
    c.setStrokeColor(FIELD_LINE)
    c.setLineWidth(0.4)
    c.line(lx, ly - 6 * mm, lx + width, ly - 6 * mm)


def _signature(c, sx, sy):
    """Fake cursive signature scribble."""
    c.setStrokeColor(white)
    c.setLineWidth(0.8)
    path = c.beginPath()
    path.moveTo(sx, sy)
    path.curveTo(sx+3*mm, sy+2*mm, sx+6*mm, sy-1*mm, sx+9*mm,  sy+1.5*mm)
    path.curveTo(sx+12*mm, sy+3*mm, sx+15*mm, sy,      sx+18*mm, sy+2*mm)
    c.drawPath(path, stroke=1, fill=0)


def _page_setup(buf):
    """Return a canvas writing to a BytesIO buffer."""
    c = canvas.Canvas(buf, pagesize=A4)
    pw, ph = A4
    c.setFillColor(PAGE_BG)
    c.rect(0, 0, pw, ph, stroke=0, fill=1)
    return c, pw, ph


def _card_frame(c, x, y, w, h):
    """White card background + navy border."""
    c.setFillColor(CARD_BG)
    c.roundRect(x, y, w, h, 8, stroke=0, fill=1)
    c.setStrokeColor(DARK_NAVY)
    c.setLineWidth(1.5)
    c.roundRect(x, y, w, h, 8, stroke=1, fill=0)


def _header_bar(c, x, y, w, h, subtitle):
    """Navy header bar with Pakistan flag + title."""
    header_h = h * 0.20
    c.setFillColor(DARK_NAVY)
    c.rect(x, y + h - header_h, w, header_h, stroke=0, fill=1)

    flag_cx = x + 22 * mm
    flag_cy = y + h - header_h / 2
    flag_r  = header_h * 0.40

    c.setFillColor(white)
    c.circle(flag_cx, flag_cy, flag_r + 1.2, stroke=0, fill=1)
    _draw_pakistan_flag(c, flag_cx, flag_cy, flag_r)

    c.setStrokeColor(white)
    c.setLineWidth(0.5)
    sep_x = flag_cx + flag_r + 4
    c.line(sep_x, flag_cy - flag_r * 0.7, sep_x, flag_cy + flag_r * 0.7)

    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(sep_x + 5, flag_cy + 2 * mm, "PAKISTAN")
    c.setFont("Helvetica", 7.5)
    c.setFillColor(ACCENT)
    c.drawString(sep_x + 5, flag_cy - 4 * mm, subtitle)

    return header_h


def _bottom_bar(c, x, y, w):
    """Navy bottom bar with Principal General signature + CRIDA text."""
    bar_h = 10 * mm
    c.setFillColor(DARK_NAVY)
    c.rect(x, y, w, bar_h, stroke=0, fill=1)

    c.setFont("Helvetica-Bold", 6)
    c.setFillColor(ACCENT)
    c.drawString(x + 4 * mm, y + 6 * mm, "Principal General")
    _signature(c, x + 4 * mm, y + 3.5 * mm)

    c.setFont("Helvetica", 5.5)
    c.setFillColor(MID_BLUE)
    c.drawCentredString(x + w / 2, y + 6 * mm, "CRIDA Official Document")
    c.setFont("Helvetica", 5)
    c.drawCentredString(x + w / 2, y + 3 * mm, "Issued by: Govt. of Pakistan")


def _footer(c, pw, card_y):
    c.setFont("Helvetica", 7)
    c.setFillColor(LIGHT_GRAY)
    c.drawCentredString(pw / 2, card_y - 12 * mm,
        f"CRIDA Official Document  |  Generated: {date.today()}  |  Page 1")


def _photo_placeholder(c, photo_x, photo_y, photo_w, photo_h, photo_path=None):
    # Always draw the border box first
    c.setFillColor(HexColor('#DDE3EC'))
    c.rect(photo_x, photo_y, photo_w, photo_h, stroke=0, fill=1)
    c.setStrokeColor(HexColor('#AABBCC'))
    c.setLineWidth(0.5)
    c.rect(photo_x, photo_y, photo_w, photo_h, stroke=1, fill=0)

    # If a real photo exists, draw it — otherwise draw the silhouette
    if photo_path and os.path.exists(photo_path):
        try:
            c.drawImage(photo_path, photo_x, photo_y, width=photo_w, height=photo_h,
                        preserveAspectRatio=True, mask='auto')
            return
        except Exception:
            pass  # fall through to silhouette if image fails to load

    # Silhouette fallback
    c.setFillColor(HexColor('#AABBCC'))
    hx = photo_x + photo_w / 2
    hy = photo_y + photo_h * 0.67
    c.circle(hx, hy, photo_w * 0.22, stroke=0, fill=1)
    c.ellipse(photo_x + photo_w * 0.1, photo_y + photo_h * 0.05,
              photo_x + photo_w * 0.9, photo_y + photo_h * 0.52, stroke=0, fill=1)


def _auto_dates(data):
    """Fill issue_date (today) and expiry_date (issue + 10 yrs) if missing."""
    issue = data.get("issue_date")
    if not issue:
        issue = date.today()
    elif isinstance(issue, str):
        issue = datetime.strptime(issue, "%Y-%m-%d").date()
    expiry = data.get("expiry_date")
    if not expiry:
        expiry = date(issue.year + 10, issue.month, issue.day)
    elif isinstance(expiry, str):
        expiry = datetime.strptime(expiry, "%Y-%m-%d").date()
    data["issue_date"]  = issue
    data["expiry_date"] = expiry
    return data


def _render(c):
    """Save canvas and return bytes."""
    c.save()


# ═══════════════════════════════════════════════════════════════════════════
#  1. CNIC
# ═══════════════════════════════════════════════════════════════════════════

def _draw_cnic(c, data, x, y, w, h):
    _card_frame(c, x, y, w, h)
    header_h = _header_bar(c, x, y, w, h, "NATIONAL IDENTITY CARD  •  CNIC")

    photo_w, photo_h = 26*mm, 32*mm
    photo_x = x + w - photo_w - 6*mm
    photo_y = y + h - header_h - photo_h - 4*mm
    _photo_placeholder(c, photo_x, photo_y, photo_w, photo_h, data.get("photo_path"))

    left_w  = photo_x - x - 12*mm
    fx      = x + 6*mm
    col_w   = w / 2 - 10*mm
    c2x     = x + w / 2 + 2*mm
    rh      = 11*mm

    r1 = y + h - header_h - 10*mm
    _field(c, "Name",           data.get("full_name","-"),      fx,  r1,       left_w)
    r2 = r1 - rh
    _field(c, "Father Name",    data.get("father_name","-"),    fx,  r2,       left_w)
    r3 = r2 - rh
    _field(c, "Gender",         data.get("gender","-"),         fx,  r3,       col_w)
    _field(c, "Blood Group",    data.get("blood_group","-"),    c2x, r3,       col_w)
    r4 = r3 - rh
    _field(c, "Marital Status", data.get("marital_status","-"), fx,  r4,       col_w)
    _field(c, "Country Of Stay",data.get("country","Pakistan"), c2x, r4,       col_w)

    r5 = y + 36*mm
    _field(c, "Identity Number",data.get("national_id_number","-"), fx,  r5,       col_w)
    _field(c, "Date of Birth",  str(data.get("dob","-")),           c2x, r5,       col_w)
    r6 = r5 - rh
    _field(c, "Date of Issue",  str(data.get("issue_date","-")),    fx,  r6,       col_w)
    _field(c, "Date of Expiry", str(data.get("expiry_date","-")),   c2x, r6,       col_w)

    _bottom_bar(c, x, y, w)


def generate_cnic_pdf(citizen_id):
    row = execute_query(
        "SELECT * FROM CitizenProfile_View WHERE citizen_id=%s LIMIT 1",
        (citizen_id,), fetch='one')
    if not row: raise ValueError("Citizen not found")

    card = execute_query(
        "SELECT * FROM CNIC_Card WHERE citizen_id=%s ORDER BY card_id DESC LIMIT 1",
        (citizen_id,), fetch='one')

    photo = execute_query(
        "SELECT file_path FROM Document WHERE citizen_id=%s AND document_type='photo' LIMIT 1",
        (citizen_id,), fetch='one')

    data = _auto_dates({
        "full_name":          row["full_name"],
        "father_name":        row.get("father_name", "-"),
        "gender":             row["gender"],
        "blood_group":        row.get("blood_group", "-"),
        "marital_status":     row["marital_status"],
        "country":            "Pakistan",
        "national_id_number": row["national_id_number"],
        "dob":                row["dob"],
        "issue_date":         card["issue_date"]  if card else None,
        "expiry_date":        card["expiry_date"] if card else None,
        "photo_path":         photo["file_path"]  if photo else None,
    })

    buf = BytesIO()
    c, pw, ph = _page_setup(buf)
    card_w, card_h = 172*mm, 110*mm
    cx = (pw - card_w) / 2
    cy = (ph - card_h) / 2 + 18*mm
    _draw_cnic(c, data, cx, cy, card_w, card_h)
    _footer(c, pw, cy)
    _render(c)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════
#  2. PASSPORT
# ═══════════════════════════════════════════════════════════════════════════

def _draw_passport(c, data, x, y, w, h):
    _card_frame(c, x, y, w, h)
    header_h = _header_bar(c, x, y, w, h, "ISLAMIC REPUBLIC OF PAKISTAN  •  PASSPORT")

    photo_w, photo_h = 26*mm, 32*mm
    photo_x = x + w - photo_w - 6*mm
    photo_y = y + h - header_h - photo_h - 4*mm
    _photo_placeholder(c, photo_x, photo_y, photo_w, photo_h, data.get("photo_path"))

    left_w = photo_x - x - 12*mm
    fx     = x + 6*mm
    col_w  = w / 2 - 10*mm
    c2x    = x + w / 2 + 2*mm
    rh     = 11*mm

    r1 = y + h - header_h - 10*mm
    _field(c, "Surname",     data.get("surname","-"),     fx,  r1, left_w)
    r2 = r1 - rh
    _field(c, "Given Names", data.get("given_names","-"), fx,  r2, left_w)
    r3 = r2 - rh
    _field(c, "Nationality", "Pakistani",                 fx,  r3, col_w)
    _field(c, "Gender",      data.get("gender","-"),      c2x, r3, col_w)
    r4 = r3 - rh
    _field(c, "National ID", data.get("national_id_number","-"), fx, r4, col_w)
    _field(c, "Date of Birth", str(data.get("dob","-")),        c2x, r4, col_w)

    r5 = y + 36*mm
    _field(c, "Passport No",   data.get("passport_number","-"),   fx,  r5, col_w)
    _field(c, "Date of Issue", str(data.get("issue_date","-")),   c2x, r5, col_w)
    r6 = r5 - rh
    _field(c, "Date of Expiry", str(data.get("expiry_date","-")), fx,  r6, col_w)
    _field(c, "Status",         data.get("status","Active"),      c2x, r6, col_w)

    _bottom_bar(c, x, y, w)


def generate_passport_pdf(citizen_id):
    row = execute_query(
        "SELECT * FROM CitizenProfile_View WHERE citizen_id=%s LIMIT 1",
        (citizen_id,), fetch='one')
    if not row: raise ValueError("Citizen not found")

    p = execute_query(
        "SELECT * FROM Passport WHERE citizen_id=%s ORDER BY passport_id DESC LIMIT 1",
        (citizen_id,), fetch='one')

    photo = execute_query(
        "SELECT file_path FROM Document WHERE citizen_id=%s AND document_type='photo' LIMIT 1",
        (citizen_id,), fetch='one')

    parts = row["full_name"].split()
    data = _auto_dates({
        "surname":            parts[-1] if parts else "-",
        "given_names":        " ".join(parts[:-1]) if len(parts) > 1 else "-",
        "gender":             row["gender"],
        "national_id_number": row["national_id_number"],
        "dob":                row["dob"],
        "passport_number":    p["passport_number"]           if p else "-",
        "issue_date":         p["issue_date"]                if p else None,
        "expiry_date":        p["expiry_date"]               if p else None,
        "status":             p.get("passport_status","Active") if p else "Active",
        "photo_path":         photo["file_path"]             if photo else None,
    })

    buf = BytesIO()
    c, pw, ph = _page_setup(buf)
    card_w, card_h = 172*mm, 110*mm
    cx = (pw - card_w) / 2
    cy = (ph - card_h) / 2 + 18*mm
    _draw_passport(c, data, cx, cy, card_w, card_h)
    _footer(c, pw, cy)
    _render(c)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════
#  3. DRIVING LICENSE
# ═══════════════════════════════════════════════════════════════════════════

def _draw_license(c, data, x, y, w, h):
    _card_frame(c, x, y, w, h)
    header_h = _header_bar(c, x, y, w, h, "DRIVING LICENSE  •  GOVT. OF PAKISTAN")

    photo_w, photo_h = 26*mm, 32*mm
    photo_x = x + w - photo_w - 6*mm
    photo_y = y + h - header_h - photo_h - 4*mm
    _photo_placeholder(c, photo_x, photo_y, photo_w, photo_h, data.get("photo_path"))

    left_w = photo_x - x - 12*mm
    fx     = x + 6*mm
    col_w  = w / 2 - 10*mm
    c2x    = x + w / 2 + 2*mm
    rh     = 11*mm

    r1 = y + h - header_h - 10*mm
    _field(c, "Full Name",   data.get("full_name","-"),       fx,  r1, left_w)
    r2 = r1 - rh
    _field(c, "National ID", data.get("national_id_number","-"), fx, r2, left_w)
    r3 = r2 - rh
    _field(c, "Date of Birth", str(data.get("dob","-")),      fx,  r3, col_w)
    _field(c, "License Type",  data.get("license_type","-"),  c2x, r3, col_w)

    r5 = y + 36*mm
    _field(c, "License Number", data.get("license_number","-"),   fx,  r5, col_w)
    _field(c, "Date of Issue",  str(data.get("issue_date","-")),  c2x, r5, col_w)
    r6 = r5 - rh
    _field(c, "Date of Expiry", str(data.get("expiry_date","-")), fx,  r6, col_w)
    _field(c, "Status",         data.get("status","Valid"),       c2x, r6, col_w)

    _bottom_bar(c, x, y, w)


def generate_license_pdf(citizen_id):
    row = execute_query(
        "SELECT * FROM CitizenProfile_View WHERE citizen_id=%s LIMIT 1",
        (citizen_id,), fetch='one')
    if not row: raise ValueError("Citizen not found")

    lic = execute_query(
        "SELECT * FROM Driving_License WHERE citizen_id=%s AND status='Valid' ORDER BY license_id DESC LIMIT 1",
        (citizen_id,), fetch='one')

    photo = execute_query(
        "SELECT file_path FROM Document WHERE citizen_id=%s AND document_type='photo' LIMIT 1",
        (citizen_id,), fetch='one')

    data = _auto_dates({
        "full_name":          row["full_name"],
        "national_id_number": row["national_id_number"],
        "dob":                row["dob"],
        "license_number":     lic["license_number"] if lic else "-",
        "license_type":       lic["license_type"]   if lic else "-",
        "issue_date":         lic["issue_date"]      if lic else None,
        "expiry_date":        lic["expiry_date"]      if lic else None,
        "status":             lic["status"]           if lic else "Valid",
        "photo_path":         photo["file_path"]      if photo else None,
    })

    buf = BytesIO()
    c, pw, ph = _page_setup(buf)
    card_w, card_h = 172*mm, 100*mm
    cx = (pw - card_w) / 2
    cy = (ph - card_h) / 2 + 18*mm
    _draw_license(c, data, cx, cy, card_w, card_h)
    _footer(c, pw, cy)
    _render(c)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════
#  4. BIRTH CERTIFICATE
# ═══════════════════════════════════════════════════════════════════════════

def _draw_certificate(c, data, x, y, w, h, subtitle, fields):
    """Generic certificate card — pass list of (label, value, col) tuples."""
    _card_frame(c, x, y, w, h)
    header_h = _header_bar(c, x, y, w, h, subtitle)

    fx    = x + 6*mm
    col_w = w - 12*mm
    h_col = w / 2 - 10*mm
    c2x   = x + w / 2 + 2*mm
    rh    = 11*mm
    cur_y = y + h - header_h - 10*mm

    for label, value, span in fields:
        if span == "full":
            _field(c, label, value, fx, cur_y, col_w)
        elif span == "left":
            _field(c, label, value, fx, cur_y, h_col)
        elif span == "right":
            _field(c, label, value, c2x, cur_y, h_col)
        if span != "right":
            cur_y -= rh

    _bottom_bar(c, x, y, w)


def generate_birth_certificate_pdf(citizen_id):
    b = execute_query(
        """SELECT br.*, c.first_name, c.last_name, c.dob, c.gender,
                  h.name AS hospital_name
           FROM Birth_Registration br
           JOIN Citizen c ON br.citizen_id = c.citizen_id
           LEFT JOIN Hospital h ON br.hospital_id = h.hospital_id
           WHERE br.citizen_id = %s LIMIT 1""",
        (citizen_id,), fetch='one')
    if not b: raise ValueError("Birth registration not found")

    fields = [
        ("Child Name",      f"{b['first_name']} {b['last_name']}", "full"),
        ("Date of Birth",   str(b["dob"]),                         "left"),
        ("Gender",          b["gender"],                           "right"),
        ("Hospital",        b.get("hospital_name") or "-",         "full"),
        ("Certificate No",  b["birth_certificate_number"],         "left"),
        ("Reg Date",        str(b["registration_date"]),           "right"),
    ]

    buf = BytesIO()
    c, pw, ph = _page_setup(buf)
    card_w, card_h = 172*mm, 100*mm
    cx = (pw - card_w) / 2
    cy = (ph - card_h) / 2 + 18*mm
    _draw_certificate(c, {}, cx, cy, card_w, card_h,
                      "BIRTH CERTIFICATE  •  GOVT. OF PAKISTAN", fields)
    _footer(c, pw, cy)
    _render(c)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════
#  5. DEATH CERTIFICATE
# ═══════════════════════════════════════════════════════════════════════════

def generate_death_certificate_pdf(citizen_id):
    d = execute_query(
        """SELECT dr.*, c.first_name, c.last_name
           FROM Death_Registration dr
           JOIN Citizen c ON dr.citizen_id = c.citizen_id
           WHERE dr.citizen_id = %s LIMIT 1""",
        (citizen_id,), fetch='one')
    if not d: raise ValueError("Death registration not found")

    fields = [
        ("Deceased Name",   f"{d['first_name']} {d['last_name']}", "full"),
        ("Date of Death",   str(d["date_of_death"]),               "left"),
        ("Certificate No",  d["death_certificate_number"],         "right"),
        ("Cause of Death",  d.get("cause_of_death") or "-",        "full"),
        ("Place of Death",  d.get("place_of_death") or "-",        "full"),
    ]

    buf = BytesIO()
    c, pw, ph = _page_setup(buf)
    card_w, card_h = 172*mm, 95*mm
    cx = (pw - card_w) / 2
    cy = (ph - card_h) / 2 + 18*mm
    _draw_certificate(c, {}, cx, cy, card_w, card_h,
                      "DEATH CERTIFICATE  •  GOVT. OF PAKISTAN", fields)
    _footer(c, pw, cy)
    _render(c)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════
#  6. MARRIAGE CERTIFICATE
# ═══════════════════════════════════════════════════════════════════════════

def generate_marriage_certificate_pdf(marriage_id):
    m = execute_query(
        """SELECT mr.*,
                  CONCAT(h.first_name,' ',h.last_name) AS husband_name,
                  CONCAT(w.first_name,' ',w.last_name) AS wife_name
           FROM Marriage_Registration mr
           JOIN Citizen h ON mr.husband_id = h.citizen_id
           JOIN Citizen w ON mr.wife_id   = w.citizen_id
           WHERE mr.marriage_id = %s""",
        (marriage_id,), fetch='one')
    if not m: raise ValueError("Marriage registration not found")

    fields = [
        ("Husband",        m["husband_name"],                  "full"),
        ("Wife",           m["wife_name"],                     "full"),
        ("Marriage Date",  str(m["marriage_date"]),            "left"),
        ("Reg Date",       str(m["registration_date"]),        "right"),
        ("Certificate No", m["marriage_certificate_number"],   "full"),
    ]

    buf = BytesIO()
    c, pw, ph = _page_setup(buf)
    card_w, card_h = 172*mm, 95*mm
    cx = (pw - card_w) / 2
    cy = (ph - card_h) / 2 + 18*mm
    _draw_certificate(c, {}, cx, cy, card_w, card_h,
                      "MARRIAGE CERTIFICATE  •  GOVT. OF PAKISTAN", fields)
    _footer(c, pw, cy)
    _render(c)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════
#  7. PAYMENT SLIP
# ═══════════════════════════════════════════════════════════════════════════

def _draw_payment(c, data, x, y, w, h):
    _card_frame(c, x, y, w, h)
    header_h = _header_bar(c, x, y, w, h, "PAYMENT RECEIPT  •  CRIDA SERVICES")

    fx    = x + 6*mm
    col_w = w - 12*mm
    h_col = w / 2 - 10*mm
    c2x   = x + w / 2 + 2*mm
    rh    = 11*mm
    cur_y = y + h - header_h - 10*mm

    _field(c, "Transaction Ref", data.get("transaction_reference","-"), fx,  cur_y, col_w); cur_y -= rh
    _field(c, "Citizen Name",    data.get("citizen_name","-"),          fx,  cur_y, col_w); cur_y -= rh
    _field(c, "Service Type",    data.get("service_type","-"),          fx,  cur_y, h_col)
    _field(c, "Amount (PKR)",    data.get("amount","-"),                c2x, cur_y, h_col); cur_y -= rh
    _field(c, "Payment Method",  data.get("payment_method","-"),        fx,  cur_y, h_col)
    _field(c, "Status",          data.get("payment_status","-"),        c2x, cur_y, h_col); cur_y -= rh
    _field(c, "Date",            str(data.get("payment_date","-")),     fx,  cur_y, col_w)

    _bottom_bar(c, x, y, w)


def generate_payment_slip_pdf(payment_id):
    pt = execute_query(
        """SELECT pt.*, CONCAT(c.first_name,' ',c.last_name) AS citizen_name
           FROM Payment_Transaction pt
           JOIN Citizen c ON pt.citizen_id = c.citizen_id
           WHERE pt.payment_id = %s""",
        (payment_id,), fetch='one')
    if not pt: raise ValueError("Payment not found")

    buf = BytesIO()
    c, pw, ph = _page_setup(buf)
    card_w, card_h = 172*mm, 100*mm
    cx = (pw - card_w) / 2
    cy = (ph - card_h) / 2 + 18*mm
    _draw_payment(c, dict(pt), cx, cy, card_w, card_h)
    _footer(c, pw, cy)
    _render(c)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════
#  STANDALONE TEST  (python pdf.py)
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import os
    out = "/mnt/user-data/outputs"
    os.makedirs(out, exist_ok=True)

    def save(name, data):
        path = os.path.join(out, name)
        with open(path, "wb") as f:
            f.write(data)
        print(f"  saved → {path}")

    print("Generating test PDFs…")

    # ── CNIC ──
    from io import BytesIO as _BIO
    buf = _BIO()
    cv, pw, ph = _page_setup(buf)
    cw, ch = 172*mm, 110*mm
    cx2 = (pw - cw) / 2; cy2 = (ph - ch) / 2 + 18*mm
    _draw_cnic(cv, _auto_dates({
        "full_name":"First7 Last7","father_name":"Father Name",
        "gender":"Female","blood_group":"A+","marital_status":"Single",
        "country":"Pakistan","national_id_number":"3000000000007","dob":"1999-03-13",
    }), cx2, cy2, cw, ch)
    _footer(cv, pw, cy2); _render(cv)
    save("test_cnic.pdf", buf.getvalue())

    # ── Passport ──
    buf = _BIO(); cv, pw, ph = _page_setup(buf)
    _draw_passport(cv, _auto_dates({
        "surname":"Last7","given_names":"First7","gender":"Female",
        "national_id_number":"3000000000007","dob":"1999-03-13",
        "passport_number":"AB1234567","status":"Active",
    }), cx2, cy2, cw, ch)
    _footer(cv, pw, cy2); _render(cv)
    save("test_passport.pdf", buf.getvalue())

    # ── Driving License ──
    buf = _BIO(); cv, pw, ph = _page_setup(buf)
    _draw_license(cv, _auto_dates({
        "full_name":"First7 Last7","national_id_number":"3000000000007",
        "dob":"1999-03-13","license_number":"LHR-2020-77777",
        "license_type":"Class B","status":"Valid",
    }), cx2, cy2, 172*mm, 100*mm)
    _footer(cv, pw, cy2); _render(cv)
    save("test_license.pdf", buf.getvalue())

    # ── Payment Slip ──
    buf = _BIO(); cv, pw, ph = _page_setup(buf)
    _draw_payment(cv, {
        "transaction_reference":"TXN-2024-001","citizen_name":"First7 Last7",
        "service_type":"CNIC Renewal","amount":"500","payment_method":"Online",
        "payment_status":"Completed","payment_date":date.today(),
    }, cx2, cy2, 172*mm, 100*mm)
    _footer(cv, pw, cy2); _render(cv)
    save("test_payment.pdf", buf.getvalue())

    print("All done!")
