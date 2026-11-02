"""FastAPI application entrypoint for LiveContext AI."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.session import init_db
from app.api.auth import router as auth_router
from app.api.conversations import router as conversations_router
from app.api.documents import router as documents_router
from app.api.integrations import router as integrations_router
from app.api.memory import router as memory_router
from app.api.observability import router as observability_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite/Postgres tables on startup
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Agentic RAG Over Live Data With Memory, Citations, and Observability.",
    lifespan=lifespan
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API v1 Routers
app.include_router(auth_router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["Auth"])
app.include_router(conversations_router, prefix=f"{settings.API_V1_PREFIX}/conversations", tags=["Conversations"])
app.include_router(documents_router, prefix=f"{settings.API_V1_PREFIX}/documents", tags=["Documents"])
app.include_router(integrations_router, prefix=f"{settings.API_V1_PREFIX}/integrations", tags=["Integrations"])
app.include_router(memory_router, prefix=f"{settings.API_V1_PREFIX}/memory", tags=["Memory"])
app.include_router(observability_router, prefix=f"{settings.API_V1_PREFIX}/observability", tags=["Observability"])


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }
