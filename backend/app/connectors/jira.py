"""Official Jira REST API Connector supporting JQL, issue details, and error handling."""
from typing import List, Dict, Any, Optional
from datetime import datetime
import base64
import httpx
from app.connectors.base import BaseConnector, ConnectorResult


class JiraConnector(BaseConnector):
    """
    Connects to Atlassian Jira Cloud REST API v3 (or v2).
    Requires domain (e.g. your-company.atlassian.net), email, and API token.
    """
    def __init__(self, domain: Optional[str] = None, email: Optional[str] = None, api_token: Optional[str] = None):
        self.domain = (domain or "").strip().rstrip("/")
        if self.domain and not self.domain.startswith("http"):
            self.domain = f"https://{self.domain}"
        self.email = email
        self.api_token = api_token

        auth_str = f"{email or ''}:{api_token or ''}"
        b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        self.headers = {
            "Authorization": f"Basic {b64_auth}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "provider": "jira",
            "searchable": True,
            "supports_jql": True,
            "read_only": True,
            "fields": ["summary", "description", "status", "priority", "assignee", "labels"]
        }

    async def health_check(self) -> Dict[str, Any]:
        if not self.domain or not self.email or not self.api_token:
            return {"status": "unconfigured", "error": "Jira domain, email, or API token missing"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.domain}/rest/api/3/myself", headers=self.headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return {"status": "connected", "display_name": data.get("displayName"), "email": data.get("emailAddress")}
                elif resp.status_code == 401:
                    return {"status": "error", "error": "Invalid Jira credentials or API token"}
                else:
                    return {"status": "error", "error": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def search(self, query: str, filters: Optional[Dict[str, Any]] = None, limit: int = 5) -> List[ConnectorResult]:
        if not self.domain or not self.email or not self.api_token:
            return []

        # If query looks like plain text, build standard JQL text search; otherwise use direct JQL
        jql = filters.get("jql") if filters and "jql" in filters else None
        if not jql:
            clean_q = query.replace('"', '\\"').strip()
            if clean_q:
                jql = f'text ~ "{clean_q}" order by updated desc'
            else:
                jql = "order by updated desc"

        results: List[ConnectorResult] = []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.domain}/rest/api/3/search",
                    headers=self.headers,
                    params={
                        "jql": jql,
                        "maxResults": min(limit, 20),
                        "fields": "summary,status,priority,assignee,updated,created,labels,description"
                    }
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()
                issues = data.get("issues", [])

                for issue in issues:
                    key = issue.get("key")
                    fields = issue.get("fields", {})
                    summary = fields.get("summary", "No Summary")
                    status = fields.get("status", {}).get("name", "Unknown")
                    priority = fields.get("priority", {}).get("name", "Medium")
                    assignee = fields.get("assignee", {}).get("displayName", "Unassigned") if fields.get("assignee") else "Unassigned"
                    updated_str = fields.get("updated")
                    dt = None
                    if updated_str:
                        try:
                            dt = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                        except Exception:
                            pass

                    # Extract description from Atlassian Document Format (ADF) or plain text
                    desc_text = self._extract_adf_text(fields.get("description"))

                    content = (
                        f"Issue Key: {key}\n"
                        f"Summary: {summary}\n"
                        f"Status: {status}\n"
                        f"Priority: {priority}\n"
                        f"Assignee: {assignee}\n"
                        f"Description: {desc_text}"
                    )

                    results.append(ConnectorResult(
                        source_type="jira",
                        source_id=key,
                        title=f"[{key}] {summary}",
                        url=f"{self.domain}/browse/{key}",
                        content=content,
                        last_updated=dt,
                        metadata={
                            "status": status,
                            "priority": priority,
                            "assignee": assignee,
                            "labels": fields.get("labels", [])
                        }
                    ))
        except Exception:
            return []

        return results

    async def fetch(self, source_id: str) -> Optional[ConnectorResult]:
        if not self.domain or not self.email or not self.api_token:
            return None
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{self.domain}/rest/api/3/issue/{source_id}", headers=self.headers)
                if resp.status_code != 200:
                    return None
                issue = resp.json()
                key = issue.get("key")
                fields = issue.get("fields", {})
                summary = fields.get("summary", "")
                status = fields.get("status", {}).get("name", "Unknown")
                priority = fields.get("priority", {}).get("name", "Medium")
                assignee = fields.get("assignee", {}).get("displayName", "Unassigned") if fields.get("assignee") else "Unassigned"
                desc_text = self._extract_adf_text(fields.get("description"))

                content = (
                    f"Issue Key: {key}\n"
                    f"Summary: {summary}\n"
                    f"Status: {status}\n"
                    f"Priority: {priority}\n"
                    f"Assignee: {assignee}\n"
                    f"Description: {desc_text}"
                )
                return ConnectorResult(
                    source_type="jira",
                    source_id=key,
                    title=f"[{key}] {summary}",
                    url=f"{self.domain}/browse/{key}",
                    content=content,
                    metadata={"status": status, "priority": priority, "assignee": assignee}
                )
        except Exception:
            return None

    def _extract_adf_text(self, desc_obj: Any) -> str:
        if isinstance(desc_obj, str):
            return desc_obj
        if not isinstance(desc_obj, dict):
            return ""

        texts = []
        def walk(node: Any):
            if isinstance(node, dict):
                if node.get("type") == "text":
                    t = node.get("text", "")
                    if t:
                        texts.append(t)
                for k, v in node.items():
                    walk(v)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(desc_obj)
        return " ".join(texts)
