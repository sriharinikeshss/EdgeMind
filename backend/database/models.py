"""
SQLAlchemy ORM models for KAVACH.
Tables: users, tasks, task_steps, artifacts
"""
import uuid
import datetime
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Integer, Float
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)          # bcrypt hash
    role = Column(String, nullable=False, default="operator")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=_uuid)
    description = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="CREATED")  # Matches TaskStatus enum
    model_used = Column(String, nullable=True)                   # which LLM was called
    response = Column(Text, nullable=True)                       # raw model output
    grounding_score = Column(Float, nullable=True)                # Phase 8: claim-to-source grounding [0,1]
    validation_report = Column(Text, nullable=True)               # Phase 8: JSON {claims, unsupported, checks}
    retry_count = Column(Integer, nullable=False, default=0)      # Phase 8: replan attempts consumed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    steps = relationship("TaskStep", back_populates="task", cascade="all, delete-orphan")
    artifacts = relationship("Artifact", back_populates="task", cascade="all, delete-orphan")


class TaskStep(Base):
    __tablename__ = "task_steps"

    id = Column(String, primary_key=True, default=_uuid)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    action = Column(String, nullable=False)
    result = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    task = relationship("Task", back_populates="steps")


class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(String, primary_key=True, default=_uuid)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=True)
    file_hash = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    task = relationship("Task", back_populates="artifacts")


class ModelRoute(Base):
    __tablename__ = "model_routes"

    id = Column(String, primary_key=True, default=_uuid)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    task_type = Column(String, nullable=False)
    selected_model = Column(String, nullable=False)
    routing_reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id = Column(String, primary_key=True, default=_uuid)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    tool_name = Column(String, nullable=False)
    arguments = Column(Text, nullable=True)
    result = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="PENDING")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=_uuid)
    filename = Column(String, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    classification = Column(String, nullable=False, default="internal")  # Phase 9: public|internal|confidential|restricted
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=True)
    action = Column(String, nullable=False)
    details = Column(Text, nullable=True)
    prev_hash = Column(String, nullable=True)   # Phase 9: hash of the previous row (chain link)
    hash = Column(String, nullable=True)        # Phase 9: sha256(prev_hash + action + details + created_at)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Approval(Base):
    """Phase 9: human-approval gate for HIGH-risk tool calls."""
    __tablename__ = "approvals"

    id = Column(String, primary_key=True, default=_uuid)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    step_id = Column(String, nullable=False)
    tool_name = Column(String, nullable=False)
    arguments = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="PENDING")  # PENDING | APPROVED | REJECTED
    requested_by = Column(String, nullable=True)
    decided_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    decided_at = Column(DateTime, nullable=True)

