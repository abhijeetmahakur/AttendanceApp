"""Excel and PDF report generation for attendance data.

Both builders take plain Python data (already pulled from the database by
the caller) and return an in-memory BytesIO buffer ready to send with
Flask's send_file - no template files or filesystem writes involved.
"""

import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

EXCEL_HEADERS = [
    "Student Name", "Student ID", "Course", "Subject",
    "Total Classes", "Classes Attended", "Classes Missed",
    "Attendance %", "Status",
]


def build_attendance_excel(rows):
    """rows: iterable of dicts with keys matching EXCEL_HEADERS (snake_case).
    Returns a BytesIO containing an .xlsx workbook."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance"

    ws.append(EXCEL_HEADERS)
    header_fill = PatternFill(start_color="2F6FEB", end_color="2F6FEB", fill_type="solid")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    for row in rows:
        ws.append([
            row["student_name"], row["reg_no"], row["course"], row["subject"],
            row["total"], row["attended"], row["missed"],
            row["percentage"], row["status"],
        ])

    widths = [22, 14, 12, 20, 13, 16, 14, 13, 12]
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width

    ws.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def build_student_attendance_pdf(college_name, student, subject_rows, overall, threshold, exam_eligible=None, exam_threshold=33.0):
    """Builds a single-student attendance report PDF.

    student: dict with name, reg_no, course.
    subject_rows: list of dicts with subject, total, attended, missed, percentage, status.
    overall: dict with total, attended, missed, percentage, status.
    exam_eligible: bool or None (None = not computed, section omitted).
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Title"], fontSize=18, textColor=colors.HexColor("#2F6FEB"),
    )
    subtitle_style = ParagraphStyle("ReportSubtitle", parent=styles["Normal"], fontSize=11, spaceAfter=4)
    section_style = ParagraphStyle(
        "Section", parent=styles["Heading2"], fontSize=13, spaceBefore=14, spaceAfter=6,
    )

    elements = [
        Paragraph(college_name, title_style),
        Paragraph("Student Attendance Report", subtitle_style),
        Spacer(1, 0.3 * cm),
    ]

    student_info = Table(
        [
            ["Student Name:", student["name"], "Registration No.:", student["reg_no"]],
            ["Course / Class:", student["course"], "Report Generated:", datetime.now().strftime("%d %b %Y, %I:%M %p")],
        ],
        colWidths=[3.2 * cm, 5.3 * cm, 3.6 * cm, 5.3 * cm],
    )
    student_info.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(student_info)

    elements.append(Paragraph("Subject-wise Attendance", section_style))

    table_data = [["Subject", "Total Classes", "Attended", "Missed", "Percentage", "Status"]]
    for row in subject_rows:
        table_data.append([
            row["subject"], str(row["total"]), str(row["attended"]), str(row["missed"]),
            f"{row['percentage']}%", row["status"].title(),
        ])

    subject_table = Table(table_data, colWidths=[5.2 * cm, 3 * cm, 2.8 * cm, 2.4 * cm, 3 * cm, 3 * cm])
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2F6FEB")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c3c9d1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef0f3")]),
    ]
    for i, row in enumerate(subject_rows, start=1):
        if row["status"] == "critical":
            style_cmds.append(("TEXTCOLOR", (5, i), (5, i), colors.HexColor("#d64545")))
        elif row["status"] == "warning":
            style_cmds.append(("TEXTCOLOR", (5, i), (5, i), colors.HexColor("#b5740b")))
        else:
            style_cmds.append(("TEXTCOLOR", (5, i), (5, i), colors.HexColor("#1f9254")))
    subject_table.setStyle(TableStyle(style_cmds))
    elements.append(subject_table)

    elements.append(Paragraph("Overall Attendance", section_style))
    overall_table = Table(
        [
            ["Total Classes", "Attended", "Missed", "Overall Percentage", "Status"],
            [
                str(overall["total"]), str(overall["attended"]), str(overall["missed"]),
                f"{overall['percentage']}%", overall["status"].title(),
            ],
        ],
        colWidths=[3.9 * cm, 3.9 * cm, 3.9 * cm, 4.1 * cm, 3.7 * cm],
    )
    overall_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1c1f26")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c3c9d1")),
        ("TOPPADDING", (0, 1), (-1, 1), 8),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
    ]))
    elements.append(overall_table)

    if exam_eligible is not None:
        elements.append(Paragraph("Exam Eligibility", section_style))
        eligibility_label = "ELIGIBLE" if exam_eligible else "NOT ELIGIBLE"
        eligibility_color = colors.HexColor("#1f9254") if exam_eligible else colors.HexColor("#d64545")
        eligibility_table = Table(
            [[f"Minimum {exam_threshold:.0f}% attendance required to sit exams", eligibility_label]],
            colWidths=[12 * cm, 6.5 * cm],
        )
        eligibility_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
            ("TEXTCOLOR", (1, 0), (1, 0), eligibility_color),
            ("ALIGN", (1, 0), (1, 0), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c3c9d1")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(eligibility_table)
        if not exam_eligible:
            elements.append(Spacer(1, 0.2 * cm))
            elements.append(Paragraph(
                "Note: this student does not currently meet the minimum attendance required to sit "
                "for examinations. Please contact the department as soon as possible.",
                ParagraphStyle("EligibilityNote", parent=styles["Normal"], fontSize=9, textColor=eligibility_color),
            ))

    elements.append(Spacer(1, 0.6 * cm))
    elements.append(Paragraph(
        f"This report reflects attendance recorded up to {datetime.now().strftime('%d %b %Y')} "
        f"against a minimum requirement of {threshold:.0f}%.",
        ParagraphStyle("Footnote", parent=styles["Normal"], fontSize=8.5, textColor=colors.HexColor("#6b7280")),
    ))

    doc.build(elements)
    buf.seek(0)
    return buf
