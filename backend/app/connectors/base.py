"""Base connector specification and interface for live sources."""
import abc
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class ConnectorResult(BaseModel):
    source_type: str  # "jira" | "notion" | "document" | "gmail"
    source_id: str
    title: str
    url: Optional[str] = None
    content: str
    last_updated: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    relevance_score: Optional[float] = None


class BaseConnector(abc.ABC):
    @abc.abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Verify API keys and connectivity."""
        pass

    @abc.abstractmethod
    async def search(self, query: str, filters: Optional[Dict[str, Any]] = None, limit: int = 5) -> List[ConnectorResult]:
        """Search items in the live source."""
        pass

    @abc.abstractmethod
    async def fetch(self, source_id: str) -> Optional[ConnectorResult]:
        """Fetch a specific item by ID."""
        pass

    @abc.abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """Describe supported search types, filters, and fields."""
        pass
