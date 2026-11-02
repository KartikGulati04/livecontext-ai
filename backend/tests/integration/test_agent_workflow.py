import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.db.session import Base
from app.db.models import User
from app.memory.service import MemoryService
from app.agents.orchestrator import AgentOrchestrator
from app.agents.state import AgentState

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def async_db():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_memory_lifecycle(async_db):
    user = User(email="test@user.com", hashed_password="pwd", full_name="Test User")
    async_db.add(user)
    await async_db.commit()
    await async_db.refresh(user)

    mem_svc = MemoryService(async_db)
    m1 = await mem_svc.create_memory(
        user_id=user.id,
        content="Prefer dark mode and concise summaries",
        memory_type="user_preference"
    )
    assert m1.id is not None
    assert m1.is_active is True

    # Retrieve memory
    retrieved = await mem_svc.retrieve_relevant_memories(user.id, "concise summaries dark mode", threshold=0.2)
    assert len(retrieved) >= 1
    assert "concise" in retrieved[0]["content"]

    # Disable memory
    await mem_svc.update_memory(user.id, m1.id, is_active=False)
    after_disable = await mem_svc.retrieve_relevant_memories(user.id, "formatting preferences")
    assert len(after_disable) == 0


@pytest.mark.asyncio
async def test_agent_orchestrator_flow(async_db):
    user = User(email="agent@user.com", hashed_password="pwd", full_name="Agent User")
    async_db.add(user)
    await async_db.commit()
    await async_db.refresh(user)

    orchestrator = AgentOrchestrator(async_db)
    graph = orchestrator.build_graph()

    state: AgentState = {
        "user_id": user.id,
        "conversation_id": "conv-1",
        "query": "What are our release blockers and Notion meeting decisions?",
        "chat_history": [],
        "connected_integrations": [],
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

    final_state = await graph.ainvoke(state)

    assert "plan" in final_state
    assert len(final_state["plan"]["subtasks"]) >= 2
    assert "timeline_events" in final_state
    assert len(final_state["timeline_events"]) >= 4
    # Ensure missing integrations are reported honestly and not simulated
    assert any("not connected" in err.lower() or "missing" in err.lower() for err in final_state["errors"])
    assert final_state["verification_report"]["is_supported"] is True
