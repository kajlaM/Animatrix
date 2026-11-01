"""
models.py
Defines SQLAlchemy database models for Users and Animation Tasks.
Designed to be simple, readable, and heavily commented for interview explanation.
"""

import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

# Base class for declarative class definitions
Base = declarative_base()


class User(Base):
    """
    User Model
    Stores registered user accounts, their credentials, and links to tasks they created.
    """
    __tablename__ = "users"

    # Unique integer ID for each user
    id = Column(Integer, primary_key=True, index=True)

    # Unique username for logging in (indexed for fast query lookup)
    username = Column(String(50), unique=True, index=True, nullable=False)

    # Securely hashed password (never stored as plain text)
    hashed_password = Column(String(255), nullable=False)

    # One-to-many relationship: One user can have many animation tasks
    # back_populates links this to the 'owner' field in the Task model
    tasks = relationship("Task", back_populates="owner", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User id={self.id} username='{self.username}'>"


class Task(Base):
    """
    Task Model
    Represents an animation generation job initiated by a user.
    Tracks generation status, the prompt, generated Manim code,
    safe local video path, public API video URL, and any errors encountered.
    """
    __tablename__ = "tasks"

    # Unique UUID string primary key (e.g. 'c2b4a1...')
    id = Column(String(36), primary_key=True, index=True)

    # Foreign key referencing the user who owns this task
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # The natural language animation prompt provided by the user
    prompt = Column(String(1000), nullable=False)

    # Generation lifecycle status: "pending", "processing", "completed", or "failed"
    status = Column(String(20), default="pending", nullable=False)

    # Accessible API URL for the finished video (e.g. /api/videos/{task_id})
    video_url = Column(String(255), nullable=True)

    # Absolute safe server path to the rendered MP4 file on disk
    # Storing this server-side prevents arbitrary path traversal attacks
    video_path = Column(String(500), nullable=True)

    # The Python/Manim code produced by the Gemini model
    code = Column(Text, nullable=True)

    # Short readable error summary if generation or rendering failed
    error = Column(Text, nullable=True)

    # Timestamp when the task was queued (timezone-aware UTC)
    created_at = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False
    )

    # Relationship back to the User model
    owner = relationship("User", back_populates="tasks")

    def __repr__(self):
        return f"<Task id='{self.id}' user_id={self.user_id} status='{self.status}'>"

