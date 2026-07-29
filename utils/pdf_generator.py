import io
import re
import datetime
import html
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.pdfgen import canvas

class AcademicNumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to calculate total pages and render standard academic running headers and footers.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_decorations(self, page_count):
        self.saveState()
        self.setFont("Times-Roman", 9)
        self.setFillColor(colors.HexColor("#4A5568"))

        width, height = letter
        margin = 54  # 0.75 in margin

        # Running Top Header (Pages > 1)
        if self._pageNumber > 1:
            self.drawString(margin, height - 36, "CAREER ADVISORY REPORT | PROFESSIONAL TECHNICAL ASSESSMENT")
            self.setStrokeColor(colors.HexColor("#CBD5E0"))
            self.setLineWidth(0.5)
            self.line(margin, height - 42, width - margin, height - 42)

        # Running Footer (All pages)
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(width - margin, 36, page_str)
        self.drawString(margin, 36, "CONFIDENTIAL | PREPARED FOR PROFESSIONAL CAREER DEVELOPMENT")
        self.setStrokeColor(colors.HexColor("#CBD5E0"))
        self.setLineWidth(0.5)
        self.line(margin, 48, width - margin, 48)

        self.restoreState()


def remove_emojis_and_icons(text: str) -> str:
    """Removes emoji characters, decorative icons, and non-academic symbols."""
    if not text:
        return ""
    cleaned_chars = []
    for char in text:
        cp = ord(char)
        # Skip emoji & decorative symbol unicode blocks
        if (0x1F600 <= cp <= 0x1F64F or
            0x1F300 <= cp <= 0x1F5FF or
            0x1F680 <= cp <= 0x1F6FF or
            0x1F1E0 <= cp <= 0x1F1FF or
            0x2600 <= cp <= 0x26FF or
            0x2700 <= cp <= 0x27BF or
            0x1F900 <= cp <= 0x1F9FF or
            0x1FA70 <= cp <= 0x1FAFF or
            0x2300 <= cp <= 0x23FF or
            0x2B50 <= cp <= 0x2B55 or
            char in "✓🎯🇱🇰📥📋🏆🎓📍💡🚀📌⚖️🗺️🎉💪❌⚡"):
            continue
        cleaned_chars.append(char)
    return "".join(cleaned_chars)


def sanitize_text_for_reportlab(text: str) -> str:
    """
    Sanitizes markdown string into clean HTML/XML formatted text safe for ReportLab Paragraphs.
    Converts bold (**...**) and italic (*...*) into ReportLab <b> and <i> tags while escaping raw XML.
    """
    if not text:
        return ""

    # 1. Remove emojis and icons
    cleaned = remove_emojis_and_icons(text)

    # 2. Strip complex HTML containers/classes
    cleaned = re.sub(r'</?(div|span|h[1-6]|p|br|table|tr|td|th)[^>]*>', ' ', cleaned, flags=re.IGNORECASE)

    # 3. Handle bold and italic markdown tags
    # Convert **bold** to placeholder
    cleaned = re.sub(r'\*\*(.*?)\*\*', r'___B_OPEN___\1___B_CLOSE___', cleaned)
    cleaned = re.sub(r'\*(.*?)\*', r'___I_OPEN___\1___I_CLOSE___', cleaned)

    # 4. Escape XML entities
    cleaned = cleaned.replace('&', '&amp;')
    cleaned = cleaned.replace('<', '&lt;').replace('>', '&gt;')

    # 5. Restore ReportLab supported tags
    cleaned = cleaned.replace('___B_OPEN___', '<b>').replace('___B_CLOSE___', '</b>')
    cleaned = cleaned.replace('___I_OPEN___', '<i>').replace('___I_CLOSE___', '</i>')

    return cleaned.strip()


