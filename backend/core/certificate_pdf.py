import asyncio
from datetime import datetime
from jinja_templates import templates
from playwright.async_api import async_playwright


async def async_generate_certificate_pdf(
    full_name: str,
    course_title: str,
    certificate_number: str,
    issued_at: datetime,
) -> bytes:
    """Generates PDF bytes for a certificate from Jinja2 template using Playwright (Chromium)."""
    template = templates.env.get_template("certificate.html")
    issued_str = issued_at.strftime("%d.%m.%Y") if issued_at else ""

    html_content = template.render(
        full_name=full_name,
        course_title=course_title,
        certificate_number=certificate_number,
        issued_at=issued_str,
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1200, "height": 1600})
        await page.set_content(html_content, wait_until="networkidle")
        pdf_bytes = await page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"},
        )
        await browser.close()
        return pdf_bytes


def generate_certificate_pdf(
    full_name: str,
    course_title: str,
    certificate_number: str,
    issued_at: datetime,
) -> bytes:
    """Sync wrapper for async_generate_certificate_pdf."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(
            async_generate_certificate_pdf(
                full_name=full_name,
                course_title=course_title,
                certificate_number=certificate_number,
                issued_at=issued_at,
            )
        )
    return asyncio.run(
        async_generate_certificate_pdf(
            full_name=full_name,
            course_title=course_title,
            certificate_number=certificate_number,
            issued_at=issued_at,
        )
    )
