import io
import math
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

Arial = "Arial"
ArialBold = "ArialBold"

_COLORS = {
    "dark": (0.24, 0.31, 0.37),
    "red": (0.91, 0.26, 0.16),
    "text_gray": (0.55, 0.55, 0.55),
    "text_dark": (0.17, 0.24, 0.31),
    "line_gray": (0.75, 0.75, 0.75),
    "stamp_blue": (0.35, 0.55, 0.70),
    "white": (1, 1, 1),
}

_fonts_registered = False


def _register_fonts():
    global _fonts_registered
    if _fonts_registered:
        return
    pdfmetrics.registerFont(
        TTFont(Arial, "/System/Library/Fonts/Supplemental/Arial.ttf")
    )
    pdfmetrics.registerFont(
        TTFont(ArialBold, "/System/Library/Fonts/Supplemental/Arial Bold.ttf")
    )
    _fonts_registered = True


def _draw_top_shapes(cv: canvas.Canvas, w: float, h: float):
    c = _COLORS

    dark_pts = [
        (0, h),
        (w, h),
        (w, h * 0.78),
        (w * 0.35, h * 0.88),
        (0, h * 0.84),
    ]
    cv.setFillColorRGB(*c["dark"])
    p = cv.beginPath()
    p.moveTo(*dark_pts[0])
    for pt in dark_pts[1:]:
        p.lineTo(*pt)
    p.close()
    cv.drawPath(p, fill=1, stroke=0)

    red_pts = [
        (0, h),
        (w, h),
        (w, h * 0.82),
        (w * 0.4, h * 0.90),
        (0, h * 0.87),
    ]
    cv.setFillColorRGB(*c["red"])
    p = cv.beginPath()
    p.moveTo(*red_pts[0])
    for pt in red_pts[1:]:
        p.lineTo(*pt)
    p.close()
    cv.drawPath(p, fill=1, stroke=0)


def _draw_bottom_shapes(cv: canvas.Canvas, w: float, h: float):
    c = _COLORS

    dark_pts = [
        (0, 0),
        (w, 0),
        (w, h * 0.22),
        (w * 0.65, h * 0.12),
        (0, h * 0.16),
    ]
    cv.setFillColorRGB(*c["dark"])
    p = cv.beginPath()
    p.moveTo(*dark_pts[0])
    for pt in dark_pts[1:]:
        p.lineTo(*pt)
    p.close()
    cv.drawPath(p, fill=1, stroke=0)

    red_pts = [
        (0, 0),
        (w, 0),
        (w, h * 0.18),
        (w * 0.6, h * 0.10),
        (0, h * 0.13),
    ]
    cv.setFillColorRGB(*c["red"])
    p = cv.beginPath()
    p.moveTo(*red_pts[0])
    for pt in red_pts[1:]:
        p.lineTo(*pt)
    p.close()
    cv.drawPath(p, fill=1, stroke=0)


def _draw_stamp(cv: canvas.Canvas, cx: float, cy: float, radius: float):
    c = _COLORS

    cv.setStrokeColorRGB(*c["stamp_blue"])
    cv.setFillColorRGB(*c["white"])
    cv.setLineWidth(1.5)
    cv.circle(cx, cy, radius, fill=1, stroke=1)

    cv.setLineWidth(1)
    cv.circle(cx, cy, radius - 3 * mm, fill=0, stroke=1)

    cv.setFillColorRGB(*c["stamp_blue"])
    cv.setFont(ArialBold, 7)
    text = "ООО «АКВАКОНТРОЛЬ»"
    text_r = radius - 5 * mm
    n = len(text)
    start_angle = 135
    angle_span = 90
    for i, ch in enumerate(text):
        angle = start_angle + (i / max(n - 1, 1)) * angle_span
        rad = math.radians(angle)
        tx = cx + text_r * math.cos(rad)
        ty = cy + text_r * math.sin(rad)
        cv.saveState()
        cv.translate(tx, ty)
        cv.rotate(angle - 90)
        cv.drawCentredString(0, 0, ch)
        cv.restoreState()

    cv.setFont(Arial, 6)
    cv.setFillColorRGB(*c["stamp_blue"])
    cv.drawCentredString(cx, cy + 2 * mm, "ИНН 7728123456")
    cv.drawCentredString(cx, cy - 1 * mm, "КПП 772801001")
    cv.drawCentredString(cx, cy - 4 * mm, "ОГРН 1157746890123")

    cv.setFont(ArialBold, 8)
    cv.drawCentredString(cx, cy - 8 * mm, "МОСКВА")


