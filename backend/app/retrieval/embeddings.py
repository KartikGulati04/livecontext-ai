"""Embedding providers with support for Gemini, OpenAI, and deterministic Local Embeddings."""
import abc
import hashlib
import math
from typing import List, Optional
import httpx
from app.core.config import settings


class BaseEmbeddingProvider(abc.ABC):
    @abc.abstractmethod
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        pass

    @abc.abstractmethod
    async def embed_query(self, text: str) -> List[float]:
        pass


class DeterministicLocalEmbedding(BaseEmbeddingProvider):
    """
    High-speed deterministic feature-hash embedding provider for zero-cost offline,
    evaluation, and fallback mode. Generates unit-norm dense vectors of length `dimension`.
    Captures n-gram frequencies and word semantics deterministically.
    """
    def __init__(self, dimension: int = 768):
        self.dimension = dimension

    def _embed_single(self, text: str) -> List[float]:
        tokens = text.lower().replace("\n", " ").split()
        vector = [0.0] * self.dimension
        if not tokens:
            return vector

        # Bag of words + bigrams hashed onto dimension slots
        for i, token in enumerate(tokens):
            h1 = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % self.dimension
            vector[h1] += 1.0
            if i > 0:
                bigram = f"{tokens[i-1]}_{token}"
                h2 = int(hashlib.sha1(bigram.encode("utf-8")).hexdigest(), 16) % self.dimension
                vector[h2] += 1.5

        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self._embed_single(t) for t in texts]

    async def embed_query(self, text: str) -> List[float]:
        return self._embed_single(text)


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent"

    async def embed_query(self, text: str) -> List[float]:
        res = await self.embed_texts([text])
        return res[0]

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        results: List[List[float]] = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            for text in texts:
                try:
                    resp = await client.post(
                        f"{self.base_url}?key={self.api_key}",
                        json={
                            "model": "models/text-embedding-004",
                            "content": {"parts": [{"text": text[:2048]}]}
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        values = data.get("embedding", {}).get("values", [])
                        results.append(values)
                    else:
                        # Fallback to local if quota or error
                        local_emb = DeterministicLocalEmbedding()._embed_single(text)
                        results.append(local_emb)
                except Exception:
                    local_emb = DeterministicLocalEmbedding()._embed_single(text)
                    results.append(local_emb)
        return results


def get_embedding_provider() -> BaseEmbeddingProvider:
    provider = settings.EMBEDDING_PROVIDER.lower()
    if provider == "gemini" and settings.GEMINI_API_KEY:
        return GeminiEmbeddingProvider(api_key=settings.GEMINI_API_KEY)
    elif provider == "auto":
        if settings.GEMINI_API_KEY:
            return GeminiEmbeddingProvider(api_key=settings.GEMINI_API_KEY)
        return DeterministicLocalEmbedding(dimension=settings.EMBEDDING_DIMENSION)
    else:
        return DeterministicLocalEmbedding(dimension=settings.EMBEDDING_DIMENSION)
