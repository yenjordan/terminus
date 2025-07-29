from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base
from passlib.context import CryptContext
import secrets


# Use passlib with bcrypt without checking version
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False)
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user")  # Roles: "user", "admin", "moderator", "reviewer"
    is_superuser = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    reset_token = Column(String, unique=True, nullable=True)

    def verify_password(self, password: str) -> bool:
        """Check if a plain password matches the hashed password."""
        return pwd_context.verify(password, self.hashed_password)

    def set_password(self, password: str):
        """Hash and store a password."""
        self.hashed_password = pwd_context.hash(password)

    def generate_reset_token(self):
        """Generate a secure reset token."""
        self.reset_token = secrets.token_urlsafe(32)

    def clear_reset_token(self):
        """Clear password reset token after use."""
        self.reset_token = None

    # Relationships
    code_sessions = relationship("CodeSession", back_populates="user", cascade="all, delete-orphan")
    code_submissions = relationship(
        "CodeSubmission", back_populates="user", cascade="all, delete-orphan"
    )
    code_reviews = relationship(
        "CodeReview", back_populates="reviewer", cascade="all, delete-orphan"
    )


class CodeSession(Base):
    """User coding sessions/workspaces"""

    __tablename__ = "code_sessions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    last_accessed = Column(DateTime, default=func.now(), onupdate=func.now())
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="code_sessions")
    files = relationship("CodeFile", back_populates="session", cascade="all, delete-orphan")
    executions = relationship(
        "CodeExecution", back_populates="session", cascade="all, delete-orphan"
    )


class CodeFile(Base):
    """Files stored in user workspaces"""

    __tablename__ = "code_files"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    path = Column(String, nullable=False)  # Relative path within session
    content = Column(Text, nullable=False, default="")
    file_type = Column(String, nullable=False, default="python")  # python, text, etc.
    session_id = Column(Integer, ForeignKey("code_sessions.id"), nullable=False)
    size_bytes = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    session = relationship("CodeSession", back_populates="files")


class CodeExecution(Base):
    """Track code execution history"""

    __tablename__ = "code_executions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("code_sessions.id"), nullable=False)
    command = Column(Text, nullable=False)  #  command that was executed
    input_data = Column(Text, nullable=True)  # any input provided
    output = Column(Text, nullable=True)  # execution output
    error = Column(Text, nullable=True)  # error output if any
    exit_code = Column(Integer, nullable=True)  # exit code
    execution_time_ms = Column(Float, nullable=True)  # execution time in milliseconds
    memory_usage_mb = Column(Float, nullable=True)  # memory usage in MB
    status = Column(String, default="pending")  # pending, running, completed, failed, timeout
    created_at = Column(DateTime, default=func.now())

    # Relationships
    session = relationship("CodeSession", back_populates="executions")


class CodeSubmission(Base):
    """Code submissions for review"""

    __tablename__ = "code_submissions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(
        Integer, ForeignKey("code_sessions.id"), nullable=True
    )  # Optional link to session
    code_content = Column(Text, nullable=False)  # snapshot of code at submission
    files_snapshot = Column(JSON, nullable=True)  # JSON snapshot of all files
    status = Column(String, default="pending")  # pending, approved, rejected, revision_requested
    priority = Column(String, default="normal")  # low, normal, high, urgent
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="code_submissions")
    reviews = relationship("CodeReview", back_populates="submission", cascade="all, delete-orphan")


class CodeReview(Base):
    """Reviews for code submissions"""

    __tablename__ = "code_reviews"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("code_submissions.id"), nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, nullable=False)  # approved, rejected, revision_requested
    comments = Column(Text, nullable=True)
    feedback = Column(Text, nullable=True)

    # New quality assessment fields
    quality_before_edits = Column(Integer, nullable=True)  # 1-5 rating scale
    quality_after_edits = Column(Integer, nullable=True)  # 1-5 rating scale
    edits_made = Column(Text, nullable=True)  # description of edits made
    is_customer_ready = Column(Boolean, nullable=True)  # if task is good enough to send to customer

    review_time_minutes = Column(Float, nullable=True)  # time spent reviewing
    created_at = Column(DateTime, default=func.now())

    # Relationships
    submission = relationship("CodeSubmission", back_populates="reviews")
    reviewer = relationship("User", back_populates="code_reviews")