def parse_markdown_to_flowables(md_text: str, styles: dict) -> list:
    """
    Parses clean markdown text line-by-line into structured ReportLab flowables.
    """
    flowables = []
    lines = md_text.split('\n')

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            flowables.append(Spacer(1, 3))
            continue

        # Header detection
        if line.startswith("# "):
            header_text = sanitize_text_for_reportlab(line.lstrip("#").strip())
            flowables.append(Spacer(1, 8))
            flowables.append(Paragraph(header_text, styles["AcademicH1"]))
            flowables.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#2D3748"), spaceBefore=3, spaceAfter=6))
            continue
        elif line.startswith("## "):
            header_text = sanitize_text_for_reportlab(line.lstrip("#").strip())
            flowables.append(Spacer(1, 6))
            flowables.append(Paragraph(header_text, styles["AcademicH2"]))
            flowables.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#718096"), spaceBefore=2, spaceAfter=5))
            continue
        elif line.startswith("### ") or line.startswith("#### "):
            header_text = sanitize_text_for_reportlab(line.lstrip("#").strip())
            flowables.append(Spacer(1, 4))
            flowables.append(Paragraph(header_text, styles["AcademicH3"]))
            continue

        # Bullet list item
        if line.startswith("- ") or line.startswith("* ") or line.startswith("• "):
            bullet_body = re.sub(r'^[-*•]\s*', '', line)
            sanitized_bullet = sanitize_text_for_reportlab(bullet_body)
            flowables.append(Paragraph(f"• &nbsp; {sanitized_bullet}", styles["AcademicBullet"]))
            continue

        # Numbered list item
        num_match = re.match(r'^(\d+)\.\s+(.*)', line)
        if num_match:
            num_idx, num_body = num_match.groups()
            sanitized_num = sanitize_text_for_reportlab(num_body)
            flowables.append(Paragraph(f"<b>{num_idx}.</b> &nbsp; {sanitized_num}", styles["AcademicNumbered"]))
            continue

        # Standard paragraph line
        sanitized_p = sanitize_text_for_reportlab(line)
        flowables.append(Paragraph(sanitized_p, styles["AcademicBody"]))

    return flowables


