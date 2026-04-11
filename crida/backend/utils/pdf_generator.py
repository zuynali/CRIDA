"""
pdf.py  –  CRIDA PDF generator (improved)
All functions return bytes, identical signatures to the original.
Changes:
  - CNIC / Passport / License: address row added
  - Birth / Death certificates: hospital name shown
  - Marriage certificate: now takes citizen_id; only shows the record where
    husband_id OR wife_id matches that citizen
  - Translucent Markhor SVG silhouette watermark in card background
"""

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white, Color
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
PK_DARK    = HexColor('#0B2F19')
TEXT_COLOR = HexColor('#0B2F19')
CARD_BG    = HexColor('#F7FBF6')
FIELD_LINE = HexColor('#A7C4A2')
LIGHT_GRAY = HexColor('#5F7B67')
PAGE_BG    = HexColor('#E8F2E7')
ACCENT     = HexColor('#72B084')
MID_GREEN  = HexColor('#3F704E')

# Translucent green for watermark
WATERMARK_COLOR = Color(0.06, 0.16, 0.08, alpha=0.08)   # very faint


# ═══════════════════════════════════════════════════════════════════════════
#  MARKHOR WATERMARK
# ═══════════════════════════════════════════════════════════════════════════

def _draw_markhor_watermark(c, cx, cy, size):
    """
    Draw a simplified Markhor silhouette as a translucent watermark.
    The markhor is Pakistan's national animal and appears on the CRIDA seal.
    Built from bezier curves to mimic the iconic spiral-horned mountain goat.
    cx, cy = centre of the watermark  |  size = overall height in points
    """
    c.saveState()
    c.setFillColor(WATERMARK_COLOR)
    c.setStrokeColor(WATERMARK_COLOR)
    c.setLineWidth(0)

    s = size / 120.0  # scale factor (design units = 120 pt tall)

    def T(x, y):           # translate + scale
        return cx + x * s, cy + y * s

    # ── Body ────────────────────────────────────────────────────────────────
    path = c.beginPath()
    # Rough quadruped body (elongated oval, slightly elevated rear)
    path.moveTo(*T(-30, 0))
    path.curveTo(*T(-38, 20), *T(-20, 38), *T(0, 38))
    path.curveTo(*T(22, 38),  *T(38, 22),  *T(35, 0))
    path.curveTo(*T(40, -8),  *T(34, -18), *T(22, -18))
    path.curveTo(*T(10, -18), *T(6, -10),  *T(0, -10))
    path.curveTo(*T(-6, -10), *T(-12, -18),*T(-22, -18))
    path.curveTo(*T(-35, -18),*T(-38, -10),*T(-30, 0))
    path.close()
    c.drawPath(path, stroke=0, fill=1)

    # ── Neck + Head ──────────────────────────────────────────────────────────
    path = c.beginPath()
    path.moveTo(*T(-2, 38))
    path.curveTo(*T(-4, 48),  *T(-8, 52),  *T(-10, 60))
    path.curveTo(*T(-12, 65), *T(-6, 68),  *T(0, 68))
    path.curveTo(*T(6, 68),   *T(10, 64),  *T(8, 58))
    path.curveTo(*T(6, 52),   *T(2, 48),   *T(2, 38))
    path.close()
    c.drawPath(path, stroke=0, fill=1)

    # ── Left spiral horn ────────────────────────────────────────────────────
    # Markhor's signature corkscrew horn going upward-left
    path = c.beginPath()
    path.moveTo(*T(-4, 68))
    path.curveTo(*T(-18, 72), *T(-28, 85), *T(-14, 92))
    path.curveTo(*T(-4, 96),  *T(4, 90),   *T(-2, 82))
    path.curveTo(*T(-6, 76),  *T(-16, 78), *T(-12, 86))
    path.curveTo(*T(-10, 90), *T(-6, 92),  *T(-4, 88))
    path.curveTo(*T(-2, 84),  *T(-8, 80),  *T(-10, 74))
    path.curveTo(*T(-14, 66), *T(-6, 65),  *T(-4, 68))
    path.close()
    c.drawPath(path, stroke=0, fill=1)

    # ── Right spiral horn ───────────────────────────────────────────────────
    path = c.beginPath()
    path.moveTo(*T(4, 68))
    path.curveTo(*T(18, 72),  *T(28, 85),  *T(14, 92))
    path.curveTo(*T(4, 96),   *T(-4, 90),  *T(2, 82))
    path.curveTo(*T(6, 76),   *T(16, 78),  *T(12, 86))
    path.curveTo(*T(10, 90),  *T(6, 92),   *T(4, 88))
    path.curveTo(*T(2, 84),   *T(8, 80),   *T(10, 74))
    path.curveTo(*T(14, 66),  *T(6, 65),   *T(4, 68))
    path.close()
    c.drawPath(path, stroke=0, fill=1)

    # ── Front legs ──────────────────────────────────────────────────────────
    for leg_x in (-18, -6):
        path = c.beginPath()
        path.moveTo(*T(leg_x, -18))
        path.curveTo(*T(leg_x - 2, -30), *T(leg_x - 2, -40), *T(leg_x, -48))
        path.lineTo(*T(leg_x + 4, -48))
        path.curveTo(*T(leg_x + 4, -40), *T(leg_x + 4, -30), *T(leg_x + 4, -18))
        path.close()
        c.drawPath(path, stroke=0, fill=1)

    # ── Back legs ───────────────────────────────────────────────────────────
    for leg_x in (10, 22):
        path = c.beginPath()
        path.moveTo(*T(leg_x, -18))
        path.curveTo(*T(leg_x - 2, -28), *T(leg_x + 4, -38), *T(leg_x + 2, -48))
        path.lineTo(*T(leg_x + 6, -48))
        path.curveTo(*T(leg_x + 8, -38), *T(leg_x + 6, -28), *T(leg_x + 4, -18))
        path.close()
        c.drawPath(path, stroke=0, fill=1)

    # ── Beard ────────────────────────────────────────────────────────────────
    path = c.beginPath()
    path.moveTo(*T(-2, 60))
    path.curveTo(*T(-6, 54),  *T(-6, 48),  *T(-2, 44))
    path.curveTo(*T(0, 46),   *T(0, 54),   *T(2, 60))
    path.close()
    c.drawPath(path, stroke=0, fill=1)

    # ── Tail ─────────────────────────────────────────────────────────────────
    path = c.beginPath()
    path.moveTo(*T(35, 10))
    path.curveTo(*T(42, 16),  *T(44, 24),  *T(40, 28))
    path.curveTo(*T(36, 26),  *T(36, 18),  *T(33, 12))
    path.close()
    c.drawPath(path, stroke=0, fill=1)

    c.restoreState()


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
    c.setFillColor(TEXT_COLOR)
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
    """White card background + green border + markhor watermark."""
    c.setFillColor(CARD_BG)
    c.roundRect(x, y, w, h, 8, stroke=0, fill=1)

    _draw_markhor_watermark(c, x + w * 0.7, y + h * 0.55, h * 0.8)

    c.setStrokeColor(PK_DARK)
    c.setLineWidth(1.5)
    c.roundRect(x, y, w, h, 8, stroke=1, fill=0)


