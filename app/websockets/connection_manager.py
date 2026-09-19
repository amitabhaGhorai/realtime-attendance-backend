"""WebSocket Connection and Broadcast Manager for Real-Time Attendance."""
import json
from typing import Dict, List, Optional
from fastapi import WebSocket

class AttendanceConnectionManager:
    def __init__(self):
        # Maps session_id -> list of WebSockets
        self.session_rooms: Dict[int, List[WebSocket]] = {}
        # Global dashboard listeners (admins, general monitors)
        self.global_listeners: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, session_id: Optional[int] = None):
        await websocket.accept()
        if session_id is not None:
            if session_id not in self.session_rooms:
                self.session_rooms[session_id] = []
            self.session_rooms[session_id].append(websocket)
        else:
            self.global_listeners.append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: Optional[int] = None):
        if session_id is not None and session_id in self.session_rooms:
            if websocket in self.session_rooms[session_id]:
                self.session_rooms[session_id].remove(websocket)
            if not self.session_rooms[session_id]:
                del self.session_rooms[session_id]
        elif websocket in self.global_listeners:
            self.global_listeners.remove(websocket)

    async def broadcast_to_session(self, session_id: int, message: dict):
        """Broadcasts an event to all subscribers listening to this attendance session."""
        text_data = json.dumps(message, default=str)
        dead_connections = []
        if session_id in self.session_rooms:
            for ws in self.session_rooms[session_id]:
                try:
                    await ws.send_text(text_data)
                except Exception:
                    dead_connections.append(ws)
            for dead in dead_connections:
                self.session_rooms[session_id].remove(dead)

        # Also send to global listeners
        await self.broadcast_global(message)

    async def broadcast_global(self, message: dict):
        """Broadcasts an event to global dashboard listeners."""
        text_data = json.dumps(message, default=str)
        dead_connections = []
        for ws in self.global_listeners:
            try:
                await ws.send_text(text_data)
            except Exception:
                dead_connections.append(ws)
        for dead in dead_connections:
            self.global_listeners.remove(dead)

ws_manager = AttendanceConnectionManager()
