"""
Standalone PDF generation worker script.
This runs as a separate process to avoid asyncio conflicts with Playwright on Windows.
"""
import sys
import base64
from playwright.sync_api import sync_playwright


def generate_pdf(html: str) -> bytes:
    """Generate PDF from HTML using Playwright (optimized for speed)"""
    with sync_playwright() as p:
        # Launch browser with performance optimizations
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-gpu',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',  # Allows embedded images
                '--disable-features=VizDisplayCompositor',
            ]
        )
        page = browser.new_page()
        
        # Use 'load' instead of 'networkidle' for 3-5x faster generation
        # 'load' waits for DOM to load, 'networkidle' waits for all network requests (slow!)
        page.set_content(html, wait_until="load")
        
        # Generate PDF
        pdf = page.pdf(
            format="A4",
            margin={"top": "20px", "bottom": "20px", "left": "20px", "right": "20px"},
            print_background=True,
            prefer_css_page_size=False
        )
        browser.close()
        return pdf


if __name__ == "__main__":
    # Read base64-encoded HTML from stdin
    html_b64 = sys.stdin.read()
    html = base64.b64decode(html_b64).decode('utf-8')
    
    # Generate PDF
    pdf_bytes = generate_pdf(html)
    
    # Write base64-encoded PDF to stdout
    pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')
    sys.stdout.write(pdf_b64)