def generate_academic_pdf(target_role: str, parsed_sec: dict = None, raw_recommendation: str = "", extracted_skills: list = None, missing_skills: list = None) -> bytes:
    """
    Generates a professional academic PDF report payload as bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    base_styles = getSampleStyleSheet()

    # Define academic typography styles (Serif Times-Roman for academic rigor)
    custom_styles = {
        "DocTitle": ParagraphStyle(
            name="DocTitle",
            fontName="Times-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#1A202C"),
            alignment=TA_LEFT,
            spaceAfter=4
        ),
        "DocSubtitle": ParagraphStyle(
            name="DocSubtitle",
            fontName="Times-Italic",
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor("#4A5568"),
            alignment=TA_LEFT,
            spaceAfter=10
        ),
        "AcademicH1": ParagraphStyle(
            name="AcademicH1",
            fontName="Times-Bold",
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#1A202C"),
            spaceBefore=10,
            spaceAfter=4,
            keepWithNext=True
        ),
        "AcademicH2": ParagraphStyle(
            name="AcademicH2",
            fontName="Times-Bold",
            fontSize=11.5,
            leading=15,
            textColor=colors.HexColor("#2D3748"),
            spaceBefore=8,
            spaceAfter=3,
            keepWithNext=True
        ),
        "AcademicH3": ParagraphStyle(
            name="AcademicH3",
            fontName="Times-BoldItalic",
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor("#2D3748"),
            spaceBefore=6,
            spaceAfter=2,
            keepWithNext=True
        ),
        "AcademicBody": ParagraphStyle(
            name="AcademicBody",
            fontName="Times-Roman",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#1A202C"),
            alignment=TA_JUSTIFY,
            spaceAfter=5
        ),
        "AcademicBullet": ParagraphStyle(
            name="AcademicBullet",
            fontName="Times-Roman",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#1A202C"),
            leftIndent=16,
            firstLineIndent=-10,
            spaceAfter=3
        ),
        "AcademicNumbered": ParagraphStyle(
            name="AcademicNumbered",
            fontName="Times-Roman",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#1A202C"),
            leftIndent=16,
            firstLineIndent=-10,
            spaceAfter=3
        ),
        "MetaCellLabel": ParagraphStyle(
            name="MetaCellLabel",
            fontName="Times-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#2D3748")
        ),
        "MetaCellValue": ParagraphStyle(
            name="MetaCellValue",
            fontName="Times-Roman",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#1A202C")
        )
    }

    story = []

    # Title Banner Block
    story.append(Paragraph("CAREER ADVISORY & STRATEGIC ASSESSMENT REPORT", custom_styles["DocTitle"]))
    story.append(Paragraph("Formal Technical Evaluation and Skill Acquisition Plan", custom_styles["DocSubtitle"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1A202C"), spaceBefore=2, spaceAfter=10))

    # Academic Document Metadata Table
    curr_date = datetime.datetime.now().strftime("%B %d, %Y")
    clean_role = sanitize_text_for_reportlab(target_role or "Technical Specialist")
    
    meta_table_data = [
        [
            Paragraph("Target Role:", custom_styles["MetaCellLabel"]),
            Paragraph(clean_role, custom_styles["MetaCellValue"]),
            Paragraph("Report Date:", custom_styles["MetaCellLabel"]),
            Paragraph(curr_date, custom_styles["MetaCellValue"])
        ],
        [
            Paragraph("Market Benchmark:", custom_styles["MetaCellLabel"]),
            Paragraph("Sri Lanka IT Sector (2026)", custom_styles["MetaCellValue"]),
            Paragraph("Publication Style:", custom_styles["MetaCellLabel"]),
            Paragraph("Academic & Professional Standard", custom_styles["MetaCellValue"])
        ]
    ]

    t_meta = Table(meta_table_data, colWidths=[110, 170, 95, 129])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#EDF2F7")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 12))

    # Executive Technical Qualifications Summary Table
    ext_skills_list = extracted_skills or []
    miss_skills_list = missing_skills or []
    
    if ext_skills_list or miss_skills_list:
        story.append(Paragraph("1. Executive Summary of Technical Qualifications", custom_styles["AcademicH1"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#2D3748"), spaceBefore=2, spaceAfter=6))

        str_str = ", ".join(ext_skills_list) if ext_skills_list else "None specified"
        gap_str = ", ".join(miss_skills_list) if miss_skills_list else "None identified"

        skills_table_data = [
            [
                Paragraph("<b>Qualification Category</b>", custom_styles["MetaCellLabel"]),
                Paragraph("<b>Identified Technical Skill Set</b>", custom_styles["MetaCellLabel"])
            ],
            [
                Paragraph("Existing Strengths", custom_styles["MetaCellLabel"]),
                Paragraph(sanitize_text_for_reportlab(str_str), custom_styles["MetaCellValue"])
            ],
            [
                Paragraph("Priority Missing Gaps", custom_styles["MetaCellLabel"]),
                Paragraph(sanitize_text_for_reportlab(gap_str), custom_styles["MetaCellValue"])
            ]
        ]

        t_skills = Table(skills_table_data, colWidths=[140, 364])
        t_skills.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#EDF2F7")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(t_skills)
        story.append(Spacer(1, 12))

    # Detailed Structured Sections
    if parsed_sec and isinstance(parsed_sec, dict) and any(parsed_sec.values()):
        sec_mapping = [
            ("profile", "2. Target Career Profile & Feasibility Assessment"),
            ("strengths_gaps", "3. Detailed Competency & Skill Gap Analysis"),
            ("roadmap", "4. Step-by-Step Learning & Development Roadmap"),
            ("certifications", "5. Recommended Professional Certifications"),
            ("market_advice", "6. Strategic Industry Guidance (Sri Lanka Market)")
        ]

        for key, sec_title in sec_mapping:
            sec_text = parsed_sec.get(key, "")
            if sec_text and sec_text.strip():
                story.append(Paragraph(sec_title, custom_styles["AcademicH1"]))
                story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#4A5568"), spaceBefore=2, spaceAfter=5))
                flowables = parse_markdown_to_flowables(sec_text, custom_styles)
                story.extend(flowables)
                story.append(Spacer(1, 8))
    elif raw_recommendation and raw_recommendation.strip():
        flowables = parse_markdown_to_flowables(raw_recommendation, custom_styles)
        story.extend(flowables)

    # Build Document using Numbered Canvas
    doc.build(story, canvasmaker=AcademicNumberedCanvas)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data