def _header_bar(c, x, y, w, h, subtitle):
    """Pakistani green header bar with Pakistan flag + title."""
    header_h = h * 0.20
    c.setFillColor(PK_GREEN)
    c.rect(x, y + h - header_h, w, header_h, stroke=0, fill=1)
    c.setFillColor(ACCENT)
    c.rect(x, y + h - header_h - 1.5 * mm, w, 1.5 * mm, stroke=0, fill=1)

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
    """Green bottom bar with Principal General signature + CRIDA text."""
    bar_h = 10 * mm
    c.setFillColor(PK_GREEN)
    c.rect(x, y, w, bar_h, stroke=0, fill=1)

    c.setFont("Helvetica-Bold", 6)
    c.setFillColor(white)
    c.drawString(x + 4 * mm, y + 6 * mm, "Principal General")
    _signature(c, x + 4 * mm, y + 3.5 * mm)

    c.setFont("Helvetica", 5.5)
    c.setFillColor(ACCENT)
    c.drawCentredString(x + w / 2, y + 6 * mm, "CRIDA Official Document")
    c.setFont("Helvetica", 5)
    c.drawCentredString(x + w / 2, y + 3 * mm, "Issued by: Govt. of Pakistan")


def _footer(c, pw, card_y):
    c.setFont("Helvetica", 7)
    c.setFillColor(LIGHT_GRAY)
    c.drawCentredString(pw / 2, card_y - 12 * mm,
        f"CRIDA Official Document  |  Generated: {date.today()}  |  Page 1")


