"""
Exhibit A - Detailed Scope of Work PDF Generator

Generates a professionally formatted PDF attachment for the MSA
containing the detailed scope of work selected by the client.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)
from reportlab.lib import colors
from io import BytesIO
from datetime import datetime
from typing import Dict, List, Any

# Service area definitions (matching frontend)
SERVICE_AREAS = {
    "dining-area": {"name": "Dining Area", "icon": "🍽️"},
    "kitchen": {"name": "Kitchen", "icon": "🍳"},
    "restrooms": {"name": "Restrooms", "icon": "🚻"},
    "offices": {"name": "Offices", "icon": "💼"},
    "floors": {"name": "Floors", "icon": "🧹"},
    "windows": {"name": "Windows", "icon": "🪟"},
    "trash-recycling": {"name": "Trash & Recycling", "icon": "♻️"},
    "high-touch": {"name": "High-Touch Surfaces", "icon": "🤚"},
}

# Task definitions (matching frontend)
TASK_DEFINITIONS = {
    "dining-area": {
        "wipe-tables": "Wipe down all tables and chairs",
        "sanitize-surfaces": "Sanitize high-touch surfaces",
        "vacuum-carpet": "Vacuum carpeted areas",
        "mop-floors": "Mop hard floor surfaces",
        "empty-trash": "Empty trash receptacles",
        "clean-light-fixtures": "Dust light fixtures and ceiling fans",
    },
    "kitchen": {
        "clean-countertops": "Clean and sanitize all countertops",
        "clean-appliances": "Clean exterior of appliances",
        "clean-sink": "Clean and sanitize sink and faucet",
        "clean-microwave": "Clean microwave interior and exterior",
        "clean-refrigerator": "Clean refrigerator exterior and handles",
        "mop-floor": "Sweep and mop floor",
        "empty-trash": "Empty trash and replace liners",
        "wipe-cabinets": "Wipe down cabinet fronts",
    },
    "restrooms": {
        "clean-toilets": "Clean and disinfect toilets",
        "clean-sinks": "Clean and disinfect sinks and faucets",
        "clean-mirrors": "Clean mirrors and glass surfaces",
        "refill-supplies": "Refill soap, paper towels, and toilet paper",
        "mop-floors": "Sweep and mop floors with disinfectant",
        "empty-trash": "Empty trash receptacles and replace liners",
        "sanitize-touchpoints": "Sanitize door handles and light switches",
        "clean-partitions": "Wipe down stall partitions",
    },
    "offices": {
        "dust-surfaces": "Dust all horizontal surfaces",
        "vacuum-carpet": "Vacuum carpeted areas",
        "mop-floors": "Mop hard floor surfaces",
        "empty-trash": "Empty trash and recycling bins",
        "clean-desks": "Wipe down desks and work surfaces",
        "sanitize-phones": "Sanitize phones and keyboards",
        "clean-windows": "Clean interior window sills",
    },
    "floors": {
        "vacuum-all": "Vacuum all carpeted areas",
        "sweep-hard": "Sweep all hard floor surfaces",
        "mop-hard": "Mop all hard floor surfaces",
        "spot-clean": "Spot clean stains and spills",
        "edge-cleaning": "Edge cleaning along baseboards",
        "floor-buffing": "Buff and polish hard floors (periodic)",
    },
    "windows": {
        "interior-windows": "Clean interior window glass",
        "window-sills": "Wipe down window sills and frames",
        "exterior-windows": "Clean exterior window glass (ground level)",
        "glass-doors": "Clean glass doors and partitions",
    },
    "trash-recycling": {
        "empty-all-bins": "Empty all trash receptacles",
        "replace-liners": "Replace trash can liners",
        "empty-recycling": "Empty recycling bins",
        "take-to-dumpster": "Transport waste to designated disposal area",
        "clean-bins": "Clean and sanitize waste receptacles (periodic)",
    },
    "high-touch": {
        "door-handles": "Sanitize all door handles and knobs",
        "light-switches": "Sanitize light switches",
        "handrails": "Sanitize handrails and banisters",
        "elevator-buttons": "Sanitize elevator buttons",
        "reception-desk": "Sanitize reception desk and counters",
        "shared-equipment": "Sanitize shared equipment (copiers, printers)",
    },
}

COMPLIANCE_CLAUSE = """All cleaning services shall be performed in accordance with applicable OSHA (Occupational Safety and Health Administration) standards and CDC (Centers for Disease Control and Prevention) guidelines for commercial cleaning and disinfection. Service Provider shall use EPA-registered disinfectants and follow manufacturer instructions for proper application and contact time."""


def generate_exhibit_a_pdf(
    scope_data: Dict[str, Any],
    client_name: str,
    business_name: str,
    contract_title: str,
) -> BytesIO:
    """
    Generate Exhibit A - Detailed Scope of Work PDF

    Args:
        scope_data: Dictionary containing selectedTasks, consumablesResponsibility, specialNotes
        client_name: Name of the client
        business_name: Name of the service provider
        contract_title: Title of the main contract

    Returns:
        BytesIO: PDF file in memory
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    )

    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor("#14b8a6"),
        spaceAfter=10,
        spaceBefore=15,
        fontName="Helvetica-Bold",
    )

    body_style = ParagraphStyle(
        "CustomBody",
        parent=styles["BodyText"],
        fontSize=10,
        textColor=colors.HexColor("#334155"),
        spaceAfter=8,
        alignment=TA_JUSTIFY,
        leading=14,
    )

    # Build document
    story = []

    # Title
    story.append(Paragraph("EXHIBIT A", title_style))
    story.append(Paragraph("DETAILED SCOPE OF WORK", title_style))
    story.append(Spacer(1, 0.3 * inch))

    # Contract reference
    story.append(
        Paragraph(
            f"<b>Attached to:</b> {contract_title}",
            body_style,
        )
    )
    story.append(
        Paragraph(
            f"<b>Between:</b> {business_name} (Service Provider) and {client_name} (Client)",
            body_style,
        )
    )
    story.append(
        Paragraph(
            f"<b>Date:</b> {datetime.now().strftime('%B %d, %Y')}",
            body_style,
        )
    )
    story.append(Spacer(1, 0.3 * inch))

    # Introduction
    story.append(Paragraph("1. SCOPE OF SERVICES", heading_style))
    story.append(
        Paragraph(
            "The Service Provider agrees to perform the following cleaning services at the Client's premises as specified below. This Exhibit A forms an integral part of the Master Service Agreement and defines the specific tasks to be performed.",
            body_style,
        )
    )
    story.append(Spacer(1, 0.2 * inch))

    # Service areas and tasks
    story.append(Paragraph("2. DETAILED TASK LIST", heading_style))

    selected_tasks = scope_data.get("selectedTasks", {})
    task_number = 1

    for area_id, task_ids in selected_tasks.items():
        if not task_ids:
            continue

        area_info = SERVICE_AREAS.get(area_id, {})
        area_name = area_info.get("name", area_id)

        # Area header
        story.append(Spacer(1, 0.15 * inch))
        story.append(
            Paragraph(
                f"<b>2.{task_number} {area_name}</b>",
                ParagraphStyle(
                    "AreaHeader",
                    parent=body_style,
                    fontSize=11,
                    textColor=colors.HexColor("#0f172a"),
                    fontName="Helvetica-Bold",
                ),
            )
        )

        # Tasks for this area
        task_data = []
        for task_id in task_ids:
            task_label = TASK_DEFINITIONS.get(area_id, {}).get(task_id, task_id)
            task_data.append(["•", task_label])

        if task_data:
            task_table = Table(task_data, colWidths=[0.3 * inch, 6 * inch])
            task_table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 0), (-1, -1), 10),
                        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#475569")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (0, -1), 0),
                        ("LEFTPADDING", (1, 0), (1, -1), 5),
                    ]
                )
            )
            story.append(task_table)

        task_number += 1

    # Consumables responsibility
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("3. CLEANING SUPPLIES & CONSUMABLES", heading_style))

    consumables = scope_data.get("consumablesResponsibility", "provider")
    if consumables == "provider":
        consumables_text = f"<b>Service Provider Provides:</b> {business_name} shall provide all cleaning supplies, chemicals, equipment, and consumables necessary to perform the services outlined in this Exhibit A. All products shall be commercial-grade and appropriate for the intended use."
    else:
        consumables_text = f"<b>Client Provides:</b> {client_name} shall provide all cleaning supplies, chemicals, equipment, and consumables necessary to perform the services outlined in this Exhibit A. The Service Provider shall notify the Client in advance if any supplies are running low or need replenishment."

    story.append(Paragraph(consumables_text, body_style))

    # Compliance clause
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("4. CLEANING STANDARDS & COMPLIANCE", heading_style))
    story.append(Paragraph(COMPLIANCE_CLAUSE, body_style))

    # Special notes
    special_notes = scope_data.get("specialNotes", "").strip()
    if special_notes:
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph("5. SPECIAL INSTRUCTIONS", heading_style))
        story.append(Paragraph(special_notes, body_style))

    # Footer
    story.append(Spacer(1, 0.3 * inch))
    story.append(
        Paragraph(
            "<i>This Exhibit A is incorporated by reference into Section 2 (Scope of Services) of the Master Service Agreement between the parties.</i>",
            ParagraphStyle(
                "Footer",
                parent=body_style,
                fontSize=9,
                textColor=colors.HexColor("#64748b"),
                alignment=TA_CENTER,
            ),
        )
    )

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer
