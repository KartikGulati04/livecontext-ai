"""Official Google Gmail API Connector using read-only scopes and OAuth tokens."""
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import base64
import httpx
from app.connectors.base import BaseConnector, ConnectorResult


class GmailConnector(BaseConnector):
    """
    Connects to the official Google Gmail REST API v1.
    Uses read-only scope (https://www.googleapis.com/auth/gmail.readonly).
    Never requests passwords or write permissions.
    """
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token
        self.base_url = "https://gmail.googleapis.com/gmail/v1/users/me"
        self.headers = {
            "Authorization": f"Bearer {access_token or ''}",
            "Accept": "application/json"
        }

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "provider": "gmail",
            "searchable": True,
            "read_only": True,
            "supports_queries": True,
            "scopes": ["https://www.googleapis.com/auth/gmail.readonly"]
        }

    async def health_check(self) -> Dict[str, Any]:
        if not self.access_token:
            return {"status": "unconfigured", "error": "Gmail OAuth access token not set"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.base_url}/profile", headers=self.headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "status": "connected",
                        "email": data.get("emailAddress"),
                        "messages_total": data.get("messagesTotal")
                    }
                elif resp.status_code == 401:
                    return {"status": "error", "error": "Invalid or expired Google OAuth access token"}
                else:
                    return {"status": "error", "error": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def search(self, query: str, filters: Optional[Dict[str, Any]] = None, limit: int = 5) -> List[ConnectorResult]:
        if not self.access_token:
            return []

        results: List[ConnectorResult] = []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.base_url}/messages",
                    headers=self.headers,
                    params={"q": query, "maxResults": min(limit, 10)}
                )
                if resp.status_code != 200:
                    return []

                msg_list = resp.json().get("messages", [])
                for msg_summary in msg_list:
                    msg_id = msg_summary.get("id")
                    item = await self.fetch(msg_id)
                    if item:
                        results.append(item)
        except Exception:
            return []

        return results

    async def fetch(self, source_id: str) -> Optional[ConnectorResult]:
        if not self.access_token:
            return None
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.base_url}/messages/{source_id}",
                    headers=self.headers,
                    params={"format": "full"}
                )
                if resp.status_code != 200:
                    return None

                data = resp.json()
                headers = data.get("payload", {}).get("headers", [])
                header_map = {h.get("name", "").lower(): h.get("value", "") for h in headers}

                subject = header_map.get("subject", "No Subject")
                sender = header_map.get("from", "Unknown Sender")
                date_str = header_map.get("date")

                dt = None
                if date_str:
                    try:
                        # Parse timestamp if available
                        internal_date = data.get("internalDate")
                        if internal_date:
                            dt = datetime.fromtimestamp(int(internal_date) / 1000, tz=timezone.utc)
                    except Exception:
                        pass

                body = self._extract_body(data.get("payload", {}))
                content = (
                    f"Subject: {subject}\n"
                    f"From: {sender}\n"
                    f"Snippet: {data.get('snippet', '')}\n\n"
                    f"{body}"
                )

                return ConnectorResult(
                    source_type="gmail",
                    source_id=source_id,
                    title=f"[Email] {subject}",
                    url=f"https://mail.google.com/mail/u/0/#inbox/{source_id}",
                    content=content,
                    last_updated=dt,
                    metadata={
                        "from": sender,
                        "subject": subject,
                        "thread_id": data.get("threadId"),
                        "labels": data.get("labelIds", [])
                    }
                )
        except Exception:
            return None

    def _extract_body(self, payload: Dict[str, Any]) -> str:
        body_data = payload.get("body", {}).get("data")
        if body_data:
            try:
                return base64.urlsafe_b64decode(body_data.encode("utf-8")).decode("utf-8", errors="replace")
            except Exception:
                pass

        parts = payload.get("parts", [])
        for part in parts:
            if part.get("mimeType") == "text/plain":
                p_data = part.get("body", {}).get("data")
                if p_data:
                    try:
                        return base64.urlsafe_b64decode(p_data.encode("utf-8")).decode("utf-8", errors="replace")
                    except Exception:
                        pass
        return ""
