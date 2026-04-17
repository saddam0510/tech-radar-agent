"""Base abstractions for all content sources."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Article:
    """Canonical content item returned by every source."""
    title: str
    link: str
    summary: str
    date: datetime
    source: str                              # human-readable source name
    tags: list[str] = field(default_factory=list)
    relevance_score: float = 0.0
    assigned_topic: Optional[str] = None    # filled in by the processing layer
    content_type: str = ""                  # Research / Tools & Releases / News & Articles / Open Source

    def __post_init__(self) -> None:
        # Normalise to UTC-aware datetime
        if self.date.tzinfo is None:
            self.date = self.date.replace(tzinfo=timezone.utc)

    def age_days(self) -> float:
        return (datetime.now(timezone.utc) - self.date).total_seconds() / 86_400


class BaseSource(ABC):
    """Every content source must implement this interface."""
    name: str = "base"

    def __init__(self, config: dict) -> None:
        self.config = config
        self.enabled: bool = config.get("enabled", True)

    @abstractmethod
    async def fetch(
        self,
        topics: list[str],
        tools: list[str],
        days_back: int = 7,
    ) -> list[Article]:
        """Fetch recent articles relevant to *topics* and *tools*.

        Args:
            topics: High-level topic labels (e.g. "LLMs", "Docker").
            tools:  Specific tool keywords (e.g. "PySpark", "Claude").
            days_back: Only return articles published within this many days.

        Returns:
            List of :class:`Article` objects.
        """

    # ── helpers ──────────────────────────────────────────────────────────────

    def _is_recent(self, date: datetime, days_back: int) -> bool:
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - date).days <= days_back

    def _truncate(self, text: str, max_chars: int = 500) -> str:
        text = (text or "").strip()
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rsplit(" ", 1)[0] + "…"
