import os
import sys

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.database import sync_engine, Base, SyncSessionLocal
from app.models import User
from app.seed import seed_database

# Initialize database schema and seeds on cold start if needed
try:
    Base.metadata.create_all(bind=sync_engine)
    db = SyncSessionLocal()
    if not db.query(User).filter_by(username="admin").first():
        seed_database()
    db.close()
except Exception as e:
    print("Startup DB init note:", e)