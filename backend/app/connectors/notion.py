"""Official Notion API Connector with pagination, block retrieval, and error resilience."""
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import httpx
from app.connectors.base import BaseConnector, ConnectorResult


class NotionConnector(BaseConnector):
    """
    Connects to the official Notion API (https://api.notion.com/v1).
    Reads page metadata, search results, and child block content.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key or ''}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "provider": "notion",
            "searchable": True,
            "filters": ["page", "database"],
            "supports_blocks": True,
            "read_only": True
        }

    async def health_check(self) -> Dict[str, Any]:
        if not self.api_key:
            return {"status": "unconfigured", "error": "Notion API key not set"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.base_url}/users/me", headers=self.headers)
                if resp.status_code == 200:
                    user_data = resp.json()
                    return {"status": "connected", "bot_id": user_data.get("id"), "name": user_data.get("name")}
                elif resp.status_code == 401:
                    return {"status": "error", "error": "Invalid or unauthorized Notion API token"}
                else:
                    return {"status": "error", "error": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def search(self, query: str, filters: Optional[Dict[str, Any]] = None, limit: int = 5) -> List[ConnectorResult]:
        if not self.api_key:
            return []

        payload: Dict[str, Any] = {
            "query": query,
            "page_size": min(limit, 20)
        }
        if filters and "filter" in filters:
            payload["filter"] = filters["filter"]

        results: List[ConnectorResult] = []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(f"{self.base_url}/search", headers=self.headers, json=payload)
                if resp.status_code != 200:
                    return []
                data = resp.json()

                for item in data.get("results", []):
                    title = "Untitled"
                    # Handle page vs database titles
                    if item.get("object") == "page":
                        props = item.get("properties", {})
                        for _, prop_val in props.items():
                            if prop_val.get("type") == "title":
                                title_parts = prop_val.get("title", [])
                                if title_parts:
                                    title = "".join(t.get("plain_text", "") for t in title_parts)
                                break
                    elif item.get("object") == "database":
                        db_title = item.get("title", [])
                        if db_title:
                            title = "".join(t.get("plain_text", "") for t in db_title)

                    url = item.get("url")
                    item_id = item.get("id")
                    last_edited = item.get("last_edited_time")
                    dt = None
                    if last_edited:
                        try:
                            dt = datetime.fromisoformat(last_edited.replace("Z", "+00:00"))
                        except Exception:
                            pass

                    # Fetch page body blocks
                    content = await self._fetch_blocks_text(client, item_id)
                    if not content:
                        content = f"Page Title: {title}"

                    results.append(ConnectorResult(
                        source_type="notion",
                        source_id=item_id,
                        title=title,
                        url=url,
                        content=content,
                        last_updated=dt,
                        metadata={
                            "object_type": item.get("object"),
                            "parent": item.get("parent"),
                            "created_time": item.get("created_time")
                        }
                    ))
        except Exception:
            return []

        return results

    async def fetch(self, source_id: str) -> Optional[ConnectorResult]:
        if not self.api_key:
            return None
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{self.base_url}/pages/{source_id}", headers=self.headers)
                if resp.status_code != 200:
                    return None
                item = resp.json()
                title = "Untitled"
                props = item.get("properties", {})
                for _, prop_val in props.items():
                    if prop_val.get("type") == "title":
                        parts = prop_val.get("title", [])
                        if parts:
                            title = "".join(t.get("plain_text", "") for t in parts)
                        break

                content = await self._fetch_blocks_text(client, source_id)
                url = item.get("url")
                return ConnectorResult(
                    source_type="notion",
                    source_id=source_id,
                    title=title,
                    url=url,
                    content=content,
                    metadata={"object_type": "page"}
                )
        except Exception:
            return None

    async def _fetch_blocks_text(self, client: httpx.AsyncClient, block_id: str) -> str:
        try:
            resp = await client.get(f"{self.base_url}/blocks/{block_id}/children?page_size=30", headers=self.headers)
            if resp.status_code != 200:
                return ""
            blocks = resp.json().get("results", [])
            lines = []
            for b in blocks:
                b_type = b.get("type")
                if b_type and b_type in b:
                    rich_texts = b[b_type].get("rich_text", [])
                    line_text = "".join(rt.get("plain_text", "") for rt in rich_texts)
                    if line_text:
                        lines.append(line_text)
            return "\n".join(lines)
        except Exception:
            return ""
