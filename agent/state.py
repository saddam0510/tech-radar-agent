"""Shared in-memory state for the agent session.

Accumulates articles across multiple tool calls so the agent can reason
about coverage before deciding to fetch more or finalize.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass
class AgentState:
    articles: list = field(default_factory=list)
    fetched_sources: set = field(default_factory=set)

    def add(self, new_articles: list, source_name: str) -> int:
        """Add articles to state, return count of newly added."""
        before = len(self.articles)
        self.articles.extend(new_articles)
        self.fetched_sources.add(source_name)
        return len(self.articles) - before

    def summary(self) -> str:
        """Return a human-readable summary for the agent."""
        if not self.articles:
            return "No articles collected yet."

        topics = [getattr(a, "assigned_topic", None) or "Unassigned" for a in self.articles]
        topic_counts = Counter(topics)
        top = ", ".join(f"{t}({n})" for t, n in topic_counts.most_common(6))
        sources_done = ", ".join(sorted(self.fetched_sources)) or "none"

        return (
            f"Total articles collected: {len(self.articles)}\n"
            f"Sources already fetched: {sources_done}\n"
            f"Topic distribution: {top}"
        )

    def reset(self) -> None:
        self.articles.clear()
        self.fetched_sources.clear()


# Module-level singleton — shared across all tool calls in one agent run
_state = AgentState()


def get_state() -> AgentState:
    return _state


def reset_state() -> None:
    _state.reset()