def _photo_placeholder(c, photo_x, photo_y, photo_w, photo_h, photo_path=None):
    c.setFillColor(HexColor('#DDE3EC'))
    c.rect(photo_x, photo_y, photo_w, photo_h, stroke=0, fill=1)
    c.setStrokeColor(HexColor('#AABBCC'))
    c.setLineWidth(0.5)
    c.rect(photo_x, photo_y, photo_w, photo_h, stroke=1, fill=0)

    if photo_path and os.path.exists(photo_path):
        try:
            c.drawImage(photo_path, photo_x, photo_y, width=photo_w, height=photo_h,
                        preserveAspectRatio=True, mask='auto')
            return
        except Exception:
            pass

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


def _format_address(row):
    """Build a compact address string from CitizenProfile_View columns."""
    parts = []
    if row.get("house_no"):   parts.append(row["house_no"])
    if row.get("street"):     parts.append(row["street"])
    if row.get("city"):       parts.append(row["city"])
    if row.get("province"):   parts.append(row["province"])
    if row.get("postal_code"):parts.append(row["postal_code"])
    return ", ".join(parts) if parts else "-"


def _render(c):
    """Save canvas and return bytes."""
    c.save()


# ═══════════════════════════════════════════════════════════════════════════
#  1. CNIC  (address row added)
# ═══════════════════════════════════════════════════════════════════════════

def _draw_cnic(c, data, x, y, w, h):
    _card_frame(c, x, y, w, h)
    header_h = _header_bar(c, x, y, w, h, "NATIONAL IDENTITY CARD  •  CNIC")

    photo_w, photo_h = 26*mm, 32*mm
    photo_x = x + w - photo_w - 6*mm
    photo_y = y + h - header_h - photo_h - 4*mm
    _photo_placeholder(c, photo_x, photo_y, photo_w, photo_h, data.get("photo_path"))

    bottom_bar_h = 10 * mm
    header_h_val = h * 0.18          # must match _header_bar ratio (we use 0.20 there — keep in sync)
    # Compute exact usable height and distribute evenly across 7 rows
    usable_h = h - (h * 0.20) - bottom_bar_h - 14 * mm   # 14 mm = top + bottom padding
    rh = usable_h / 7.0

    left_w  = photo_x - x - 12*mm
    fx      = x + 6*mm
    col_w   = w / 2 - 10*mm
    c2x     = x + w / 2 + 2*mm

    r1 = y + h - (h * 0.20) - 7*mm
    _field(c, "Name",           data.get("full_name", "-"),      fx,  r1,  left_w)
    r2 = r1 - rh
    _field(c, "Father Name",    data.get("father_name", "-"),    fx,  r2,  left_w)
    r3 = r2 - rh
    _field(c, "Gender",         data.get("gender", "-"),         fx,  r3,  col_w)
    _field(c, "Blood Group",    data.get("blood_group", "-"),    c2x, r3,  col_w)
    r4 = r3 - rh
    _field(c, "Marital Status", data.get("marital_status", "-"), fx,  r4,  col_w)
    _field(c, "Country Of Stay",data.get("country", "Pakistan"), c2x, r4,  col_w)
    r5 = r4 - rh
    addr = data.get("address", "-")
    if len(addr) > 60:
        addr = addr[:57] + "…"
    _field(c, "Address", addr, fx, r5, w - 12*mm)
    r6 = r5 - rh
    _field(c, "Identity Number", data.get("national_id_number", "-"), fx,  r6,  col_w)
    _field(c, "Date of Birth",   str(data.get("dob", "-")),           c2x, r6,  col_w)
    r7 = r6 - rh
    _field(c, "Date of Issue",   str(data.get("issue_date", "-")),    fx,  r7,  col_w)
    _field(c, "Date of Expiry",  str(data.get("expiry_date", "-")),   c2x, r7,  col_w)

    _bottom_bar(c, x, y, w)


