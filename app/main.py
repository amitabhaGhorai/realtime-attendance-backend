"""FastAPI Application Main Entrypoint."""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.websockets.connection_manager import ws_manager

# Routers
from app.routers import (
    auth, academic, users, biometrics, sessions,
    attendance, recognition, reports, devices, audit
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize and seed database on startup for persistent/container environments (Render / Docker / Local)
    if not os.environ.get("VERCEL"):
        try:
            from app.seed import seed_database
            seed_database()
        except Exception as e:
            print("Startup DB initialization note:", e)
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Production-ready real-time camera face recognition attendance management platform.",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root Endpoint
@app.get("/")
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "status": "ONLINE",
        "documentation": "/docs",
        "health_check": "/api/health"
    }

# Mount API Routers
app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(academic.router, prefix=settings.API_PREFIX)
app.include_router(users.router, prefix=settings.API_PREFIX)
app.include_router(biometrics.router, prefix=settings.API_PREFIX)
app.include_router(sessions.router, prefix=settings.API_PREFIX)
app.include_router(attendance.router, prefix=settings.API_PREFIX)
app.include_router(recognition.router, prefix=settings.API_PREFIX)
app.include_router(reports.router, prefix=settings.API_PREFIX)
app.include_router(devices.router, prefix=settings.API_PREFIX)
app.include_router(audit.router, prefix=settings.API_PREFIX)

# WebSocket Real-Time Endpoint
@app.websocket("/ws/attendance")
async def websocket_attendance_global(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

@app.websocket("/ws/attendance/{session_id}")
async def websocket_attendance_session(websocket: WebSocket, session_id: int):
    await ws_manager.connect(websocket, session_id=session_id)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, session_id=session_id)

@app.get("/api/health")
async def health_check():
    return {
        "status": "HEALTHY",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "institution": settings.INSTITUTION_NAME
    }

# Optionally mount built frontend dist if available
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)