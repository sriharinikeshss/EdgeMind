from sqlalchemy import Column, String, DateTime, Enum, ForeignKey
from sqlalchemy.orm import declarative_base
import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    role = Column(String, nullable=False)

class Task(Base):
    __tablename__ = 'tasks'
    id = Column(String, primary_key=True)
    description = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class TaskStep(Base):
    __tablename__ = 'task_steps'
    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey('tasks.id'))
    action = Column(String)
    result = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Artifact(Base):
    __tablename__ = 'artifacts'
    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey('tasks.id'))
    filename = Column(String, nullable=False)
    file_hash = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
