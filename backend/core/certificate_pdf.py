import asyncio
from datetime import datetime

from core.config import settings
from jinja_templates import templates
from playwright.async_api import async_playwright


certificate_generation_semaphore = asyncio.Semaphore(
    settings.certificate.max_parallel_generations,
)


async def async_generate_certificate_pdf(
    full_name: str,
    course_title: str,
    certificate_number: str,
    issued_at: datetime,
) -> bytes:
    """Render a certificate PDF with bounded browser resources and execution time.

    Args:
        full_name: Recipient name shown on the certificate.
        course_title: Completed course title.
        certificate_number: Unique certificate identifier.
        issued_at: Certificate issue timestamp.

    Returns:
        Rendered PDF bytes.

    Raises:
        TimeoutError: If browser rendering exceeds the configured limit.
        playwright.async_api.Error: If the provisioned Chromium browser fails.
    """
    template = templates.env.get_template("certificate.html")
    issued_str = issued_at.strftime("%d.%m.%Y") if issued_at else ""

    html_content = template.render(
        full_name=full_name,
        course_title=course_title,
        certificate_number=certificate_number,
        issued_at=issued_str,
    )

    timeout_seconds = settings.certificate.render_timeout_seconds
    timeout_milliseconds = timeout_seconds * 1_000

    async with certificate_generation_semaphore:
        async with async_playwright() as playwright:
            async with asyncio.timeout(timeout_seconds):
                browser = await playwright.chromium.launch(headless=True)
                try:
                    page = await browser.new_page(
                        viewport={"width": 1200, "height": 1600},
                    )
                    await page.set_content(
                        html_content,
                        wait_until="networkidle",
                        timeout=timeout_milliseconds,
                    )
                    return await page.pdf(
                        format="A4",
                        print_background=True,
                        margin={
                            "top": "0mm",
                            "right": "0mm",
                            "bottom": "0mm",
                            "left": "0mm",
                        },
                    )
                finally:
                    await browser.close()