def generate_cnic_pdf(citizen_id):
    row = execute_query(
        "SELECT * FROM CitizenProfile_View WHERE citizen_id=%s LIMIT 1",
        (citizen_id,), fetch='one')
    if not row: raise ValueError("Citizen not found")

    card = execute_query(
        "SELECT * FROM CNIC_Card WHERE citizen_id=%s ORDER BY card_id DESC LIMIT 1",
        (citizen_id,), fetch='one')

    # Father name via Family_Relationship
    father = execute_query(
        """SELECT CONCAT(c.first_name,' ',c.last_name) AS father_name
           FROM Family_Relationship fr
           JOIN Citizen c ON fr.related_citizen_id = c.citizen_id
           WHERE fr.citizen_id = %s AND fr.relationship_type = 'Father' LIMIT 1""",
        (citizen_id,), fetch='one')

    photo = execute_query(
        "SELECT file_path FROM Document WHERE citizen_id=%s AND document_type='photo' LIMIT 1",
        (citizen_id,), fetch='one')

    data = _auto_dates({
        "full_name":          row["full_name"],
        "father_name":        father["father_name"] if father else row.get("father_name", "-"),
        "gender":             row["gender"],
        "blood_group":        row.get("blood_group", "-"),
        "marital_status":     row["marital_status"],
        "country":            "Pakistan",
        "address":            _format_address(row),
        "national_id_number": row["national_id_number"],
        "dob":                row["dob"],
        "issue_date":         card["issue_date"]  if card else None,
        "expiry_date":        card["expiry_date"] if card else None,
        "photo_path":         photo["file_path"]  if photo else None,
    })

    buf = BytesIO()
    c, pw, ph = _page_setup(buf)
    card_w, card_h = 172*mm, 138*mm
    cx = (pw - card_w) / 2
    cy = (ph - card_h) / 2 + 18*mm
    _draw_cnic(c, data, cx, cy, card_w, card_h)
    _footer(c, pw, cy)
    _render(c)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════
#  2. PASSPORT  (address row added)
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
    rh     = (h - (h * 0.20) - 10*mm - 14*mm) / 7.0

    r1 = y + h - (h * 0.20) - 7*mm
    _field(c, "Surname",     data.get("surname", "-"),     fx,  r1, left_w)
    r2 = r1 - rh
    _field(c, "Given Names", data.get("given_names", "-"), fx,  r2, left_w)
    r3 = r2 - rh
    _field(c, "Nationality", "Pakistani",                  fx,  r3, col_w)
    _field(c, "Gender",      data.get("gender", "-"),      c2x, r3, col_w)
    r4 = r3 - rh
    _field(c, "National ID", data.get("national_id_number", "-"), fx,  r4, col_w)
    _field(c, "Date of Birth", str(data.get("dob", "-")),         c2x, r4, col_w)
    r5 = r4 - rh
    addr = data.get("address", "-")
    if len(addr) > 60: addr = addr[:57] + "…"
    _field(c, "Address", addr, fx, r5, w - 12*mm)
    r6 = r5 - rh
    _field(c, "Passport No",   data.get("passport_number", "-"),   fx,  r6, col_w)
    _field(c, "Date of Issue", str(data.get("issue_date", "-")),   c2x, r6, col_w)
    r7 = r6 - rh
    _field(c, "Date of Expiry", str(data.get("expiry_date", "-")), fx,  r7, col_w)
    _field(c, "Status",         data.get("status", "Valid"),       c2x, r7, col_w)

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
        "address":            _format_address(row),
        "passport_number":    p["passport_number"]              if p else "-",
        "issue_date":         p["issue_date"]                   if p else None,
        "expiry_date":        p["expiry_date"]                  if p else None,
        "status":             p.get("passport_status", "Valid") if p else "Valid",
        "photo_path":         photo["file_path"]                if photo else None,
    })

    buf = BytesIO()
    c, pw, ph = _page_setup(buf)
    card_w, card_h = 172*mm, 138*mm
    cx = (pw - card_w) / 2
    cy = (ph - card_h) / 2 + 18*mm
    _draw_passport(c, data, cx, cy, card_w, card_h)
    _footer(c, pw, cy)
    _render(c)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════
