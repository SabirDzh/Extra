import asyncio
import os
import subprocess
import shutil
import tempfile
from datetime import datetime
from core.config import BASE_DIR

def generate_certificate_pdf(
    full_name: str,
    course_title: str,
    certificate_number: str,
    issued_at: datetime,
) -> bytes:
    # 1. Load the template using Jinja2
    from jinja_templates import templates
    template = templates.env.get_template("certificate.html")
    
    issued_str = issued_at.strftime("%d.%m.%Y") if issued_at else ""
    
    # Render HTML content
    html_content = template.render(
        full_name=full_name,
        course_title=course_title,
        certificate_number=certificate_number,
        issued_at=issued_str,
    )
    
    # 2. Write to a temporary file
    temp_dir = tempfile.gettempdir()
    html_path = os.path.join(temp_dir, f"cert_{certificate_number}.html")
    pdf_path = os.path.join(temp_dir, f"cert_{certificate_number}.pdf")
    
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    try:
        # 3. Find Google Chrome executable
        chrome_path = None
        mac_chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(mac_chrome):
            chrome_path = mac_chrome
        else:
            for cmd in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"]:
                path = shutil.which(cmd)
                if path:
                    chrome_path = path
                    break
                    
        if not chrome_path:
            raise FileNotFoundError(
                "Google Chrome or Chromium executable not found. "
                "Please make sure Google Chrome is installed."
            )
            
        # Run Chrome headlessly to convert to PDF
        cmd = [
            chrome_path,
            "--headless",
            "--disable-gpu",
            f"--print-to-pdf={pdf_path}",
            html_path
        ]
        
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Read the generated PDF bytes
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
            
        return pdf_bytes
        
    finally:
        # Clean up temp files
        if os.path.exists(html_path):
            try:
                os.remove(html_path)
            except OSError:
                pass
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except OSError:
                pass


async def async_generate_certificate_pdf(
    full_name: str,
    course_title: str,
    certificate_number: str,
    issued_at: datetime,
) -> bytes:
    """Async wrapper around generate_certificate_pdf."""
    return await asyncio.to_thread(
        generate_certificate_pdf,
        full_name=full_name,
        course_title=course_title,
        certificate_number=certificate_number,
        issued_at=issued_at,
    )
