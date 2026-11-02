"""User Memory management endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.db.session import get_db
from app.db.models import User
from app.api.deps import get_current_user
from app.memory.service import MemoryService

router = APIRouter()


class MemoryCreateInput(BaseModel):
    content: str
    memory_type: str = "user_preference"  # preference | project_context | fact


class MemoryUpdateInput(BaseModel):
    content: Optional[str] = None
    is_active: Optional[bool] = None


class MemoryResponse(BaseModel):
    id: str
    content: str
    memory_type: str
    provenance: str
    is_active: bool
    user_consented: bool
    created_at: str


@router.get("", response_model=List[MemoryResponse])
async def list_memories(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    mem_svc = MemoryService(db)
    mems = await mem_svc.list_memories(user.id)
    return [
        MemoryResponse(
            id=m.id,
            content=m.content,
            memory_type=m.memory_type,
            provenance=m.provenance,
            is_active=m.is_active,
            user_consented=m.user_consented,
            created_at=m.created_at.isoformat() if m.created_at else ""
        ) for m in mems
    ]


@router.post("", response_model=MemoryResponse)
async def create_memory(
    input_data: MemoryCreateInput,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    mem_svc = MemoryService(db)
    m = await mem_svc.create_memory(
        user_id=user.id,
        content=input_data.content,
        memory_type=input_data.memory_type,
        provenance="explicit_input",
        user_consented=True
    )
    return MemoryResponse(
        id=m.id,
        content=m.content,
        memory_type=m.memory_type,
        provenance=m.provenance,
        is_active=m.is_active,
        user_consented=m.user_consented,
        created_at=m.created_at.isoformat() if m.created_at else ""
    )


@router.patch("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: str,
    input_data: MemoryUpdateInput,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    mem_svc = MemoryService(db)
    m = await mem_svc.update_memory(
        user_id=user.id,
        memory_id=memory_id,
        content=input_data.content,
        is_active=input_data.is_active
    )
    if not m:
        raise HTTPException(status_code=404, detail="Memory not found")
    return MemoryResponse(
        id=m.id,
        content=m.content,
        memory_type=m.memory_type,
        provenance=m.provenance,
        is_active=m.is_active,
        user_consented=m.user_consented,
        created_at=m.created_at.isoformat() if m.created_at else ""
    )


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    mem_svc = MemoryService(db)
    deleted = await mem_svc.delete_memory(user.id, memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"message": "Memory deleted successfully"}
