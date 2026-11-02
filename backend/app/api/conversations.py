"""Conversations, message streaming, and agent invocation endpoints."""
import time
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import User, Conversation, Message, Integration
from app.api.deps import get_current_user
from app.agents.orchestrator import AgentOrchestrator
from app.agents.state import AgentState
from app.observability.service import ObservabilityService

router = APIRouter()


class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    citations: Optional[List[Dict[str, Any]]] = None
    verification_status: Optional[Dict[str, Any]] = None
    execution_plan: Optional[Dict[str, Any]] = None
    created_at: str


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str


class ChatResponse(BaseModel):
    conversation_id: str
    message: MessageResponse
    timeline_events: List[Dict[str, Any]]


@router.get("", response_model=List[ConversationResponse])
async def list_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc())
    convs = (await db.execute(stmt)).scalars().all()
    return [
        ConversationResponse(
            id=c.id,
            title=c.title,
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat()
        ) for c in convs
    ]


@router.post("", response_model=ConversationResponse)
async def create_conversation(
    title: Optional[str] = "New Conversation",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    conv = Conversation(user_id=user.id, title=title or "New Conversation")
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat()
    )


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.id == conversation_id, Conversation.user_id == user.id)
        .order_by(Message.created_at.asc())
    )
    msgs = (await db.execute(stmt)).scalars().all()
    return [
        MessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            citations=m.citations,
            verification_status=m.verification_status,
            execution_plan=m.execution_plan,
            created_at=m.created_at.isoformat()
        ) for m in msgs
    ]


@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(
    req: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    t_start = time.time()
    
    # 1. Resolve or create conversation
    conv_id = req.conversation_id
    if conv_id:
        stmt = select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user.id)
        conv = (await db.execute(stmt)).scalar_one_or_none()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conv = Conversation(
            user_id=user.id,
            title=req.message[:35] + ("..." if len(req.message) > 35 else "")
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        conv_id = conv.id

    # 2. Save user message
    user_msg = Message(
        conversation_id=conv_id,
        role="user",
        content=req.message
    )
    db.add(user_msg)
    await db.commit()

    # 3. Fetch connected integrations for user
    ig_stmt = select(Integration.provider).where(Integration.user_id == user.id, Integration.is_active == True)
    connected_integrations = list((await db.execute(ig_stmt)).scalars().all())

    # 4. Initialize Agent Graph State
    initial_state: AgentState = {
        "user_id": user.id,
        "conversation_id": conv_id,
        "query": req.message,
        "chat_history": [],
        "connected_integrations": connected_integrations,
        "query_understanding": {},
        "plan": {},
        "executed_tools": [],
        "evidence_items": [],
        "draft_answer": "",
        "verification_report": {},
        "final_answer": "",
        "citations": [],
        "iteration_count": 0,
        "timeline_events": [],
        "errors": [],
        "total_latency_ms": 0.0
    }

    # 5. Run LangGraph Workflow
    orchestrator = AgentOrchestrator(db)
    graph = orchestrator.build_graph()
    final_state = await graph.ainvoke(initial_state)

    total_latency_ms = (time.time() - t_start) * 1000

    # 6. Save assistant message with citations, verification, and plan
    assistant_msg = Message(
        conversation_id=conv_id,
        role="assistant",
        content=final_state.get("final_answer", ""),
        citations=final_state.get("citations", []),
        verification_status=final_state.get("verification_report", {}),
        execution_plan=final_state.get("plan", {})
    )
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)

    # 7. Record Execution Trace for Observability
    obs_svc = ObservabilityService(db)
    await obs_svc.record_trace(
        user_id=user.id,
        conversation_id=conv_id,
        query=req.message,
        stages=final_state.get("timeline_events", []),
        tool_calls=final_state.get("executed_tools", []),
        total_latency_ms=total_latency_ms
    )

    return ChatResponse(
        conversation_id=conv_id,
        message=MessageResponse(
            id=assistant_msg.id,
            role=assistant_msg.role,
            content=assistant_msg.content,
            citations=assistant_msg.citations,
            verification_status=assistant_msg.verification_status,
            execution_plan=assistant_msg.execution_plan,
            created_at=assistant_msg.created_at.isoformat()
        ),
        timeline_events=final_state.get("timeline_events", [])
    )
