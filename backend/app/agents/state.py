"""Agent State definitions for the LangGraph orchestration engine."""
from typing import List, Dict, Any, Optional, TypedDict
from pydantic import BaseModel, Field


class SubTask(BaseModel):
    id: str
    description: str
    tool: str
    arguments: Dict[str, Any]
    status: str = "pending"  # pending, running, completed, failed
    result_summary: Optional[str] = None


class ExecutionPlan(BaseModel):
    subtasks: List[SubTask] = Field(default_factory=list)
    budget_tool_calls: int = 8
    completion_criteria: str = ""


class EvidenceItem(BaseModel):
    evidence_id: str  # e.g., "S1", "S2"
    source_type: str  # "jira", "notion", "document", "memory"
    source_id: str
    title: str
    url: Optional[str] = None
    excerpt: str
    last_updated: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    relevance_score: float = 0.5


class VerificationReport(BaseModel):
    is_supported: bool = True
    unsupported_claims: List[str] = Field(default_factory=list)
    invalid_citations: List[str] = Field(default_factory=list)
    conflicts_detected: List[str] = Field(default_factory=list)
    missing_info: List[str] = Field(default_factory=list)
    correction_needed: bool = False
    confidence_explanation: str = ""


class AgentTimelineEvent(BaseModel):
    stage: str
    title: str
    status: str  # "running" | "completed" | "warning" | "error"
    details: Optional[str] = None
    duration_ms: Optional[float] = None


class AgentState(TypedDict):
    # User input and session context
    user_id: str
    conversation_id: str
    query: str
    chat_history: List[Dict[str, str]]
    connected_integrations: List[str]

    # Reasoning and workflow stages
    query_understanding: Dict[str, Any]
    plan: Dict[str, Any]
    executed_tools: List[Dict[str, Any]]
    evidence_items: List[Dict[str, Any]]
    
    # Synthesis & Verification
    draft_answer: str
    verification_report: Dict[str, Any]
    final_answer: str
    citations: List[Dict[str, Any]]
    
    # Execution metadata & Observability
    iteration_count: int
    timeline_events: List[Dict[str, Any]]
    errors: List[str]
    total_latency_ms: float
