"""
Exhibit A - Detailed Scope of Work PDF Generator

Generates a professionally formatted PDF attachment for the MSA
containing the detailed scope of work selected by the client.
Uses Playwright (Chromium) for PDF generation - same as contract PDFs.
"""

import asyncio
import base64
import json
import os
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict


# Load service area and task definitions from JSON template file
def load_template_definitions():
    """Load service areas and tasks from the JSON template file"""
    template_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "cleanenroll_scope_of_work_templates.json"
    )

    service_areas = {}
    task_definitions = {}

    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            data = json.load(f)

            for template in data.get("templates", []):
                for area in template.get("serviceAreas", []):
                    area_id = area["name"].lower().replace(" ", "-").replace("/", "-")
                    service_areas[area_id] = {
                        "name": area["name"],
                        "icon": get_area_icon(area["name"]),
                    }

                    # Build task definitions for this area
                    if area_id not in task_definitions:
                        task_definitions[area_id] = {}

                    for task_label in area.get("tasks", []):
                        task_id = (
                            task_label.lower()
                            .replace(" ", "-")
                            .replace("/", "-")
                            .replace("(", "")
                            .replace(")", "")
                        )
                        task_definitions[area_id][task_id] = task_label

    return service_areas, task_definitions


def get_area_icon(area_name: str) -> str:
    """Get an appropriate icon for a service area"""
    area_lower = area_name.lower()

    icon_map = {
        "lobby": "🏢",
        "reception": "🏢",
        "workstation": "💼",
        "office": "💼",
        "conference": "📊",
        "meeting": "📊",
        "breakroom": "☕",
        "kitchenette": "☕",
        "kitchen": "🍳",
        "restroom": "🚻",
        "bathroom": "🚻",
        "sales": "🛍️",
        "retail": "🛍️",
        "fitting": "👔",
        "checkout": "💳",
        "pos": "💳",
        "stockroom": "📦",
        "storage": "📦",
        "warehouse": "📦",
        "dining": "🍽️",
        "cafeteria": "🍽️",
        "bar": "🍸",
        "grease": "🧴",
        "exam": "🏥",
        "medical": "🏥",
        "waiting": "🪑",
        "clinical": "🧪",
        "biohazard": "⚠️",
        "production": "🏭",
        "industrial": "🏭",
        "loading": "🚚",
        "dock": "🚚",
        "workout": "🏋️",
        "gym": "🏋️",
        "locker": "🚿",
        "classroom": "📚",
        "hallway": "🚶",
        "common": "🚶",
    }

    for key, icon in icon_map.items():
        if key in area_lower:
            return icon

    return "📋"


# Load definitions at module level
SERVICE_AREAS, TASK_DEFINITIONS = load_template_definitions()

COMPLIANCE_CLAUSE = """All cleaning services shall be performed in accordance with applicable OSHA (Occupational Safety and Health Administration) standards and CDC (Centers for Disease Control and Prevention) guidelines for commercial cleaning and disinfection. Service Provider shall use EPA-registered disinfectants and follow manufacturer instructions for proper application and contact time."""


