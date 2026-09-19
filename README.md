# Real-Time Attendance Management System — Backend API & AI Engine

A production-grade, centralized **FastAPI** backend powering camera-based face recognition attendance tracking, presentation attack anti-spoofing, real-time WebSocket telemetry, and multi-tier role-based access control.

---

## Architecture & Features

- **Framework**: FastAPI (Asynchronous Python 3)
- **Database & ORM**: SQLAlchemy 2.0 with async engine (`aiosqlite`) and sync migrations (`sqlite3` / `postgresql`)
- **Real-Time Communication**: Native WebSockets (`/ws/attendance`) broadcasting live scans and status overrides
- **AI Vision Pipeline**:
  - **OpenCV Face Detection**: Bounding box localization and facial feature alignment
  - **Laplacian Blur Quality Checker**: Rejects blurry frames before recognition
  - **Fourier Anti-Spoofing Filter**: Presentation attack detection analyzing frequency texture energy
  - **128-d L2 Normalized Embeddings**: Cosine distance template matching
- **Reporting**: ReportLab automated PDF ledger generation and RFC-4180 CSV export
- **Security & RBAC**: Salted bcrypt password hashing, JWT bearer tokens, and immutable audit logs

---

## Quick Setup & Launch

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Seed database
python -m app.seed

# 3. Run automated tests
python -m unittest tests/test_attendance.py

# 4. Start backend server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- **Swagger API Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check:** [http://localhost:8000/api/health](http://localhost:8000/api/health)
- **WebSocket Endpoint:** `ws://localhost:8000/ws/attendance`

---

## Default Credentials

| Role | Username | Password |
| :--- | :--- | :--- |
| **Super Admin** | `superadmin` | `admin123` |
| **Campus Admin** | `admin` | `admin123` |
| **Teacher (John)** | `prof_john` | `teacher123` |
| **Student (Alice)** | `alice` | `student123` |
| **Camera Operator** | `operator1` | `operator123` |
