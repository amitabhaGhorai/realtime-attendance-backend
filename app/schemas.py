"""Pydantic Schemas for Request/Response Validation."""
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

# --- Auth Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    username: str
    full_name: str

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None
    user_id: Optional[int] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    role: str
    is_active: bool = True

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True

# --- Academic Schemas ---
class DepartmentBase(BaseModel):
    name: str
    code: str

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentResponse(DepartmentBase):
    id: int
    class Config:
        from_attributes = True

class SectionBase(BaseModel):
    department_id: int
    academic_year: str
    semester: int
    section_name: str

class SectionCreate(SectionBase):
    pass

class SectionResponse(SectionBase):
    id: int
    class Config:
        from_attributes = True

class RoomBase(BaseModel):
    building: str
    room_number: str
    capacity: int = 60

class RoomCreate(RoomBase):
    pass

class RoomResponse(RoomBase):
    id: int
    class Config:
        from_attributes = True

class CourseBase(BaseModel):
    department_id: int
    course_code: str
    course_name: str
    credits: int = 3
    semester: int

class CourseCreate(CourseBase):
    pass

class CourseResponse(CourseBase):
    id: int
    class Config:
        from_attributes = True

class CourseOfferingCreate(BaseModel):
    course_id: int
    teacher_id: int
    section_id: int
    academic_year: str
    semester: int

class CourseOfferingResponse(BaseModel):
    id: int
    course_id: int
    teacher_id: int
    section_id: int
    academic_year: str
    semester: int
    course_name: Optional[str] = None
    course_code: Optional[str] = None
    teacher_name: Optional[str] = None
    section_name: Optional[str] = None
    class Config:
        from_attributes = True

class EnrollmentCreate(BaseModel):
    course_offering_id: int
    student_id: int

class EnrollmentResponse(BaseModel):
    id: int
    course_offering_id: int
    student_id: int
    enrolled_at: datetime
    class Config:
        from_attributes = True

# --- People Schemas ---
class TeacherCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    name: str
    employee_id: str
    department_id: int
    designation: str = "Assistant Professor"

class TeacherResponse(BaseModel):
    id: int
    user_id: int
    employee_id: str
    name: str
    email: str
    department_id: int
    designation: str
    is_active: bool
    department_name: Optional[str] = None
    class Config:
        from_attributes = True

class StudentCreate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = "student123"
    roll_number: str
    name: str
    email: EmailStr
    department_id: int
    section_id: int
    semester: int
    contact_number: Optional[str] = None

class StudentResponse(BaseModel):
    id: int
    roll_number: str
    name: str
    email: str
    department_id: int
    section_id: int
    semester: int
    contact_number: Optional[str] = None
    is_active: bool
    has_face_template: bool = False
    department_name: Optional[str] = None
    section_name: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True

# --- Attendance Schemas ---
class AttendanceSessionCreate(BaseModel):
    course_offering_id: int
    room_id: int
    teacher_id: int
    title: str
    grace_period_minutes: int = 10

class AttendanceSessionResponse(BaseModel):
    id: int
    course_offering_id: int
    room_id: int
    teacher_id: int
    title: str
    date: str
    start_time: datetime
    end_time: Optional[datetime] = None
    grace_period_minutes: int
    status: str
    course_name: Optional[str] = None
    teacher_name: Optional[str] = None
    room_number: Optional[str] = None
    total_enrolled: int = 0
    present_count: int = 0
    late_count: int = 0
    absent_count: int = 0
    class Config:
        from_attributes = True

class AttendanceRecordResponse(BaseModel):
    id: int
    session_id: int
    student_id: int
    student_name: str
    roll_number: str
    status: str
    marked_at: datetime
    verification_method: str
    confidence_score: Optional[float] = None
    notes: Optional[str] = None
    class Config:
        from_attributes = True

class AttendanceRecordOverride(BaseModel):
    status: str  # PRESENT, LATE, ABSENT, EXCUSED
    reason: str  # Mandatory justification for audit

# --- Biometric & AI Schemas ---
class FaceEnrollmentRequest(BaseModel):
    student_id: int
    samples: List[str]  # Base64 encoded JPEG/PNG images (1 to 3 images)

class FaceEnrollmentResponse(BaseModel):
    student_id: int
    success: bool
    quality_score: float
    message: str
    model_version: str

class RecognitionVerifyRequest(BaseModel):
    session_id: int
    image_base64: str
    device_id: Optional[int] = None

class RecognitionVerifyResponse(BaseModel):
    success: bool
    result: str  # SUCCESS, DUPLICATE, NOT_ENROLLED, LOW_CONFIDENCE, UNKNOWN, SPOOF_DETECTED
    student_id: Optional[int] = None
    student_name: Optional[str] = None
    roll_number: Optional[str] = None
    status: Optional[str] = None  # PRESENT or LATE
    confidence: Optional[float] = None
    message: str

# --- Devices ---
class DeviceCreate(BaseModel):
    name: str
    device_code: str
    room_id: Optional[int] = None
    ip_address: Optional[str] = None
    software_version: str = "v1.0.0"

class DeviceResponse(BaseModel):
    id: int
    name: str
    device_code: str
    room_id: Optional[int] = None
    ip_address: Optional[str] = None
    status: str
    last_heartbeat: datetime
    software_version: str
    room_number: Optional[str] = None
    class Config:
        from_attributes = True

# --- Audit Logs ---
class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    old_state: Optional[str] = None
    new_state: Optional[str] = None
    reason: Optional[str] = None
    ip_address: Optional[str] = None
    timestamp: datetime
    class Config:
        from_attributes = True
