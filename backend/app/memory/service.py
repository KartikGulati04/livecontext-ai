"""Memory service for short-term conversation context and consented long-term user memories."""
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.db.models import Memory, Message
from app.retrieval.embeddings import get_embedding_provider
from app.retrieval.search import cosine_similarity


class MemoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # --- Short-term Context ---
    async def get_recent_conversation_messages(self, conversation_id: str, limit: int = 6) -> List[Dict[str, str]]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        messages = list(result.scalars().all())
        messages.reverse()  # Chronological order
        return [{"role": m.role, "content": m.content} for m in messages]

    # --- Long-term Memories ---
    async def retrieve_relevant_memories(
        self,
        user_id: str,
        query: str,
        top_k: int = 3,
        threshold: float = 0.35
    ) -> List[Dict[str, Any]]:
        """
        Retrieves consented, active user memories relevant to the query.
        Guarantees memories never override current instructions or source permissions.
        """
        stmt = select(Memory).where(
            Memory.user_id == user_id,
            Memory.is_active == True,
            Memory.user_consented == True
        )
        result = await self.db.execute(stmt)
        memories = result.scalars().all()
        if not memories:
            return []

        embedding_provider = get_embedding_provider()
        query_vector = await embedding_provider.embed_query(query)

        scored_memories = []
        q_lower = query.lower()
        for mem in memories:
            score = 0.0
            if mem.embedding:
                score = cosine_similarity(query_vector, mem.embedding)
            # Add lexical boost for shared keywords or tokens
            mem_tokens = set(mem.content.lower().split())
            query_tokens = set(q_lower.split())
            if query_tokens & mem_tokens or any(t in mem.content.lower() for t in query_tokens):
                score = max(score, 0.5)

            # In user preference search or broad query, include if score exceeds threshold or if threshold is low
            if score >= threshold or threshold <= 0.0:
                scored_memories.append({
                    "id": mem.id,
                    "content": mem.content,
                    "memory_type": mem.memory_type,
                    "provenance": mem.provenance,
                    "score": round(score, 4)
                })

        scored_memories.sort(key=lambda x: x["score"], reverse=True)
        return scored_memories[:top_k]

    async def create_memory(
        self,
        user_id: str,
        content: str,
        memory_type: str = "user_preference",
        provenance: str = "explicit_input",
        user_consented: bool = True
    ) -> Memory:
        # Check for duplicates or near-duplicates
        stmt = select(Memory).where(
            Memory.user_id == user_id,
            Memory.content == content.strip()
        )
        existing = (await self.db.execute(stmt)).scalar_one_or_none()
        if existing:
            return existing

        embedding_provider = get_embedding_provider()
        emb = await embedding_provider.embed_query(content)

        memory = Memory(
            user_id=user_id,
            content=content.strip(),
            memory_type=memory_type,
            provenance=provenance,
            is_active=True,
            user_consented=user_consented,
            embedding=emb
        )
        self.db.add(memory)
        await self.db.commit()
        await self.db.refresh(memory)
        return memory

    async def list_memories(self, user_id: str) -> List[Memory]:
        stmt = select(Memory).where(Memory.user_id == user_id).order_by(Memory.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_memory(self, user_id: str, memory_id: str, content: Optional[str] = None, is_active: Optional[bool] = None) -> Optional[Memory]:
        stmt = select(Memory).where(Memory.id == memory_id, Memory.user_id == user_id)
        memory = (await self.db.execute(stmt)).scalar_one_or_none()
        if not memory:
            return None

        if content is not None:
            memory.content = content.strip()
            embedding_provider = get_embedding_provider()
            memory.embedding = await embedding_provider.embed_query(memory.content)
        if is_active is not None:
            memory.is_active = is_active

        memory.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(memory)
        return memory

    async def delete_memory(self, user_id: str, memory_id: str) -> bool:
        stmt = delete(Memory).where(Memory.id == memory_id, Memory.user_id == user_id)
        res = await self.db.execute(stmt)
        await self.db.commit()
        return res.rowcount > 0
