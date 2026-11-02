"""Text chunker with configurable size and overlap, preserving metadata."""
from typing import List, Dict, Any


def chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    base_metadata: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
    """
    Chunks a text into segments of approximately `chunk_size` characters with `chunk_overlap`,
    splitting on word or paragraph boundaries when possible.
    """
    if base_metadata is None:
        base_metadata = {}

    if not text:
        return []

    words = text.split()
    chunks: List[Dict[str, Any]] = []
    
    # Calculate approximate words per chunk (avg ~5 chars per word + space = 6 chars)
    words_per_chunk = max(10, chunk_size // 6)
    overlap_words = max(2, chunk_overlap // 6)
    step = max(1, words_per_chunk - overlap_words)

    chunk_idx = 0
    for i in range(0, len(words), step):
        chunk_words = words[i:i + words_per_chunk]
        chunk_str = " ".join(chunk_words).strip()
        if not chunk_str:
            continue

        meta = base_metadata.copy()
        meta["chunk_index"] = chunk_idx
        chunks.append({
            "content": chunk_str,
            "metadata": meta,
            "chunk_index": chunk_idx
        })
        chunk_idx += 1
        if i + words_per_chunk >= len(words):
            break

    return chunks
