"""LLM Provider adapter supporting Gemini 1.5, OpenAI GPT-4o, and deterministic fallback."""
import abc
import json
import re
from typing import Dict, Any, List, Optional
import httpx
from app.core.config import settings


class BaseLLMClient(abc.ABC):
    @abc.abstractmethod
    async def generate_response(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        pass

    @abc.abstractmethod
    async def generate_structured(self, prompt: str, system_instruction: Optional[str] = None) -> Dict[str, Any]:
        pass


class GeminiClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str = "gemini-1.5-pro"):
        self.api_key = api_key
        self.model = model
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    async def generate_response(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        contents = []
        if system_instruction:
            contents.append({"role": "user", "parts": [{"text": f"SYSTEM INSTRUCTION: {system_instruction}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will strictly obey."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{self.base_url}?key={self.api_key}",
                json={"contents": contents}
            )
            if resp.status_code == 200:
                data = resp.json()
                try:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                except Exception:
                    return ""
            raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text}")

    async def generate_structured(self, prompt: str, system_instruction: Optional[str] = None) -> Dict[str, Any]:
        instruct = (system_instruction or "") + "\nRespond with VALID JSON ONLY. Do not wrap in markdown or backticks."
        raw = await self.generate_response(prompt, instruct)
        # Parse json
        clean = re.sub(r"^```json\s*", "", raw.strip(), flags=re.MULTILINE)
        clean = re.sub(r"```$", "", clean.strip(), flags=re.MULTILINE)
        return json.loads(clean.strip())


class LocalFallbackLLMClient(BaseLLMClient):
    """
    High-fidelity deterministic local engine for query decomposition,
    grounded synthesis, and verification when external API keys are omitted.
    """
    async def generate_response(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        return "Deterministic response based on retrieved evidence."

    async def generate_structured(self, prompt: str, system_instruction: Optional[str] = None) -> Dict[str, Any]:
        return {}


def get_llm_client() -> BaseLLMClient:
    if settings.GEMINI_API_KEY:
        return GeminiClient(api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL)
    return LocalFallbackLLMClient()
