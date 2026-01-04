import asyncio
from playwright.sync_api import sync_playwright

def _sync_html_to_pdf(html: str) -> bytes:
    """Synchronous HTML to PDF conversion using Playwright"""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        pdf = page.pdf(
            format="A4",
            margin={"top": "20px", "bottom": "20px", "left": "20px", "right": "20px"},
            print_background=True
        )
        browser.close()
        return pdf

async def html_to_pdf(html: str) -> bytes:
    """Convert HTML to PDF using Playwright - runs sync API in thread pool"""
    return await asyncio.to_thread(_sync_html_to_pdf, html)

async def main():
    html = "<html><body><h1>Test Contract</h1><p>This is a test.</p></body></html>"
    pdf = await html_to_pdf(html)
    print(f"PDF generated successfully: {len(pdf)} bytes")

if __name__ == "__main__":
    asyncio.run(main())