async def html_to_pdf(html: str) -> bytes:
    """
    Convert HTML to PDF using Playwright via subprocess.
    Runs in a separate process to avoid asyncio conflicts on Windows.
    Same approach as contract PDF generation.
    """
    # Get the path to the pdf_worker script
    worker_path = os.path.join(os.path.dirname(__file__), "..", "pdf_worker.py")
    worker_path = os.path.abspath(worker_path)

    # Get the correct Python executable from the venv
    python_exe = sys.executable

    # Encode HTML as base64 to safely pass via stdin
    html_b64 = base64.b64encode(html.encode("utf-8")).decode("utf-8")

    def run_worker():
        # Run the worker script as a separate process
        try:
            result = subprocess.run(
                [python_exe, worker_path],
                input=html_b64,
                capture_output=True,
                text=True,
                timeout=120,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            if result.returncode != 0:
                raise Exception(f"PDF worker failed (exit {result.returncode}): {result.stderr}")

            # Decode the base64 PDF from stdout
            pdf_b64 = result.stdout.strip()
            if not pdf_b64:
                raise Exception("PDF worker returned empty output")
            return base64.b64decode(pdf_b64)
        except subprocess.TimeoutExpired as e:
            raise Exception("PDF generation timed out after 120 seconds") from e
        except Exception as e:
            raise Exception(f"PDF generation error: {str(e)}") from e

    # Run in thread pool to not block the event loop
    return await asyncio.to_thread(run_worker)


def generate_exhibit_a_html(
    scope_data: Dict[str, Any],
    client_name: str,
    business_name: str,
    contract_title: str,
) -> str:
    """
    Generate HTML for Exhibit A - Detailed Scope of Work

    Args:
        scope_data: Dictionary containing selectedTasks, consumablesResponsibility, specialNotes
        client_name: Name of the client
        business_name: Name of the service provider
        contract_title: Title of the main contract

    Returns:
        str: HTML content
    """
    selected_tasks = scope_data.get("selectedTasks", {})
    consumables = scope_data.get("consumablesResponsibility", "provider")
    special_notes = scope_data.get("specialNotes", "").strip()

    # Build task sections HTML
    task_sections_html = ""
    task_number = 1

    for area_id, task_ids in selected_tasks.items():
        if not task_ids:
            continue

        area_info = SERVICE_AREAS.get(area_id, {})
        area_name = area_info.get("name", area_id)

        # Build task list for this area
        tasks_html = ""
        for task_id in task_ids:
            task_label = TASK_DEFINITIONS.get(area_id, {}).get(task_id, task_id)
            tasks_html += f"<li>{task_label}</li>"

        task_sections_html += f"""
        <div class="task-section">
            <h4>2.{task_number} {area_name}</h4>
            <ul class="task-list">{tasks_html}</ul>
        </div>
        """
        task_number += 1

    # Build consumables section
    if consumables == "provider":
        consumables_html = f"""
        <p><strong>Service Provider Provides:</strong> {business_name} shall provide all cleaning supplies, 
        chemicals, equipment, and consumables necessary to perform the services outlined in this Exhibit A. 
        All products shall be commercial-grade and appropriate for the intended use.</p>
        """
    else:
        consumables_html = f"""
        <p><strong>Client Provides:</strong> {client_name} shall provide all cleaning supplies, chemicals, 
        equipment, and consumables necessary to perform the services outlined in this Exhibit A. The Service 
        Provider shall notify the Client in advance if any supplies are running low or need replenishment.</p>
        """

    # Build special notes section
    special_notes_html = ""
    if special_notes:
        special_notes_html = f"""
        <div class="section">
            <h3>5. SPECIAL INSTRUCTIONS</h3>
            <p style="white-space: pre-wrap;">{special_notes}</p>
        </div>
        """

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Exhibit A - Scope of Work</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }}
        body {{
            font-family: 'Poppins', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 10pt;
            line-height: 1.7;
            color: #0A2540;
            background: white;
            padding: 50px 60px;
        }}
        .title {{
            font-size: 22pt;
            font-weight: 600;
            color: #0A2540;
            text-align: center;
            margin-bottom: 10px;
        }}
        .subtitle {{
            font-size: 18pt;
            font-weight: 600;
            color: #0A2540;
            text-align: center;
            margin-bottom: 30px;
        }}
        .contract-info {{
            font-size: 10pt;
            color: #425466;
            margin-bottom: 30px;
            line-height: 1.8;
        }}
        .contract-info strong {{
            color: #0A2540;
        }}
        .section {{
            margin-bottom: 28px;
        }}
        h3 {{
            font-size: 11pt;
            font-weight: 600;
            color: #0A2540;
            margin-bottom: 12px;
        }}
        .section p {{
            color: #425466;
            font-size: 10pt;
            line-height: 1.8;
            margin-bottom: 12px;
        }}
        .task-section {{
            margin-bottom: 20px;
        }}
        .task-section h4 {{
            font-size: 10pt;
            font-weight: 600;
            color: #0A2540;
            margin-bottom: 8px;
        }}
        .task-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .task-list li {{
            padding: 4px 0;
            padding-left: 20px;
            position: relative;
            font-size: 10pt;
            color: #475569;
        }}
        .task-list li:before {{
            content: "•";
            color: #14b8a6;
            font-weight: bold;
            position: absolute;
            left: 0;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #E2E8F0;
            text-align: center;
            font-size: 9pt;
            color: #64748b;
            font-style: italic;
        }}
    </style>
</head>
<body>
    <div class="title">EXHIBIT A</div>
    <div class="subtitle">DETAILED SCOPE OF WORK</div>
    
    <div class="contract-info">
        <p><strong>Attached to:</strong> {contract_title}</p>
        <p><strong>Between:</strong> {business_name} (Service Provider) and {client_name} (Client)</p>
        <p><strong>Date:</strong> {datetime.now().strftime('%B %d, %Y')}</p>
    </div>
    
    <div class="section">
        <h3>1. SCOPE OF SERVICES</h3>
        <p>The Service Provider agrees to perform the following cleaning services at the Client's premises as 
        specified below. This Exhibit A forms an integral part of the Master Service Agreement and defines the 
        specific tasks to be performed.</p>
    </div>
    
    <div class="section">
        <h3>2. DETAILED TASK LIST</h3>
        {task_sections_html}
    </div>
    
    <div class="section">
        <h3>3. CLEANING SUPPLIES & CONSUMABLES</h3>
        {consumables_html}
    </div>
    
    <div class="section">
        <h3>4. CLEANING STANDARDS & COMPLIANCE</h3>
        <p>{COMPLIANCE_CLAUSE}</p>
    </div>
    
    {special_notes_html}
    
    <div class="footer">
        This Exhibit A is incorporated by reference into Section 2 (Scope of Services) of the Master Service 
        Agreement between the parties.
    </div>
</body>
</html>
    """

    return html


async def generate_exhibit_a_pdf(
    scope_data: Dict[str, Any],
    client_name: str,
    business_name: str,
    contract_title: str,
) -> bytes:
    """
    Generate Exhibit A - Detailed Scope of Work PDF

    Args:
        scope_data: Dictionary containing selectedTasks, consumablesResponsibility, specialNotes
        client_name: Name of the client
        business_name: Name of the service provider
        contract_title: Title of the main contract

    Returns:
        bytes: PDF file content
    """
    # Generate HTML
    html = generate_exhibit_a_html(scope_data, client_name, business_name, contract_title)

    # Convert to PDF using Playwright
    pdf_bytes = await html_to_pdf(html)

    return pdf_bytes
