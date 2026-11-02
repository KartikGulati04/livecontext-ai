"""SQLAlchemy Database Models for LiveContext AI."""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from app.db.session import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    integrations = relationship("Integration", back_populates="user", cascade="all, delete-orphan")
    memories = relationship("Memory", back_populates="user", cascade="all, delete-orphan")
    traces = relationship("ExecutionTrace", back_populates="user", cascade="all, delete-orphan")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False, default="New Conversation")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")
    traces = relationship("ExecutionTrace", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False)  # "user" | "assistant" | "system"
    content = Column(Text, nullable=False)
    citations = Column(JSON, nullable=True)  # List of citations [{source_id, title, url, excerpt, chunk_id}]
    verification_status = Column(JSON, nullable=True)  # Verification report
    execution_plan = Column(JSON, nullable=True)  # Plan summary
    created_at = Column(DateTime, default=utc_now)

    conversation = relationship("Conversation", back_populates="messages")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # pdf, txt, md
    file_size_bytes = Column(Integer, nullable=False)
    content_hash = Column(String, nullable=False, index=True)
    status = Column(String, default="pending")  # pending, indexing, ready, failed
    error_message = Column(Text, nullable=True)
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    user = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON, nullable=True)  # {page: 1, section: "Intro", ...}
    embedding = Column(JSON, nullable=True)  # Stored as list of floats for portability
    created_at = Column(DateTime, default=utc_now)

    document = relationship("Document", back_populates="chunks")


class Integration(Base):
    __tablename__ = "integrations"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String, nullable=False)  # "notion", "jira", "gmail"
    is_active = Column(Boolean, default=True)
    credentials_encrypted = Column(Text, nullable=True)  # Encrypted JSON or token
    config = Column(JSON, nullable=True)  # {domain: "example.atlassian.net", project_key: "PROJ", ...}
    last_sync_at = Column(DateTime, nullable=True)
    sync_status = Column(String, default="idle")  # idle, syncing, error, connected
    sync_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    user = relationship("User", back_populates="integrations")


class Memory(Base):
    __tablename__ = "memories"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    memory_type = Column(String, default="user_preference")  # preference, project_context, fact
    provenance = Column(String, default="user_stated")  # explicit_input, assistant_approved
    is_active = Column(Boolean, default=True)
    user_consented = Column(Boolean, default=True)
    embedding = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    user = relationship("User", back_populates="memories")


class ExecutionTrace(Base):
    __tablename__ = "execution_traces"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True)
    query = Column(Text, nullable=False)
    stages = Column(JSON, nullable=False)  # [{stage: "planner", duration_ms: 120, status: "success", ...}]
    tool_calls = Column(JSON, nullable=False)  # [{tool: "jira_search", inputs: {}, results_count: 3, latency_ms: 450}]
    model_provider = Column(String, nullable=True)
    model_name = Column(String, nullable=True)
    token_usage = Column(JSON, nullable=True)  # {prompt_tokens: 450, completion_tokens: 180, total_tokens: 630}
    total_latency_ms = Column(Float, nullable=False)
    created_at = Column(DateTime, default=utc_now)

    user = relationship("User", back_populates="traces")
    conversation = relationship("Conversation", back_populates="traces")
