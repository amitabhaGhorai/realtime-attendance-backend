"""Database Initialization and Demo Data Seeder."""
import json
from datetime import datetime, date
import numpy as np
from app.database import sync_engine, SyncSessionLocal, Base
from app.models import (
    User, Role, Department, Section, Room, Teacher, Student,
    Course, CourseOffering, Enrollment, AttendanceSession,
    AttendanceRecord, FaceTemplate, Device, AuditLog
)
from app.auth import get_password_hash

def seed_database():
    print("Creating tables...")
    Base.metadata.create_all(bind=sync_engine)
    db = SyncSessionLocal()

    # Check if already seeded
    if db.query(User).filter_by(username="admin").first():
        print("Database already seeded.")
        db.close()
        return

    print("Seeding roles and users...")
    # 1. Roles
    roles = [
        Role(role_name="SUPER_ADMIN", description="Full system configuration and audit access"),
        Role(role_name="ADMIN", description="Campus and resource administration"),
        Role(role_name="TEACHER", description="Course session and live attendance control"),
        Role(role_name="STUDENT", description="Personal attendance records viewer"),
        Role(role_name="DEVICE_OPERATOR", description="Attendance camera unit operator")
    ]
    db.add_all(roles)

    # 2. Users
    pwd_admin = get_password_hash("admin123")
    pwd_teacher = get_password_hash("teacher123")
    pwd_student = get_password_hash("student123")
    pwd_operator = get_password_hash("operator123")

    u_super = User(username="superadmin", email="superadmin@institution.edu", hashed_password=pwd_admin, role="SUPER_ADMIN", full_name="Super Administrator")
    u_admin = User(username="admin", email="admin@institution.edu", hashed_password=pwd_admin, role="ADMIN", full_name="Campus Admin")
    u_prof_john = User(username="prof_john", email="john.miller@institution.edu", hashed_password=pwd_teacher, role="TEACHER", full_name="Dr. John Miller")
    u_prof_sarah = User(username="prof_sarah", email="sarah.connor@institution.edu", hashed_password=pwd_teacher, role="TEACHER", full_name="Dr. Sarah Connor")
    u_alice = User(username="alice", email="alice.j@student.edu", hashed_password=pwd_student, role="STUDENT", full_name="Alice Johnson")
    u_bob = User(username="bob", email="bob.s@student.edu", hashed_password=pwd_student, role="STUDENT", full_name="Bob Smith")
    u_charlie = User(username="charlie", email="charlie.d@student.edu", hashed_password=pwd_student, role="STUDENT", full_name="Charlie Davis")
    u_operator = User(username="operator1", email="operator1@institution.edu", hashed_password=pwd_operator, role="DEVICE_OPERATOR", full_name="Camera Operator 1")

    db.add_all([u_super, u_admin, u_prof_john, u_prof_sarah, u_alice, u_bob, u_charlie, u_operator])
    db.flush()

    # 3. Departments
    dept_cs = Department(name="Computer Science & Engineering", code="CSE")
    dept_ece = Department(name="Electronics & Communication", code="ECE")
    dept_it = Department(name="Information Technology", code="IT")
    db.add_all([dept_cs, dept_ece, dept_it])
    db.flush()

    # 4. Sections
    sec_a = Section(department_id=dept_cs.id, academic_year="2025-2026", semester=4, section_name="Section A")
    sec_b = Section(department_id=dept_cs.id, academic_year="2025-2026", semester=4, section_name="Section B")
    db.add_all([sec_a, sec_b])
    db.flush()

    # 5. Rooms
    room_lab = Room(building="Tech Tower", room_number="Lab 401", capacity=45)
    room_hall = Room(building="Main Academic Block", room_number="Hall 202", capacity=90)
    db.add_all([room_lab, room_hall])
    db.flush()

    # 6. Teachers
    t_john = Teacher(user_id=u_prof_john.id, employee_id="EMP101", name="Dr. John Miller", email="john.miller@institution.edu", department_id=dept_cs.id, designation="Professor")
    t_sarah = Teacher(user_id=u_prof_sarah.id, employee_id="EMP102", name="Dr. Sarah Connor", email="sarah.connor@institution.edu", department_id=dept_cs.id, designation="Associate Professor")
    db.add_all([t_john, t_sarah])
    db.flush()

    # 7. Students
    s_alice = Student(user_id=u_alice.id, roll_number="CS2026001", name="Alice Johnson", email="alice.j@student.edu", department_id=dept_cs.id, section_id=sec_a.id, semester=4, contact_number="+1-555-0101")
    s_bob = Student(user_id=u_bob.id, roll_number="CS2026002", name="Bob Smith", email="bob.s@student.edu", department_id=dept_cs.id, section_id=sec_a.id, semester=4, contact_number="+1-555-0102")
    s_charlie = Student(user_id=u_charlie.id, roll_number="CS2026003", name="Charlie Davis", email="charlie.d@student.edu", department_id=dept_cs.id, section_id=sec_a.id, semester=4, contact_number="+1-555-0103")
    db.add_all([s_alice, s_bob, s_charlie])
    db.flush()

    # 8. Courses
    c_net = Course(department_id=dept_cs.id, course_code="CS401", course_name="Advanced Computer Networks", credits=4, semester=4)
    c_ai = Course(department_id=dept_cs.id, course_code="CS403", course_name="Artificial Intelligence & Vision", credits=4, semester=4)
    db.add_all([c_net, c_ai])
    db.flush()

    # 9. Course Offerings
    off_net = CourseOffering(course_id=c_net.id, teacher_id=t_john.id, section_id=sec_a.id, academic_year="2025-2026", semester=4)
    off_ai = CourseOffering(course_id=c_ai.id, teacher_id=t_sarah.id, section_id=sec_a.id, academic_year="2025-2026", semester=4)
    db.add_all([off_net, off_ai])
    db.flush()

    # 10. Enrollments
    e1 = Enrollment(course_offering_id=off_net.id, student_id=s_alice.id)
    e2 = Enrollment(course_offering_id=off_net.id, student_id=s_bob.id)
    e3 = Enrollment(course_offering_id=off_net.id, student_id=s_charlie.id)
    e4 = Enrollment(course_offering_id=off_ai.id, student_id=s_alice.id)
    e5 = Enrollment(course_offering_id=off_ai.id, student_id=s_charlie.id)
    db.add_all([e1, e2, e3, e4, e5])

    # 11. Devices
    dev1 = Device(name="Lab 401 AI Camera", device_code="CAM-LAB401", room_id=room_lab.id, ip_address="192.168.1.101", status="ONLINE", last_heartbeat=datetime.utcnow(), software_version="v1.2.0")
    dev2 = Device(name="Hall 202 High-Res Dome", device_code="CAM-LH202", room_id=room_hall.id, ip_address="192.168.1.102", status="ONLINE", last_heartbeat=datetime.utcnow(), software_version="v1.2.0")
    db.add_all([dev1, dev2])
    db.flush()

    # 12. Active Attendance Session
    today_str = date.today().isoformat()
    sess1 = AttendanceSession(
        course_offering_id=off_net.id,
        room_id=room_lab.id,
        teacher_id=t_john.id,
        title="CS401 Lecture 14: Network Routing Algorithms",
        date=today_str,
        start_time=datetime.utcnow(),
        grace_period_minutes=10,
        status="ACTIVE"
    )
    db.add(sess1)
    db.flush()

    # 13. Face Templates for Alice and Bob (normalized 128-d sample vectors)
    np.random.seed(42)
    vec_alice = np.random.normal(0.5, 0.2, 128)
    vec_alice = (vec_alice / np.linalg.norm(vec_alice)).tolist()
    ft_alice = FaceTemplate(student_id=s_alice.id, embedding=json.dumps(vec_alice), quality_score=0.92, is_active=True)

    vec_bob = np.random.normal(-0.5, 0.2, 128)
    vec_bob = (vec_bob / np.linalg.norm(vec_bob)).tolist()
    ft_bob = FaceTemplate(student_id=s_bob.id, embedding=json.dumps(vec_bob), quality_score=0.88, is_active=True)
    db.add_all([ft_alice, ft_bob])

    # 14. Initial Attendance Record for Alice
    rec1 = AttendanceRecord(
        session_id=sess1.id,
        student_id=s_alice.id,
        status="PRESENT",
        marked_at=datetime.utcnow(),
        verification_method="FACE_RECOGNITION",
        confidence_score=0.895,
        notes="Automated face recognition at entrance"
    )
    db.add(rec1)

    # 15. Initial Audit Log
    audit1 = AuditLog(
        user_id=u_admin.id,
        action="SYSTEM_INIT",
        entity_type="System",
        entity_id=1,
        reason="System initialized with baseline academic seed data",
        timestamp=datetime.utcnow()
    )
    db.add(audit1)

    db.commit()
    db.close()
    print("Database seeding completed successfully!")

if __name__ == "__main__":
    seed_database()
