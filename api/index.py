import os
import sys
import traceback

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

try:
    from app.main import app as main_app
    app = main_app
except Exception as exc:
    err_traceback = traceback.format_exc()
    print("FATAL COLD START ERROR:", err_traceback)
    
    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse
    
    app = FastAPI()
    
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
    async def fallback_debug(path: str = ""):
        return PlainTextResponse(
            f"Vercel Serverless Python Cold Start Exception:\n\n{err_traceback}",
            status_code=500
        )