#  3. DRIVING LICENSE  (address row added)
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
    rh     = (h - (h * 0.20) - 10*mm - 14*mm) / 6.0

    r1 = y + h - (h * 0.20) - 7*mm
    _field(c, "Full Name",   data.get("full_name", "-"),          fx,  r1, left_w)
    r2 = r1 - rh
    _field(c, "National ID", data.get("national_id_number", "-"), fx,  r2, left_w)
    r3 = r2 - rh
    _field(c, "Date of Birth", str(data.get("dob", "-")),         fx,  r3, col_w)
    _field(c, "License Type",  data.get("license_type", "-"),     c2x, r3, col_w)
    r4 = r3 - rh
    addr = data.get("address", "-")
    if len(addr) > 60: addr = addr[:57] + "…"
    _field(c, "Address", addr, fx, r4, w - 12*mm)
    r5 = r4 - rh
    _field(c, "License Number", data.get("license_number", "-"),   fx,  r5, col_w)
    _field(c, "Date of Issue",  str(data.get("issue_date", "-")),  c2x, r5, col_w)
    r6 = r5 - rh
    _field(c, "Date of Expiry", str(data.get("expiry_date", "-")), fx,  r6, col_w)
    _field(c, "Status",         data.get("status", "Valid"),       c2x, r6, col_w)

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
        "address":            _format_address(row),
        "license_number":     lic["license_number"] if lic else "-",
        "license_type":       lic["license_type"]   if lic else "-",
        "issue_date":         lic["issue_date"]      if lic else None,
        "expiry_date":        lic["expiry_date"]     if lic else None,
        "status":             lic["status"]          if lic else "Valid",
        "photo_path":         photo["file_path"]     if photo else None,
    })

    buf = BytesIO()
    c, pw, ph = _page_setup(buf)
    card_w, card_h = 172*mm, 120*mm
    cx = (pw - card_w) / 2
    cy = (ph - card_h) / 2 + 18*mm
    _draw_license(c, data, cx, cy, card_w, card_h)
    _footer(c, pw, cy)
    _render(c)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════
#  GENERIC CERTIFICATE HELPER
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


# ═══════════════════════════════════════════════════════════════════════════
#  4. BIRTH CERTIFICATE  (hospital name added)
# ═══════════════════════════════════════════════════════════════════════════

def generate_birth_certificate_pdf(citizen_id):
    b = execute_query(
        """SELECT br.*, c.first_name, c.last_name, c.dob, c.gender,
                  h.name AS hospital_name, h.city AS hospital_city
           FROM Birth_Registration br
           JOIN Citizen c ON br.citizen_id = c.citizen_id
           LEFT JOIN Hospital h ON br.hospital_id = h.hospital_id
           WHERE br.citizen_id = %s LIMIT 1""",
        (citizen_id,), fetch='one')
    if not b: raise ValueError("Birth registration not found")

    hospital_display = "-"
    if b.get("hospital_name"):
        hospital_display = b["hospital_name"]
        if b.get("hospital_city"):
            hospital_display += f", {b['hospital_city']}"

    fields = [
        ("Child Name",      f"{b['first_name']} {b['last_name']}", "full"),
        ("Date of Birth",   str(b["dob"]),                         "left"),
        ("Gender",          b["gender"],                           "right"),
        ("Hospital / Place",hospital_display,                      "full"),
        ("Certificate No",  b["birth_certificate_number"] or "-",  "left"),
        ("Reg Date",        str(b["registration_date"]),           "right"),
    ]

    buf = BytesIO()
    c, pw, ph = _page_setup(buf)
    card_w, card_h = 172*mm, 105*mm
    cx = (pw - card_w) / 2
    cy = (ph - card_h) / 2 + 18*mm
    _draw_certificate(c, {}, cx, cy, card_w, card_h,
                      "BIRTH CERTIFICATE  •  GOVT. OF PAKISTAN", fields)
    _footer(c, pw, cy)
    _render(c)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════