def _wrap_text(cv: canvas.Canvas, text: str, font: str, size: float, max_width: float):
    cv.setFont(font, size)
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if cv.stringWidth(test, font, size) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def generate_certificate_pdf(
    full_name: str,
    course_title: str,
    certificate_number: str,
    issued_at: datetime,
) -> bytes:
    _register_fonts()

    buf = io.BytesIO()
    w, h = A4
    cv = canvas.Canvas(buf, pagesize=A4)

    _draw_top_shapes(cv, w, h)
    _draw_bottom_shapes(cv, w, h)

    c = _COLORS
    cx = w / 2
    margin = 30 * mm

    y_title = h * 0.76
    cv.setFont(ArialBold, 48)
    cv.setFillColorRGB(*c["text_gray"])
    cv.drawCentredString(cx, y_title, "СЕРТИФИКАТ")

    y_subtitle = y_title - 28
    cv.setFont(ArialBold, 22)
    cv.setFillColorRGB(*c["text_gray"])
    cv.drawCentredString(cx, y_subtitle, "МОНТАЖНИКА")

    y_line = y_subtitle - 22
    cv.setStrokeColorRGB(*c["line_gray"])
    cv.setLineWidth(0.5)
    cv.line(margin, y_line, w - margin, y_line)

    y_name = y_line - 32
    cv.setFont(ArialBold, 24)
    cv.setFillColorRGB(*c["text_dark"])
    name_width = cv.stringWidth(full_name, ArialBold, 24)
    max_name_w = w - 2 * margin
    if name_width > max_name_w:
        cv.setFont(ArialBold, 18)
    cv.drawCentredString(cx, y_name, full_name)

    y_lecture_label = y_name - 38
    cv.setFont(Arial, 13)
    cv.setFillColorRGB(*c["text_gray"])
    cv.drawCentredString(cx, y_lecture_label, "Прослушал(а) лекцию по теме:")

    y_course = y_lecture_label - 26
    lines = _wrap_text(cv, course_title, ArialBold, 16, w - 2 * margin - 20 * mm)
    for i, line in enumerate(lines):
        cv.setFont(ArialBold, 16)
        cv.setFillColorRGB(*c["text_dark"])
        cv.drawCentredString(cx, y_course - i * 22, line)

    y_cert_label = y_course - len(lines) * 22 - 35
    cv.setFont(Arial, 11)
    cv.setFillColorRGB(*c["text_gray"])
    cv.drawString(margin + 10 * mm, y_cert_label, "Сертификат выдан")

    stamp_cx = w - margin - 22 * mm
    stamp_cy = y_cert_label + 4 * mm
    _draw_stamp(cv, stamp_cx, stamp_cy, 18 * mm)

    y_logo_text = y_cert_label - 55
    cv.setFont(ArialBold, 36)
    cv.setFillColorRGB(*c["red"])
    cv.drawCentredString(cx, y_logo_text, "EXTRA®")

    y_brand = y_logo_text - 28
    brand_text = "АКВАКОНТРОЛЬ"
    cv.setFont(ArialBold, 22)
    brand_w = cv.stringWidth(brand_text, ArialBold, 22)
    box_pad_x = 12
    box_pad_y = 6
    box_x = cx - brand_w / 2 - box_pad_x
    box_y = y_brand - box_pad_y
    box_w = brand_w + 2 * box_pad_x
    box_h = 22 + 2 * box_pad_y

    cv.setStrokeColorRGB(*c["text_dark"])
    cv.setLineWidth(1.5)
    cv.setFillColorRGB(*c["white"])
    cv.roundRect(box_x, box_y, box_w, box_h, 10, fill=1, stroke=1)

    cv.setFont(ArialBold, 22)
    cv.setFillColorRGB(*c["text_dark"])
    cv.drawCentredString(cx, y_brand, brand_text)

    cv.save()
    buf.seek(0)
    return buf.read()
