"""
database.py
Database connection configuration and session management using SQLAlchemy and SQLite.
Creates the database engine, provides the SessionLocal factory, and exposes the get_db() dependency.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Task

# Resolve repo root directory and database path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "animatrix.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# create_engine initializes the connection pool and dialect.
# check_same_thread=False is required for SQLite when used in multi-threaded
# applications like FastAPI, allowing separate threads to share the engine safely.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# SessionLocal is a factory class producing database sessions.
# autocommit=False ensures transactions are controlled explicitly.
# autoflush=False avoids premature flushes before commit.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    FastAPI dependency that provides a transactional database session per request.
    Yields the session to the route handler and guarantees session closure in the finally block.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initializes database tables on application startup.
    Also handles server crash / restart recovery:
    Any tasks that were left in 'processing' status are marked as 'failed'
    because in-memory background tasks do not survive a server restart.
    """
    # Create all tables defined in models.py if they do not exist
    Base.metadata.create_all(bind=engine)

    # Clean up orphaned tasks that were interrupted by a restart
    db = SessionLocal()
    try:
        interrupted_tasks = db.query(Task).filter(Task.status == "processing").all()
        if interrupted_tasks:
            for task in interrupted_tasks:
                task.status = "failed"
                task.error = "Server restarted during generation"
            db.commit()
            print(f"[Database] Cleaned up {len(interrupted_tasks)} interrupted tasks from previous run.")
    except Exception as e:
        print(f"[Database] Error checking interrupted tasks on startup: {e}")
        db.rollback()
    finally:
        db.close()