#  5. DEATH CERTIFICATE  (hospital / place of death shown)
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
        ("Certificate No",  d["death_certificate_number"] or "-",  "right"),
        ("Cause of Death",  d.get("cause_of_death") or "-",        "full"),
        ("Place of Death",  d.get("place_of_death") or "-",        "full"),
    ]

    buf = BytesIO()
    c, pw, ph = _page_setup(buf)
    card_w, card_h = 172*mm, 100*mm
    cx = (pw - card_w) / 2
    cy = (ph - card_h) / 2 + 18*mm
    _draw_certificate(c, {}, cx, cy, card_w, card_h,
                      "DEATH CERTIFICATE  •  GOVT. OF PAKISTAN", fields)
    _footer(c, pw, cy)
    _render(c)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════
#  6. MARRIAGE CERTIFICATE
#     Takes citizen_id — finds the record where THIS citizen is husband OR wife
# ═══════════════════════════════════════════════════════════════════════════

def generate_marriage_certificate_pdf(citizen_id):
    """
    Generate the marriage certificate for a given citizen.
    Looks up the most recent Marriage_Registration where the citizen is
    either the husband or the wife, matching the schema constraints
    (husband must be Male, wife must be Female).
    """
    m = execute_query(
        """SELECT mr.*,
                  CONCAT(h.first_name,' ',h.last_name) AS husband_name,
                  CONCAT(w.first_name,' ',w.last_name) AS wife_name
           FROM Marriage_Registration mr
           JOIN Citizen h ON mr.husband_id = h.citizen_id
           JOIN Citizen w ON mr.wife_id   = w.citizen_id
           WHERE mr.husband_id = %s OR mr.wife_id = %s
           ORDER BY mr.marriage_id DESC
           LIMIT 1""",
        (citizen_id, citizen_id), fetch='one')
    if not m: raise ValueError(f"No marriage registration found for citizen {citizen_id}")

    fields = [
        ("Husband",        m["husband_name"],                        "full"),
        ("Wife",           m["wife_name"],                           "full"),
        ("Marriage Date",  str(m["marriage_date"]),                  "left"),
        ("Reg Date",       str(m["registration_date"]),              "right"),
        ("Certificate No", m["marriage_certificate_number"] or "-",  "full"),
    ]

    buf = BytesIO()
    c, pw, ph = _page_setup(buf)
    card_w, card_h = 172*mm, 100*mm
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

    _field(c, "Transaction Ref", data.get("transaction_reference", "-"), fx,  cur_y, col_w); cur_y -= rh
    _field(c, "Citizen Name",    data.get("citizen_name", "-"),          fx,  cur_y, col_w); cur_y -= rh
    _field(c, "Service Type",    data.get("service_type", "-"),          fx,  cur_y, h_col)
    _field(c, "Amount (PKR)",    data.get("amount", "-"),                c2x, cur_y, h_col); cur_y -= rh
    _field(c, "Payment Method",  data.get("payment_method", "-"),        fx,  cur_y, h_col)
    _field(c, "Status",          data.get("payment_status", "-"),        c2x, cur_y, h_col); cur_y -= rh
    _field(c, "Date",            str(data.get("payment_date", "-")),     fx,  cur_y, col_w)

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


