"""Integrations configuration, connection testing, and synchronization endpoints."""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel
from datetime import datetime, timezone

from app.db.session import get_db
from app.db.models import User, Integration
from app.api.deps import get_current_user
from app.core.security import encrypt_credentials, decrypt_credentials
from app.connectors.notion import NotionConnector
from app.connectors.jira import JiraConnector
from app.connectors.gmail import GmailConnector

router = APIRouter()


class IntegrationConfigInput(BaseModel):
    provider: str  # "notion" | "jira" | "gmail"
    credentials: Dict[str, Any]  # {"api_key": "..."} or {"domain": "...", "email": "...", "api_token": "..."} or {"access_token": "..."}
    config: Optional[Dict[str, Any]] = None


class IntegrationStatusResponse(BaseModel):
    id: str
    provider: str
    is_active: bool
    sync_status: str
    last_sync_at: Optional[str]
    sync_error: Optional[str]
    capabilities: Dict[str, Any]


@router.get("", response_model=List[IntegrationStatusResponse])
async def list_integrations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Integration).where(Integration.user_id == user.id)
    integrations = (await db.execute(stmt)).scalars().all()
    res = []
    for ig in integrations:
        cap = {}
        if ig.provider == "notion":
            cap = NotionConnector().get_capabilities()
        elif ig.provider == "jira":
            cap = JiraConnector().get_capabilities()
        elif ig.provider == "gmail":
            cap = GmailConnector().get_capabilities()

        res.append(IntegrationStatusResponse(
            id=ig.id,
            provider=ig.provider,
            is_active=ig.is_active,
            sync_status=ig.sync_status,
            last_sync_at=ig.last_sync_at.isoformat() if ig.last_sync_at else None,
            sync_error=ig.sync_error,
            capabilities=cap
        ))
    return res


@router.post("/configure", response_model=IntegrationStatusResponse)
async def configure_integration(
    input_data: IntegrationConfigInput,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    provider = input_data.provider.lower()
    if provider not in ["notion", "jira", "gmail"]:
        raise HTTPException(status_code=400, detail="Unsupported provider. Choose 'notion', 'jira', or 'gmail'.")

    # Validate live credentials before persisting
    status_str = "connected"
    err_str = None
    if provider == "notion":
        conn = NotionConnector(api_key=input_data.credentials.get("api_key"))
        check = await conn.health_check()
        if check["status"] != "connected":
            status_str = "error"
            err_str = check.get("error", "Failed to connect to Notion")
    elif provider == "jira":
        conn = JiraConnector(
            domain=input_data.credentials.get("domain"),
            email=input_data.credentials.get("email"),
            api_token=input_data.credentials.get("api_token")
        )
        check = await conn.health_check()
        if check["status"] != "connected":
            status_str = "error"
            err_str = check.get("error", "Failed to connect to Jira")
    elif provider == "gmail":
        conn = GmailConnector(access_token=input_data.credentials.get("access_token"))
        check = await conn.health_check()
        if check["status"] != "connected":
            status_str = "error"
            err_str = check.get("error", "Failed to connect to Gmail")

    # Find existing or create new
    stmt = select(Integration).where(Integration.user_id == user.id, Integration.provider == provider)
    ig = (await db.execute(stmt)).scalar_one_or_none()
    if not ig:
        ig = Integration(user_id=user.id, provider=provider)
        db.add(ig)

    ig.credentials_encrypted = encrypt_credentials(input_data.credentials)
    ig.config = input_data.config or {}
    ig.is_active = True
    ig.sync_status = status_str
    ig.sync_error = err_str
    ig.last_sync_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(ig)

    cap = NotionConnector().get_capabilities() if provider == "notion" else JiraConnector().get_capabilities()

    return IntegrationStatusResponse(
        id=ig.id,
        provider=ig.provider,
        is_active=ig.is_active,
        sync_status=ig.sync_status,
        last_sync_at=ig.last_sync_at.isoformat() if ig.last_sync_at else None,
        sync_error=ig.sync_error,
        capabilities=cap
    )


@router.delete("/{provider}")
async def disconnect_integration(
    provider: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = delete(Integration).where(Integration.user_id == user.id, Integration.provider == provider)
    res = await db.execute(stmt)
    await db.commit()
    return {"message": f"Integration {provider} disconnected"}
