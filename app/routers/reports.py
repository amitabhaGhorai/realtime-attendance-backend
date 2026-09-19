"""Reporting and Export (PDF & CSV) Endpoints."""
import io
import csv
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import AttendanceRecord, AttendanceSession, Student, CourseOffering, Course, Department, Section
from app.config import settings
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

router = APIRouter(prefix="/reports", tags=["Reporting & Exports"])

@router.get("/daily")
async def get_daily_summary(
    date_str: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    target_date = date_str or date.today().isoformat()
    
    # Total sessions today
    sessions_stmt = select(AttendanceSession).where(AttendanceSession.date == target_date)
    sessions = (await db.execute(sessions_stmt)).scalars().all()
    session_ids = [s.id for s in sessions]

    if not session_ids:
        return {
            "date": target_date,
            "total_sessions": 0,
            "total_records": 0,
            "present_count": 0,
            "late_count": 0,
            "absent_count": 0,
            "attendance_rate": 0.0
        }

    records_stmt = select(AttendanceRecord).where(AttendanceRecord.session_id.in_(session_ids))
    records = (await db.execute(records_stmt)).scalars().all()

    present_count = sum(1 for r in records if r.status == "PRESENT")
    late_count = sum(1 for r in records if r.status == "LATE")
    absent_count = sum(1 for r in records if r.status == "ABSENT")
    total = len(records)
    rate = round(((present_count + late_count) / total * 100.0), 1) if total > 0 else 0.0

    return {
        "date": target_date,
        "total_sessions": len(sessions),
        "total_records": total,
        "present_count": present_count,
        "late_count": late_count,
        "absent_count": absent_count,
        "attendance_rate": rate
    }

@router.get("/student/{student_id}")
async def get_student_report(student_id: int, db: AsyncSession = Depends(get_db)):
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    stmt = select(AttendanceRecord).options(
        selectinload(AttendanceRecord.session).selectinload(AttendanceSession.course_offering).selectinload(CourseOffering.course)
    ).where(AttendanceRecord.student_id == student_id).order_by(AttendanceRecord.marked_at.desc())

    records = (await db.execute(stmt)).scalars().all()

    total_classes = len(records)
    attended = sum(1 for r in records if r.status in ["PRESENT", "LATE"])
    percentage = round((attended / total_classes * 100.0), 1) if total_classes > 0 else 0.0

    history = []
    for r in records:
        c_name = r.session.course_offering.course.course_name if r.session and r.session.course_offering and r.session.course_offering.course else "Class"
        history.append({
            "record_id": r.id,
            "session_title": r.session.title if r.session else "Session",
            "course_name": c_name,
            "date": r.session.date if r.session else "",
            "status": r.status,
            "marked_at": r.marked_at.strftime("%Y-%m-%d %H:%M"),
            "method": r.verification_method
        })

    return {
        "student_id": student.id,
        "name": student.name,
        "roll_number": student.roll_number,
        "total_classes": total_classes,
        "attended_classes": attended,
        "attendance_percentage": percentage,
        "is_eligible": percentage >= 75.0,  # 75% college eligibility threshold
        "history": history
    }

@router.get("/export/csv")
async def export_attendance_csv(
    session_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(AttendanceRecord).options(
        selectinload(AttendanceRecord.student),
        selectinload(AttendanceRecord.session).selectinload(AttendanceSession.course_offering).selectinload(CourseOffering.course)
    )
    if session_id:
        stmt = stmt.where(AttendanceRecord.session_id == session_id)

    records = (await db.execute(stmt.order_by(AttendanceRecord.marked_at.desc()))).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Record ID", "Session Title", "Course Code", "Course Name",
        "Student Roll No", "Student Name", "Status", "Marked Time",
        "Verification Method", "Confidence Score", "Notes"
    ])

    for r in records:
        c_code = r.session.course_offering.course.course_code if r.session and r.session.course_offering and r.session.course_offering.course else ""
        c_name = r.session.course_offering.course.course_name if r.session and r.session.course_offering and r.session.course_offering.course else ""
        writer.writerow([
            r.id,
            r.session.title if r.session else "",
            c_code,
            c_name,
            r.student.roll_number if r.student else "",
            r.student.name if r.student else "",
            r.status,
            r.marked_at.strftime("%Y-%m-%d %H:%M:%S") if r.marked_at else "",
            r.verification_method,
            f"{round(r.confidence_score, 3)}" if r.confidence_score else "N/A",
            r.notes or ""
        ])

    output.seek(0)
    filename = f"attendance_report_{date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/export/pdf")
async def export_attendance_pdf(
    session_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(AttendanceRecord).options(
        selectinload(AttendanceRecord.student),
        selectinload(AttendanceRecord.session).selectinload(AttendanceSession.course_offering).selectinload(CourseOffering.course)
    )
    if session_id:
        stmt = stmt.where(AttendanceRecord.session_id == session_id)

    records = (await db.execute(stmt.order_by(AttendanceRecord.marked_at.desc()))).scalars().all()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    styles = getSampleStyleSheet()

    # Title & Header
    title_style = ParagraphStyle(
        name="InstTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1e3a8a"),
        alignment=1  # Center
    )
    subtitle_style = ParagraphStyle(
        name="SubTitle",
        parent=styles["Normal"],
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#475569"),
        alignment=1
    )

    elements.append(Paragraph(settings.INSTITUTION_NAME, title_style))
    elements.append(Paragraph("Official Real-Time Attendance Audit Ledger", subtitle_style))
    elements.append(Paragraph(f"Generated on: {datetime.utcnow().strftime('%B %d, %Y %H:%M UTC')}", subtitle_style))
    elements.append(Spacer(1, 15))

    # Summary Stats
    total = len(records)
    present = sum(1 for r in records if r.status == "PRESENT")
    late = sum(1 for r in records if r.status == "LATE")
    absent = sum(1 for r in records if r.status == "ABSENT")
    rate = round((present + late) / total * 100.0, 1) if total > 0 else 0.0

    summary_data = [
        ["Total Records", "Present", "Late", "Absent", "Turnout %"],
        [str(total), str(present), str(late), str(absent), f"{rate}%"]
    ]
    summary_table = Table(summary_data, colWidths=[100, 100, 100, 100, 140])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor("#0f172a")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1"))
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    # Attendance Table
    table_data = [["Roll No", "Student Name", "Course", "Status", "Time", "Method"]]
    for r in records[:150]:  # Cap first 150 rows in single document
        c_code = r.session.course_offering.course.course_code if r.session and r.session.course_offering and r.session.course_offering.course else ""
        table_data.append([
            r.student.roll_number if r.student else "N/A",
            r.student.name[:22] if r.student else "Unknown",
            c_code,
            r.status,
            r.marked_at.strftime("%H:%M:%S") if r.marked_at else "",
            "AI FACE" if r.verification_method == "FACE_RECOGNITION" else "MANUAL"
        ])

    rec_table = Table(table_data, colWidths=[85, 145, 75, 75, 75, 85])
    rec_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4)
    ]))
    elements.append(rec_table)

    doc.build(elements)
    buffer.seek(0)
    filename = f"attendance_report_{date.today().isoformat()}.pdf"

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