def generate_placeholder_pdf(message="Document not available"):
    buf = BytesIO()
    c, pw, ph = _page_setup(buf)
    c.setFont("Helvetica-Bold", 24)
    c.setFillColor(PK_GREEN)
    c.drawCentredString(pw/2, ph/2 + 50, "CRIDA Document")
    c.setFont("Helvetica", 16)
    c.setFillColor(TEXT_COLOR)
    c.drawCentredString(pw/2, ph/2, message)
    c.setFont("Helvetica", 12)
    c.setFillColor(LIGHT_GRAY)
    c.drawCentredString(pw/2, ph/2 - 30, "Please contact your nearest CRIDA office for assistance.")
    _footer(c, pw, ph/2 - 100)
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

    from io import BytesIO as _BIO

    SAMPLE_ADDRESS = "House 12, Street 4, Model Town, Lahore, Punjab 54000"

    # ── CNIC ──
    buf = _BIO(); cv, pw, ph = _page_setup(buf)
    cw, ch = 172*mm, 138*mm
    cx2 = (pw - cw) / 2; cy2 = (ph - ch) / 2 + 18*mm
    _draw_cnic(cv, _auto_dates({
        "full_name":          "First7 Last7",
        "father_name":        "Father Name",
        "gender":             "Female",
        "blood_group":        "A+",
        "marital_status":     "Single",
        "country":            "Pakistan",
        "address":            SAMPLE_ADDRESS,
        "national_id_number": "3000000000007",
        "dob":                "1999-03-13",
    }), cx2, cy2, cw, ch)
    _footer(cv, pw, cy2); _render(cv)
    save("test_cnic.pdf", buf.getvalue())

    # ── Passport ──
    buf = _BIO(); cv, pw, ph = _page_setup(buf)
    _draw_passport(cv, _auto_dates({
        "surname":            "Last7",
        "given_names":        "First7",
        "gender":             "Female",
        "national_id_number": "3000000000007",
        "dob":                "1999-03-13",
        "address":            SAMPLE_ADDRESS,
        "passport_number":    "AB1234567",
        "status":             "Valid",
    }), cx2, cy2, cw, ch)
    _footer(cv, pw, cy2); _render(cv)
    save("test_passport.pdf", buf.getvalue())

    # ── Driving License ──
    buf = _BIO(); cv, pw, ph = _page_setup(buf)
    _draw_license(cv, _auto_dates({
        "full_name":          "First7 Last7",
        "national_id_number": "3000000000007",
        "dob":                "1999-03-13",
        "address":            SAMPLE_ADDRESS,
        "license_number":     "LHR-2020-77777",
        "license_type":       "Car",
        "status":             "Valid",
    }), cx2, cy2, 172*mm, 120*mm)
    _footer(cv, pw, cy2); _render(cv)
    save("test_license.pdf", buf.getvalue())

    # ── Birth Certificate ──
    buf = _BIO(); cv, pw, ph = _page_setup(buf)
    _draw_certificate(cv, {}, cx2, cy2, 172*mm, 105*mm,
        "BIRTH CERTIFICATE  •  GOVT. OF PAKISTAN", [
            ("Child Name",      "First7 Last7",           "full"),
            ("Date of Birth",   "1999-03-13",             "left"),
            ("Gender",          "Female",                 "right"),
            ("Hospital / Place","Services Hospital, Lahore","full"),
            ("Certificate No",  "BC-2024-0007",           "left"),
            ("Reg Date",        str(date.today()),         "right"),
        ])
    _footer(cv, pw, cy2); _render(cv)
    save("test_birth_cert.pdf", buf.getvalue())

    # ── Death Certificate ──
    buf = _BIO(); cv, pw, ph = _page_setup(buf)
    _draw_certificate(cv, {}, cx2, cy2, 172*mm, 100*mm,
        "DEATH CERTIFICATE  •  GOVT. OF PAKISTAN", [
            ("Deceased Name",  "First7 Last7",           "full"),
            ("Date of Death",  "2024-01-01",             "left"),
            ("Certificate No", "DC-2024-0001",           "right"),
            ("Cause of Death", "Natural Causes",         "full"),
            ("Place of Death", "Services Hospital, Lahore","full"),
        ])
    _footer(cv, pw, cy2); _render(cv)
    save("test_death_cert.pdf", buf.getvalue())

    # ── Marriage Certificate ──
    buf = _BIO(); cv, pw, ph = _page_setup(buf)
    _draw_certificate(cv, {}, cx2, cy2, 172*mm, 100*mm,
        "MARRIAGE CERTIFICATE  •  GOVT. OF PAKISTAN", [
            ("Husband",        "Husband Name",           "full"),
            ("Wife",           "First7 Last7",           "full"),
            ("Marriage Date",  "2023-06-15",             "left"),
            ("Reg Date",       str(date.today()),         "right"),
            ("Certificate No", "MC-2023-0007",           "full"),
        ])
    _footer(cv, pw, cy2); _render(cv)
    save("test_marriage_cert.pdf", buf.getvalue())

    # ── Payment Slip ──
    buf = _BIO(); cv, pw, ph = _page_setup(buf)
    _draw_payment(cv, {
        "transaction_reference": "TXN-2024-001",
        "citizen_name":          "First7 Last7",
        "service_type":          "CNIC Renewal",
        "amount":                "500",
        "payment_method":        "Online",
        "payment_status":        "Completed",
        "payment_date":          date.today(),
    }, cx2, cy2, 172*mm, 100*mm)
    _footer(cv, pw, cy2); _render(cv)
    save("test_payment.pdf", buf.getvalue())

    print("All done!")