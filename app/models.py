"""SQLAlchemy ORM Models for all 16 System Entities."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="STUDENT")  # SUPER_ADMIN, ADMIN, TEACHER, STUDENT, DEVICE_OPERATOR
    full_name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    student = relationship("Student", back_populates="user", uselist=False)
    teacher = relationship("Teacher", back_populates="user", uselist=False)
    audit_logs = relationship("AuditLog", back_populates="user")
    notifications = relationship("Notification", back_populates="user")


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    role_name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255))
    permissions = Column(Text)  # JSON or comma-separated permissions


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(20), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    sections = relationship("Section", back_populates="department")
    teachers = relationship("Teacher", back_populates="department")
    courses = relationship("Course", back_populates="department")
    students = relationship("Student", back_populates="department")


class Section(Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    academic_year = Column(String(20), nullable=False)  # e.g., "2025-2026"
    semester = Column(Integer, nullable=False)
    section_name = Column(String(20), nullable=False)  # e.g., "A", "B"

    department = relationship("Department", back_populates="sections")
    students = relationship("Student", back_populates="section")
    course_offerings = relationship("CourseOffering", back_populates="section")


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    building = Column(String(100), nullable=False)
    room_number = Column(String(50), nullable=False)
    capacity = Column(Integer, default=60)

    devices = relationship("Device", back_populates="room")
    attendance_sessions = relationship("AttendanceSession", back_populates="room")


class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    employee_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    designation = Column(String(100), default="Assistant Professor")
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="teacher")
    department = relationship("Department", back_populates="teachers")
    course_offerings = relationship("CourseOffering", back_populates="teacher")
    attendance_sessions = relationship("AttendanceSession", back_populates="teacher")


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=True)
    roll_number = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False)
    semester = Column(Integer, nullable=False)
    contact_number = Column(String(20))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="student")
    department = relationship("Department", back_populates="students")
    section = relationship("Section", back_populates="students")
    enrollments = relationship("Enrollment", back_populates="student")
    attendance_records = relationship("AttendanceRecord", back_populates="student")
    face_templates = relationship("FaceTemplate", back_populates="student", cascade="all, delete-orphan")


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    course_code = Column(String(20), unique=True, index=True, nullable=False)
    course_name = Column(String(150), nullable=False)
    credits = Column(Integer, default=3)
    semester = Column(Integer, nullable=False)

    department = relationship("Department", back_populates="courses")
    offerings = relationship("CourseOffering", back_populates="course")


class CourseOffering(Base):
    __tablename__ = "course_offerings"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False)
    academic_year = Column(String(20), nullable=False)
    semester = Column(Integer, nullable=False)

    course = relationship("Course", back_populates="offerings")
    teacher = relationship("Teacher", back_populates="course_offerings")
    section = relationship("Section", back_populates="course_offerings")
    enrollments = relationship("Enrollment", back_populates="course_offering")
    attendance_sessions = relationship("AttendanceSession", back_populates="course_offering")


class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, index=True)
    course_offering_id = Column(Integer, ForeignKey("course_offerings.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    enrolled_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("course_offering_id", "student_id", name="uq_offering_student"),
    )

    course_offering = relationship("CourseOffering", back_populates="enrollments")
    student = relationship("Student", back_populates="enrollments")


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"

    id = Column(Integer, primary_key=True, index=True)
    course_offering_id = Column(Integer, ForeignKey("course_offerings.id"), nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    title = Column(String(150), nullable=False)
    date = Column(String(20), nullable=False)  # YYYY-MM-DD
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    grace_period_minutes = Column(Integer, default=10)
    status = Column(String(20), default="ACTIVE")  # SCHEDULED, ACTIVE, PAUSED, CLOSED
    created_at = Column(DateTime, default=datetime.utcnow)

    course_offering = relationship("CourseOffering", back_populates="attendance_sessions")
    room = relationship("Room", back_populates="attendance_sessions")
    teacher = relationship("Teacher", back_populates="attendance_sessions")
    attendance_records = relationship("AttendanceRecord", back_populates="session", cascade="all, delete-orphan")
    recognition_events = relationship("RecognitionEvent", back_populates="session")


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("attendance_sessions.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    status = Column(String(20), nullable=False, default="PRESENT")  # PRESENT, LATE, ABSENT, EXCUSED
    marked_at = Column(DateTime, default=datetime.utcnow)
    verification_method = Column(String(30), default="FACE_RECOGNITION")  # FACE_RECOGNITION, MANUAL_OVERRIDE
    confidence_score = Column(Float, nullable=True)
    marked_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_session_student_attendance"),
    )

    session = relationship("AttendanceSession", back_populates="attendance_records")
    student = relationship("Student", back_populates="attendance_records")


class FaceTemplate(Base):
    __tablename__ = "face_templates"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    embedding = Column(Text, nullable=False)  # JSON-serialized float array (128-d or 512-d)
    model_version = Column(String(50), default="OpenCV_SFace_v1")
    quality_score = Column(Float, default=1.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="face_templates")


class RecognitionEvent(Base):
    __tablename__ = "recognition_events"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("attendance_sessions.id"), nullable=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)
    recognized_student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    confidence = Column(Float, nullable=True)
    result = Column(String(30), nullable=False)  # SUCCESS, DUPLICATE, NOT_ENROLLED, LOW_CONFIDENCE, UNKNOWN, SPOOF_DETECTED
    error_message = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    session = relationship("AttendanceSession", back_populates="recognition_events")
    device = relationship("Device", back_populates="recognition_events")


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    device_code = Column(String(50), unique=True, nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=True)
    ip_address = Column(String(50))
    status = Column(String(20), default="ONLINE")  # ONLINE, OFFLINE
    last_heartbeat = Column(DateTime, default=datetime.utcnow)
    software_version = Column(String(50), default="v1.0.0")

    room = relationship("Room", back_populates="devices")
    recognition_events = relationship("RecognitionEvent", back_populates="device")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)  # e.g., "MANUAL_ATTENDANCE_OVERRIDE", "BIOMETRIC_REVOKED"
    entity_type = Column(String(50), nullable=False)  # e.g., "AttendanceRecord", "FaceTemplate"
    entity_id = Column(Integer, nullable=True)
    old_state = Column(Text, nullable=True)
    new_state = Column(Text, nullable=True)
    reason = Column(String(255), nullable=True)
    ip_address = Column(String(50), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="audit_logs")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="notifications")
