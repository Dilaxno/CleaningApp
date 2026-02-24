"""
Scope of Work PDF Generator
Generates professional, branded Exhibit A style PDFs with frequency column
"""

import hashlib
import io
import logging
import os
from datetime import datetime
from typing import Optional

import boto3
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from ..models import BusinessConfig, Client, ScopeProposal, User

logger = logging.getLogger(__name__)

# R2 Configuration
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL")


def get_r2_client():
    """Get R2 client"""
    return boto3.client(
        "s3",
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def upload_scope_pdf_to_r2(
    pdf_bytes: bytes, user_firebase_uid: str, proposal_public_id: str
) -> str:
    """Upload scope PDF to R2 and return the key"""
    key = f"scope-proposals/{user_firebase_uid}/{proposal_public_id}.pdf"

    r2 = get_r2_client()
    r2.put_object(
        Bucket=R2_BUCKET_NAME,
        Key=key,
        Body=pdf_bytes,
        ContentType="application/pdf",
    )

    logger.info(f"✅ Uploaded scope PDF to R2: {key}")
    return key


class ScopePDFGenerator:
    """Generate professional scope of work PDFs"""

    def __init__(self, proposal: ScopeProposal, db: Session):
        self.proposal = proposal
        self.db = db

        # Get related data
        self.user = db.query(User).filter(User.id == proposal.user_id).first()
        self.client = db.query(Client).filter(Client.id == proposal.client_id).first()
        self.business_config = (
            db.query(BusinessConfig).filter(BusinessConfig.user_id == proposal.user_id).first()
        )

        # PDF settings
        self.page_width, self.page_height = letter
        self.margin = 0.75 * inch
        self.content_width = self.page_width - (2 * self.margin)

        # Brand color (teal)
        self.brand_color = colors.HexColor("#14b8a6")
        self.dark_gray = colors.HexColor("#1e293b")
        self.light_gray = colors.HexColor("#f1f5f9")

    def generate(self) -> bytes:
        """Generate PDF and return bytes"""
        logger.info(f"📄 Generating scope PDF for proposal {self.proposal.id}")

        # Create PDF buffer
        buffer = io.BytesIO()

        # Create document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=self.margin,
            leftMargin=self.margin,
            topMargin=self.margin,
            bottomMargin=self.margin,
            title=f"Scope of Work - {self.client.business_name}",
        )

        # Build content
        story = []
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=24,
            textColor=self.brand_color,
            spaceAfter=12,
            alignment=1,  # Center
        )

        heading_style = ParagraphStyle(
            "CustomHeading",
            parent=styles["Heading2"],
            fontSize=16,
            textColor=self.dark_gray,
            spaceAfter=10,
            spaceBefore=20,
        )

        body_style = ParagraphStyle(
            "CustomBody",
            parent=styles["Normal"],
            fontSize=10,
            textColor=self.dark_gray,
            spaceAfter=6,
        )

        # Header Section
        story.append(Paragraph("SCOPE OF WORK", title_style))
        story.append(Paragraph("Exhibit A", body_style))
        story.append(Spacer(1, 0.3 * inch))

        # Company and Client Info
        info_data = [
            ["Company:", self.business_config.business_name or self.user.full_name],
            ["Client:", self.client.business_name],
            ["Contact:", self.client.contact_name or "N/A"],
            ["Property Address:", self._format_address()],
            ["Version:", self.proposal.version],
            ["Date:", datetime.utcnow().strftime("%B %d, %Y")],
        ]

        info_table = Table(info_data, colWidths=[1.5 * inch, 4.5 * inch])
        info_table.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 10),
                    ("FONT", (1, 0), (1, -1), "Helvetica", 10),
                    ("TEXTCOLOR", (0, 0), (-1, -1), self.dark_gray),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(info_table)
        story.append(Spacer(1, 0.4 * inch))

        # Scope of Work Content
        story.append(Paragraph("SCOPE OF WORK", heading_style))

        # Service Areas and Tasks
        scope_data = self.proposal.scope_data
        service_areas = scope_data.get("serviceAreas", [])

        for area in service_areas:
            # Area Header
            area_name = area.get("name", "")
            story.append(
                Paragraph(
                    f"<b>{area_name}</b>",
                    ParagraphStyle(
                        "AreaHeader",
                        parent=body_style,
                        fontSize=12,
                        textColor=self.brand_color,
                        spaceAfter=8,
                        spaceBefore=12,
                    ),
                )
            )

            # Tasks Table
            tasks = area.get("tasks", [])
            if tasks:
                # Table header
                table_data = [["Task", "Frequency", "Notes"]]

                # Add tasks
                for task in tasks:
                    task_label = task.get("label", "")
                    frequency = task.get("frequency", "As Needed")
                    notes = task.get("notes", "")

                    table_data.append([task_label, frequency, notes or "-"])

                # Create table
                task_table = Table(
                    table_data,
                    colWidths=[3.5 * inch, 1.5 * inch, 1.5 * inch],
                    repeatRows=1,
                )

                task_table.setStyle(
                    TableStyle(
                        [
                            # Header row
                            ("BACKGROUND", (0, 0), (-1, 0), self.brand_color),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
                            ("ALIGN", (0, 0), (-1, 0), "LEFT"),
                            ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                            ("TOPPADDING", (0, 0), (-1, 0), 10),
                            # Data rows
                            ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
                            ("TEXTCOLOR", (0, 1), (-1, -1), self.dark_gray),
                            ("ALIGN", (0, 1), (-1, -1), "LEFT"),
                            ("VALIGN", (0, 1), (-1, -1), "TOP"),
                            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, self.light_gray]),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                            ("LEFTPADDING", (0, 0), (-1, -1), 8),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                            ("TOPPADDING", (0, 1), (-1, -1), 6),
                            ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
                        ]
                    )
                )

                story.append(task_table)
                story.append(Spacer(1, 0.2 * inch))

        # Provider Notes
        if self.proposal.provider_notes:
            story.append(Spacer(1, 0.3 * inch))
            story.append(Paragraph("ADDITIONAL NOTES", heading_style))
            story.append(Paragraph(self.proposal.provider_notes, body_style))

        # Footer Section
        story.append(Spacer(1, 0.5 * inch))
        story.append(
            Paragraph(
                "<i>This Scope of Work is an integral part of the service agreement between the parties.</i>",
                ParagraphStyle(
                    "Footer",
                    parent=body_style,
                    fontSize=8,
                    textColor=colors.grey,
                    alignment=1,
                ),
            )
        )

        # Build PDF
        doc.build(story, onFirstPage=self._add_page_number, onLaterPages=self._add_page_number)

        # Get PDF bytes
        pdf_bytes = buffer.getvalue()
        buffer.close()

        logger.info(f"✅ Generated scope PDF ({len(pdf_bytes)} bytes)")
        return pdf_bytes

    def _format_address(self) -> str:
        """Format client property address"""
        form_data = self.client.form_data or {}
        address_parts = []

        if form_data.get("property_address"):
            address_parts.append(form_data["property_address"])
        if form_data.get("property_city"):
            address_parts.append(form_data["property_city"])
        if form_data.get("property_state"):
            address_parts.append(form_data["property_state"])
        if form_data.get("property_zipcode"):
            address_parts.append(form_data["property_zipcode"])

        return ", ".join(address_parts) if address_parts else "N/A"

    def _add_page_number(self, canvas_obj, doc):
        """Add page numbers to PDF"""
        page_num = canvas_obj.getPageNumber()
        text = f"Page {page_num}"
        canvas_obj.setFont("Helvetica", 9)
        canvas_obj.setFillColor(colors.grey)
        canvas_obj.drawRightString(self.page_width - self.margin, self.margin / 2, text)

    @staticmethod
    def calculate_hash(pdf_bytes: bytes) -> str:
        """Calculate SHA-256 hash of PDF"""
        return hashlib.sha256(pdf_bytes).hexdigest()


async def generate_scope_pdf(proposal: ScopeProposal, db: Session) -> tuple[bytes, str, str]:
    """
    Generate scope PDF, upload to R2, and return (pdf_bytes, pdf_hash, pdf_key)
    """
    generator = ScopePDFGenerator(proposal, db)
    pdf_bytes = generator.generate()
    pdf_hash = ScopePDFGenerator.calculate_hash(pdf_bytes)

    # Get user firebase_uid for R2 path
    user = db.query(User).filter(User.id == proposal.user_id).first()
    if not user:
        raise ValueError("User not found")

    # Upload to R2
    pdf_key = upload_scope_pdf_to_r2(pdf_bytes, user.firebase_uid, proposal.public_id)

    return pdf_bytes, pdf_hash, pdf_key
