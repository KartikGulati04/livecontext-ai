"""Connector registry and factory for managing user integrations."""
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Integration
from app.core.security import decrypt_credentials
from app.connectors.base import BaseConnector
from app.connectors.notion import NotionConnector
from app.connectors.jira import JiraConnector
from app.connectors.gmail import GmailConnector


async def get_user_connector(db: AsyncSession, user_id: str, provider: str) -> Optional[BaseConnector]:
    """
    Fetches the configured integration for a user and instantiates the connector.
    Returns None if not configured or inactive.
    """
    stmt = select(Integration).where(
        Integration.user_id == user_id,
        Integration.provider == provider,
        Integration.is_active == True
    )
    result = await db.execute(stmt)
    integration = result.scalar_one_or_none()
    if not integration or not integration.credentials_encrypted:
        return None

    creds = decrypt_credentials(integration.credentials_encrypted)
    config = integration.config or {}

    if provider == "notion":
        api_key = creds.get("api_key")
        if api_key:
            return NotionConnector(api_key=api_key)
    elif provider == "jira":
        domain = config.get("domain") or creds.get("domain")
        email = creds.get("email")
        api_token = creds.get("api_token")
        if domain and email and api_token:
            return JiraConnector(domain=domain, email=email, api_token=api_token)
    elif provider == "gmail":
        token = creds.get("access_token")
        if token:
            return GmailConnector(access_token=token)

    return None
