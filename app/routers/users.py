"""Student, Teacher, and User Management Endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import User, Student, Teacher, Department, Section, FaceTemplate
from app.schemas import (
    StudentCreate, StudentResponse,
    TeacherCreate, TeacherResponse,
    UserResponse
)
from app.auth import get_password_hash, require_roles

router = APIRouter(tags=["People Management"])

# --- Students ---
@router.get("/students", response_model=List[StudentResponse])
async def list_students(department_id: Optional[int] = None, section_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Student).options(
        selectinload(Student.department),
        selectinload(Student.section),
        selectinload(Student.face_templates)
    )
    if department_id:
        stmt = stmt.where(Student.department_id == department_id)
    if section_id:
        stmt = stmt.where(Student.section_id == section_id)

    result = await db.execute(stmt.order_by(Student.roll_number))
    students = result.scalars().all()

    responses = []
    for s in students:
        has_face = any(ft.is_active for ft in s.face_templates)
        responses.append(StudentResponse(
            id=s.id,
            roll_number=s.roll_number,
            name=s.name,
            email=s.email,
            department_id=s.department_id,
            section_id=s.section_id,
            semester=s.semester,
            contact_number=s.contact_number,
            is_active=s.is_active,
            has_face_template=has_face,
            department_name=s.department.name if s.department else None,
            section_name=s.section.section_name if s.section else None,
            created_at=s.created_at
        ))
    return responses

@router.post("/students", response_model=StudentResponse, dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN"))])
async def create_student(data: StudentCreate, db: AsyncSession = Depends(get_db)):
    # Check roll number uniqueness
    check_roll = await db.execute(select(Student).where(Student.roll_number == data.roll_number))
    if check_roll.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Roll number {data.roll_number} already registered")

    # Create associated user account
    username = data.username or data.roll_number.lower()
    user_check = await db.execute(select(User).where(User.username == username))
    if user_check.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Username {username} already exists")

    new_user = User(
        username=username,
        email=data.email,
        hashed_password=get_password_hash(data.password or "student123"),
        role="STUDENT",
        full_name=data.name,
        is_active=True
    )
    db.add(new_user)
    await db.flush()

    new_student = Student(
        user_id=new_user.id,
        roll_number=data.roll_number,
        name=data.name,
        email=data.email,
        department_id=data.department_id,
        section_id=data.section_id,
        semester=data.semester,
        contact_number=data.contact_number,
        is_active=True
    )
    db.add(new_student)
    await db.commit()
    await db.refresh(new_student)

    return StudentResponse(
        id=new_student.id,
        roll_number=new_student.roll_number,
        name=new_student.name,
        email=new_student.email,
        department_id=new_student.department_id,
        section_id=new_student.section_id,
        semester=new_student.semester,
        contact_number=new_student.contact_number,
        is_active=new_student.is_active,
        has_face_template=False,
        created_at=new_student.created_at
    )

# --- Teachers ---
@router.get("/teachers", response_model=List[TeacherResponse])
async def list_teachers(db: AsyncSession = Depends(get_db)):
    stmt = select(Teacher).options(selectinload(Teacher.department))
    result = await db.execute(stmt.order_by(Teacher.name))
    teachers = result.scalars().all()

    responses = []
    for t in teachers:
        responses.append(TeacherResponse(
            id=t.id,
            user_id=t.user_id,
            employee_id=t.employee_id,
            name=t.name,
            email=t.email,
            department_id=t.department_id,
            designation=t.designation,
            is_active=t.is_active,
            department_name=t.department.name if t.department else None
        ))
    return responses

@router.post("/teachers", response_model=TeacherResponse, dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN"))])
async def create_teacher(data: TeacherCreate, db: AsyncSession = Depends(get_db)):
    check_emp = await db.execute(select(Teacher).where(Teacher.employee_id == data.employee_id))
    if check_emp.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Employee ID {data.employee_id} already registered")

    new_user = User(
        username=data.username,
        email=data.email,
        hashed_password=get_password_hash(data.password),
        role="TEACHER",
        full_name=data.name,
        is_active=True
    )
    db.add(new_user)
    await db.flush()

    new_teacher = Teacher(
        user_id=new_user.id,
        employee_id=data.employee_id,
        name=data.name,
        email=data.email,
        department_id=data.department_id,
        designation=data.designation,
        is_active=True
    )
    db.add(new_teacher)
    await db.commit()
    await db.refresh(new_teacher)

    return TeacherResponse(
        id=new_teacher.id,
        user_id=new_teacher.user_id,
        employee_id=new_teacher.employee_id,
        name=new_teacher.name,
        email=new_teacher.email,
        department_id=new_teacher.department_id,
        designation=new_teacher.designation,
        is_active=new_teacher.is_active
    )

# --- Users list & Status Toggle ---
@router.get("/users", response_model=List[UserResponse], dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN"))])
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.id))
    return result.scalars().all()

@router.patch("/users/{id}/status", dependencies=[Depends(require_roles("SUPER_ADMIN", "ADMIN"))])
async def toggle_user_status(id: int, is_active: bool, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = is_active
    await db.commit()
    return {"message": f"User {user.username} status updated to {'active' if is_active else 'inactive'}"}
