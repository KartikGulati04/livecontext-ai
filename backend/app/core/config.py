"""Application configuration settings."""
from typing import List, Optional
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "LiveContext AI"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str = "livecontext-super-secret-dev-jwt-key-2026-change-in-prod"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ALGORITHM: str = "HS256"

    # Database
    # Default to a local SQLite database for instant zero-dependency execution
    # Can be overridden by PostgreSQL URL: postgresql+asyncpg://user:pass@localhost:5432/livecontext
    DATABASE_URL: str = "sqlite+aiosqlite:///./livecontext.db"
    ENABLE_PGVECTOR: bool = False

    # AI Providers
    DEFAULT_LLM_PROVIDER: str = "gemini"  # "gemini" | "openai" | "mock"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-pro"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"
    
    # Retrieval & Embeddings
    EMBEDDING_PROVIDER: str = "auto"  # "gemini" | "openai" | "local" | "auto"
    EMBEDDING_DIMENSION: int = 768  # standard for text-embedding-004 or local fallback
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    RETRIEVAL_TOP_K: int = 5
    RETRIEVAL_SIMILARITY_THRESHOLD: float = 0.45

    # Storage paths
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

    # Agent Limits
    AGENT_MAX_ITERATIONS: int = 3
    AGENT_MAX_TOOL_CALLS: int = 8
    AGENT_EXECUTION_TIMEOUT_SECONDS: int = 60


settings = Settings()
