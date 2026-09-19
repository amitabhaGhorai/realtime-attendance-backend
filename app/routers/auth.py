"""Authentication and Authorization Endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User, Student, Teacher
from app.schemas import LoginRequest, Token, UserResponse
from app.auth import verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=Token)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.username == req.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated. Contact administrator."
        )

    access_token = create_access_token(
        data={"sub": user.username, "role": user.role, "user_id": user.id}
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role,
        user_id=user.id,
        username=user.username,
        full_name=user.full_name
    )

@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    profile = {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at
    }
    if current_user.role == "STUDENT":
        s_stmt = select(Student).where(Student.user_id == current_user.id)
        s_res = await db.execute(s_stmt)
        student = s_res.scalar_one_or_none()
        if student:
            profile["student"] = {
                "id": student.id,
                "roll_number": student.roll_number,
                "department_id": student.department_id,
                "section_id": student.section_id,
                "semester": student.semester
            }
    elif current_user.role == "TEACHER":
        t_stmt = select(Teacher).where(Teacher.user_id == current_user.id)
        t_res = await db.execute(t_stmt)
        teacher = t_res.scalar_one_or_none()
        if teacher:
            profile["teacher"] = {
                "id": teacher.id,
                "employee_id": teacher.employee_id,
                "department_id": teacher.department_id,
                "designation": teacher.designation
            }
    return profile

@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    return {"message": "Successfully logged out"}
