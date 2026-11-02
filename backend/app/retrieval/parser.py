"""Document parsing utilities for PDF, Markdown, and TXT files."""
import io
import hashlib
from typing import List, Dict, Any, Tuple
import pypdf


def compute_content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def parse_document(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    Parses file content and returns a list of pages/sections with metadata.
    Returns: List of dicts: [{"text": str, "page_number": int, "section": str}]
    """
    ext = filename.lower().split(".")[-1]
    results: List[Dict[str, Any]] = []

    if ext == "pdf":
        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                clean_text = text.strip()
                if clean_text:
                    results.append({
                        "text": clean_text,
                        "page_number": i + 1,
                        "section": f"Page {i + 1}"
                    })
        except Exception as e:
            raise ValueError(f"Failed to parse PDF {filename}: {str(e)}")

    elif ext in ["md", "markdown"]:
        try:
            text = file_bytes.decode("utf-8", errors="replace")
            # Chunk by headers or return structured sections
            lines = text.split("\n")
            current_section = "Document Header"
            current_buffer: List[str] = []
            section_idx = 1

            for line in lines:
                if line.startswith("#"):
                    if current_buffer:
                        buf_text = "\n".join(current_buffer).strip()
                        if buf_text:
                            results.append({
                                "text": buf_text,
                                "page_number": section_idx,
                                "section": current_section
                            })
                            section_idx += 1
                        current_buffer = []
                    current_section = line.strip("# ").strip()
                current_buffer.append(line)

            if current_buffer:
                buf_text = "\n".join(current_buffer).strip()
                if buf_text:
                    results.append({
                        "text": buf_text,
                        "page_number": section_idx,
                        "section": current_section
                    })
        except Exception as e:
            raise ValueError(f"Failed to parse Markdown {filename}: {str(e)}")

    elif ext in ["txt", "log", "csv"]:
        try:
            text = file_bytes.decode("utf-8", errors="replace").strip()
            if text:
                results.append({
                    "text": text,
                    "page_number": 1,
                    "section": "General"
                })
        except Exception as e:
            raise ValueError(f"Failed to parse text file {filename}: {str(e)}")
    else:
        raise ValueError(f"Unsupported file format: {ext}")

    return results
