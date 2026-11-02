"""Document upload, parsing, chunking, and indexing endpoints."""
import os
import shutil
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import User, Document, DocumentChunk
from app.api.deps import get_current_user
from app.retrieval.parser import parse_document, compute_content_hash
from app.retrieval.chunker import chunk_text
from app.retrieval.embeddings import get_embedding_provider
from app.core.config import settings

router = APIRouter()


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size_bytes: int
    status: str
    chunk_count: int
    created_at: str


@router.get("", response_model=List[DocumentResponse])
async def list_documents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc())
    docs = (await db.execute(stmt)).scalars().all()
    return [
        DocumentResponse(
            id=d.id,
            filename=d.filename,
            file_type=d.file_type,
            file_size_bytes=d.file_size_bytes,
            status=d.status,
            chunk_count=d.chunk_count,
            created_at=d.created_at.isoformat() if d.created_at else ""
        ) for d in docs
    ]


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds maximum allowed size (10 MB)")

    ext = file.filename.split(".")[-1].lower() if file.filename else ""
    if ext not in ["pdf", "txt", "md", "markdown", "log"]:
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload PDF, TXT, or MD.")

    content_hash = compute_content_hash(content)

    # Check for duplicate document
    stmt = select(Document).where(Document.user_id == user.id, Document.content_hash == content_hash)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        return DocumentResponse(
            id=existing.id,
            filename=existing.filename,
            file_type=existing.file_type,
            file_size_bytes=existing.file_size_bytes,
            status=existing.status,
            chunk_count=existing.chunk_count,
            created_at=existing.created_at.isoformat()
        )

    doc = Document(
        user_id=user.id,
        filename=file.filename or "unknown_file",
        file_type=ext,
        file_size_bytes=len(content),
        content_hash=content_hash,
        status="indexing"
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Parse and chunk document
    try:
        sections = parse_document(content, doc.filename)
        all_chunks = []
        for sec in sections:
            meta = {"page": sec.get("page_number"), "section": sec.get("section")}
            sec_chunks = chunk_text(
                sec["text"],
                chunk_size=settings.CHUNK_SIZE,
                chunk_overlap=settings.CHUNK_OVERLAP,
                base_metadata=meta
            )
            all_chunks.extend(sec_chunks)

        if all_chunks:
            embedding_provider = get_embedding_provider()
            texts = [c["content"] for c in all_chunks]
            embeddings = await embedding_provider.embed_texts(texts)

            for i, c in enumerate(all_chunks):
                chunk_obj = DocumentChunk(
                    document_id=doc.id,
                    chunk_index=i,
                    content=c["content"],
                    metadata_json=c["metadata"],
                    embedding=embeddings[i] if i < len(embeddings) else None
                )
                db.add(chunk_obj)

        doc.chunk_count = len(all_chunks)
        doc.status = "ready"
        await db.commit()
        await db.refresh(doc)
    except Exception as e:
        doc.status = "failed"
        doc.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")

    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        file_type=doc.file_type,
        file_size_bytes=doc.file_size_bytes,
        status=doc.status,
        chunk_count=doc.chunk_count,
        created_at=doc.created_at.isoformat()
    )


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = delete(Document).where(Document.id == doc_id, Document.user_id == user.id)
    res = await db.execute(stmt)
    await db.commit()
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted successfully"}
