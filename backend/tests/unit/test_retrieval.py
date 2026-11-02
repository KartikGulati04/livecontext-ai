import pytest
from app.retrieval.chunker import chunk_text
from app.retrieval.embeddings import DeterministicLocalEmbedding
from app.retrieval.search import cosine_similarity
from app.retrieval.parser import parse_document, compute_content_hash


def test_chunker_basic():
    text = "Word " * 200
    chunks = chunk_text(text, chunk_size=200, chunk_overlap=30)
    assert len(chunks) > 1
    assert "chunk_index" in chunks[0]["metadata"]
    assert chunks[0]["metadata"]["chunk_index"] == 0


def test_content_hash():
    c1 = b"Hello LiveContext AI"
    c2 = b"Hello LiveContext AI"
    c3 = b"Different Content"
    assert compute_content_hash(c1) == compute_content_hash(c2)
    assert compute_content_hash(c1) != compute_content_hash(c3)


def test_markdown_parser():
    md = b"# Title 1\nSome description here.\n## Subtitle\nMore text."
    sections = parse_document(md, "test.md")
    assert len(sections) >= 2
    assert "Title 1" in sections[0]["section"]


@pytest.mark.asyncio
async def test_deterministic_embedding_similarity():
    embedder = DeterministicLocalEmbedding(dimension=128)
    v1 = await embedder.embed_query("machine learning rag embeddings")
    v2 = await embedder.embed_query("machine learning embeddings retrieval")
    v3 = await embedder.embed_query("completely unrelated cooking recipe pancake")

    sim_related = cosine_similarity(v1, v2)
    sim_unrelated = cosine_similarity(v1, v3)

    assert sim_related > sim_unrelated
    assert sim_related > 0.4
