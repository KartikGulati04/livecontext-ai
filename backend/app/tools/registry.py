"""Tool definitions, execution schemas, and security permission checks."""
from typing import Dict, Any, List, Optional, Callable
from pydantic import BaseModel, Field


class ToolCallRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]
    required_permissions: List[str] = Field(default_factory=list)


AVAILABLE_TOOLS: Dict[str, ToolDefinition] = {
    "search_documents": ToolDefinition(
        name="search_documents",
        description="Search indexed documents and local knowledge base for relevant chunks.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query keywords"}
            },
            "required": ["query"]
        },
        required_permissions=["documents:read"]
    ),
    "search_jira": ToolDefinition(
        name="search_jira",
        description="Search issues in connected Atlassian Jira workspace by keyword or JQL.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Issue summary or keyword"},
                "jql": {"type": "string", "description": "Optional explicit JQL filter"}
            },
            "required": ["query"]
        },
        required_permissions=["jira:read"]
    ),
    "get_jira_issue": ToolDefinition(
        name="get_jira_issue",
        description="Fetch complete details, status, and description for a specific Jira issue key.",
        parameters={
            "type": "object",
            "properties": {
                "issue_key": {"type": "string", "description": "Jira issue key, e.g. PROJ-101"}
            },
            "required": ["issue_key"]
        },
        required_permissions=["jira:read"]
    ),
    "search_notion": ToolDefinition(
        name="search_notion",
        description="Search pages, notes, and documentation in connected Notion workspace.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search terms"}
            },
            "required": ["query"]
        },
        required_permissions=["notion:read"]
    ),
    "get_notion_page": ToolDefinition(
        name="get_notion_page",
        description="Fetch blocks and body content for a specific Notion page ID.",
        parameters={
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "UUID of the Notion page"}
            },
            "required": ["page_id"]
        },
        required_permissions=["notion:read"]
    ),
    "get_user_memories": ToolDefinition(
        name="get_user_memories",
        description="Retrieve user-approved preferences, project context, and historical directives.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Topic to retrieve user memory on"}
            },
            "required": ["query"]
        },
        required_permissions=["memory:read"]
    ),
    "search_gmail": ToolDefinition(
        name="search_gmail",
        description="Search recent emails and message threads in connected Gmail account using read-only scope.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Email sender, subject keywords, or search query"}
            },
            "required": ["query"]
        },
        required_permissions=["gmail:read"]
    )
}
