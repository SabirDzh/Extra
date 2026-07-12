import asyncio
import io
import os
import threading
from datetime import datetime

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from core.config import BASE_DIR

Arial = "Arial"
ArialBold = "ArialBold"

_TEMPLATE_PATH = BASE_DIR / "media" / "certificate_template.pdf"

_COLORS = {
    "text_dark": (0.17, 0.24, 0.31),
    "text_gray": (0.55, 0.55, 0.55),
}

_fonts_registered = False
_fonts_lock = threading.Lock()


def _find_fonts():
    """Return (regular_path, bold_path) for the first available Cyrillic font family."""
    families = [
        # macOS
        (
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ),
        (
            "/Library/Fonts/Arial.ttf",
            "/Library/Fonts/Arial Bold.ttf",
        ),
        # Linux
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ),
        (
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ),
        (
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        ),
        (
            "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
            "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf",
        ),
        # Windows
        (
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ),
    ]
    for regular, bold in families:
        if regular and bold and os.path.exists(regular) and os.path.exists(bold):
            return regular, bold
    return None, None


def _register_fonts():
    global _fonts_registered
    if _fonts_registered:
        return

    with _fonts_lock:
        if _fonts_registered:
            return

        regular_path, bold_path = _find_fonts()
        if not regular_path or not bold_path:
            raise RuntimeError(
                "No suitable TTF font family found for certificate PDF generation. "
                "Please install DejaVu, Liberation, or Arial fonts."
            )

        pdfmetrics.registerFont(TTFont(Arial, regular_path))
        pdfmetrics.registerFont(TTFont(ArialBold, bold_path))
        _fonts_registered = True


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


def _create_overlay(
    full_name: str,
    course_title: str,
    certificate_number: str,
    issued_at: datetime,
) -> bytes:
    _register_fonts()

    buf = io.BytesIO()
    w, h = A4
    cv = canvas.Canvas(buf, pagesize=A4)

    margin = 30 * mm
    cx = w / 2

    # Full name (center, large)
    y_name = h * 0.66
    cv.setFont(ArialBold, 24)
    cv.setFillColorRGB(*_COLORS["text_dark"])
    name_width = cv.stringWidth(full_name, ArialBold, 24)
    if name_width > w - 2 * margin:
        cv.setFont(ArialBold, 18)
    cv.drawCentredString(cx, y_name, full_name)

    # Course title (center, below name)
    y_course_label = y_name - 38
    cv.setFont(Arial, 13)
    cv.setFillColorRGB(*_COLORS["text_gray"])
    cv.drawCentredString(cx, y_course_label, "Прослушал(а) лекцию по теме:")

    y_course = y_course_label - 26
    cv.setFont(ArialBold, 16)
    cv.setFillColorRGB(*_COLORS["text_dark"])
    lines = _wrap_text(cv, course_title, ArialBold, 16, w - 2 * margin - 20 * mm)
    for i, line in enumerate(lines):
        cv.drawCentredString(cx, y_course - i * 22, line)

    # Certificate number and issued date (bottom area)
    y_bottom = y_course - len(lines) * 22 - 50
    cv.setFont(Arial, 11)
    cv.setFillColorRGB(*_COLORS["text_gray"])
    date_str = issued_at.strftime("%d.%m.%Y") if issued_at else ""
    cv.drawCentredString(cx, y_bottom, f"Сертификат № {certificate_number}")
    cv.drawCentredString(cx, y_bottom - 18, f"Выдан: {date_str}")

    cv.save()
    buf.seek(0)
    return buf.read()


def generate_certificate_pdf(
    full_name: str,
    course_title: str,
    certificate_number: str,
    issued_at: datetime,
) -> bytes:
    if not _TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"Certificate template not found at {_TEMPLATE_PATH}. "
            "Please place the template PDF at this location."
        )

    overlay_bytes = _create_overlay(
        full_name=full_name,
        course_title=course_title,
        certificate_number=certificate_number,
        issued_at=issued_at,
    )

    template = PdfReader(str(_TEMPLATE_PATH))
    overlay = PdfReader(io.BytesIO(overlay_bytes))

    writer = PdfWriter()
    page = template.pages[0]
    page.merge_page(overlay.pages[0])
    writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out.read()


async def async_generate_certificate_pdf(
    full_name: str,
    course_title: str,
    certificate_number: str,
    issued_at: datetime,
) -> bytes:
    """Async wrapper around generate_certificate_pdf.

    PDF generation is CPU-bound and may block the event loop, so it is run in
    a separate thread.
    """
    return await asyncio.to_thread(
        generate_certificate_pdf,
        full_name=full_name,
        course_title=course_title,
        certificate_number=certificate_number,
        issued_at=issued_at,
    )
