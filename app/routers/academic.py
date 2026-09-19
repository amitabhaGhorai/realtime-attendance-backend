"""Academic Structure & Curriculum Endpoints."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import Department, Section, Room, Course, CourseOffering, Enrollment, User
from app.schemas import (
    DepartmentCreate, DepartmentResponse,
    SectionCreate, SectionResponse,
    RoomCreate, RoomResponse,
    CourseCreate, CourseResponse,
    CourseOfferingCreate, CourseOfferingResponse,
    EnrollmentCreate, EnrollmentResponse
)
from app.auth import get_current_user, require_roles

router = APIRouter(tags=["Academic Hierarchy"])

# --- Departments ---
@router.get("/departments", response_model=List[DepartmentResponse])
async def list_departments(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Department).order_by(Department.name))
    return result.scalars().all()

@router.post("/departments", response_model=DepartmentResponse, dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN"))])
async def create_department(dept: DepartmentCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Department).where(Department.code == dept.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Department with code {dept.code} already exists")
    new_dept = Department(name=dept.name, code=dept.code)
    db.add(new_dept)
    await db.commit()
    await db.refresh(new_dept)
    return new_dept

# --- Sections ---
@router.get("/sections", response_model=List[SectionResponse])
async def list_sections(department_id: int = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Section)
    if department_id:
        stmt = stmt.where(Section.department_id == department_id)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/sections", response_model=SectionResponse, dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN"))])
async def create_section(sec: SectionCreate, db: AsyncSession = Depends(get_db)):
    new_sec = Section(
        department_id=sec.department_id,
        academic_year=sec.academic_year,
        semester=sec.semester,
        section_name=sec.section_name
    )
    db.add(new_sec)
    await db.commit()
    await db.refresh(new_sec)
    return new_sec

# --- Rooms ---
@router.get("/rooms", response_model=List[RoomResponse])
async def list_rooms(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Room).order_by(Room.building, Room.room_number))
    return result.scalars().all()

@router.post("/rooms", response_model=RoomResponse, dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN"))])
async def create_room(room: RoomCreate, db: AsyncSession = Depends(get_db)):
    new_room = Room(building=room.building, room_number=room.room_number, capacity=room.capacity)
    db.add(new_room)
    await db.commit()
    await db.refresh(new_room)
    return new_room

# --- Courses ---
@router.get("/courses", response_model=List[CourseResponse])
async def list_courses(department_id: int = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Course)
    if department_id:
        stmt = stmt.where(Course.department_id == department_id)
    result = await db.execute(stmt.order_by(Course.course_code))
    return result.scalars().all()

@router.post("/courses", response_model=CourseResponse, dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN"))])
async def create_course(course: CourseCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Course).where(Course.course_code == course.course_code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Course with code {course.course_code} already exists")
    new_course = Course(
        department_id=course.department_id,
        course_code=course.course_code,
        course_name=course.course_name,
        credits=course.credits,
        semester=course.semester
    )
    db.add(new_course)
    await db.commit()
    await db.refresh(new_course)
    return new_course

# --- Course Offerings ---
@router.get("/course-offerings", response_model=List[CourseOfferingResponse])
async def list_course_offerings(teacher_id: int = None, db: AsyncSession = Depends(get_db)):
    stmt = select(CourseOffering).options(
        selectinload(CourseOffering.course),
        selectinload(CourseOffering.teacher),
        selectinload(CourseOffering.section)
    )
    if teacher_id:
        stmt = stmt.where(CourseOffering.teacher_id == teacher_id)
    result = await db.execute(stmt)
    offerings = result.scalars().all()
    
    responses = []
    for off in offerings:
        responses.append(CourseOfferingResponse(
            id=off.id,
            course_id=off.course_id,
            teacher_id=off.teacher_id,
            section_id=off.section_id,
            academic_year=off.academic_year,
            semester=off.semester,
            course_name=off.course.course_name if off.course else None,
            course_code=off.course.course_code if off.course else None,
            teacher_name=off.teacher.name if off.teacher else None,
            section_name=off.section.section_name if off.section else None
        ))
    return responses

@router.post("/course-offerings", response_model=CourseOfferingResponse, dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN"))])
async def create_course_offering(off: CourseOfferingCreate, db: AsyncSession = Depends(get_db)):
    new_offering = CourseOffering(
        course_id=off.course_id,
        teacher_id=off.teacher_id,
        section_id=off.section_id,
        academic_year=off.academic_year,
        semester=off.semester
    )
    db.add(new_offering)
    await db.commit()
    await db.refresh(new_offering)
    return CourseOfferingResponse(
        id=new_offering.id,
        course_id=new_offering.course_id,
        teacher_id=new_offering.teacher_id,
        section_id=new_offering.section_id,
        academic_year=new_offering.academic_year,
        semester=new_offering.semester
    )

# --- Enrollments ---
@router.post("/enrollments", response_model=EnrollmentResponse, dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN"))])
async def enroll_student(enr: EnrollmentCreate, db: AsyncSession = Depends(get_db)):
    # Check duplicate
    stmt = select(Enrollment).where(
        Enrollment.course_offering_id == enr.course_offering_id,
        Enrollment.student_id == enr.student_id
    )
    existing = await db.execute(stmt)
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Student is already enrolled in this course offering")

    new_enr = Enrollment(course_offering_id=enr.course_offering_id, student_id=enr.student_id)
    db.add(new_enr)
    await db.commit()
    await db.refresh(new_enr)
    return new_enr
