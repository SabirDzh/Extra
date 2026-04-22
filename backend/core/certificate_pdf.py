import io
from datetime import datetime

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas


def generate_certificate_pdf(
    full_name: str,
    course_title: str,
    certificate_number: str,
    issued_at: datetime,
) -> bytes:
    buf = io.BytesIO()
    width, height = landscape(A4)
    c = canvas.Canvas(buf, pagesize=landscape(A4))


    c.setStrokeColorRGB(0.2, 0.4, 0.7)
    c.setLineWidth(4)
    c.rect(1.5 * cm, 1.5 * cm, width - 3 * cm, height - 3 * cm)


    c.setFont("Helvetica-Bold", 36)
    c.setFillColorRGB(0.2, 0.3, 0.6)
    c.drawCentredString(width / 2, height - 4 * cm, "Certificate of Completion")


    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.setLineWidth(1)
    c.line(6 * cm, height - 5 * cm, width - 6 * cm, height - 5 * cm)


    c.setFont("Helvetica", 16)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawCentredString(width / 2, height - 7 * cm, "This certifies that")

    c.setFont("Helvetica-Bold", 28)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.drawCentredString(width / 2, height - 9 * cm, full_name)

    c.setFont("Helvetica", 16)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawCentredString(
        width / 2, height - 11 * cm, "has successfully completed the course"
    )

    c.setFont("Helvetica-Bold", 22)
    c.setFillColorRGB(0.2, 0.4, 0.7)
    c.drawCentredString(width / 2, height - 13 * cm, course_title)


    c.setFont("Helvetica", 11)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    date_str = issued_at.strftime("%B %d, %Y")
    c.drawCentredString(width / 2, 4 * cm, f"Date: {date_str}")
    c.drawCentredString(width / 2, 3 * cm, f"Certificate No: {certificate_number}")

    c.save()
    buf.seek(0)
    return buf.read()
