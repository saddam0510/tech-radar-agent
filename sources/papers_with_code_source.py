"""Papers with Code source — trending ML papers with code.

Tier 1: high-signal, structured research + implementation data.
API docs: https://paperswithcode.com/api/v1/docs/
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta

import requests

from sources.base import Article, BaseSource
from utils.logger import get_logger

logger = get_logger("source.paperswithcode")

_API_BASE = "https://paperswithcode.com/api/v1"


class PapersWithCodeSource(BaseSource):
    name = "Papers with Code"
    default_tier = 1

    async def fetch(
        self,
        topics: list[str],
        tools: list[str],
        days_back: int = 7,
    ) -> list[Article]:
        return await asyncio.to_thread(self._fetch_sync, topics, tools, days_back)

    def _fetch_sync(
        self,
        topics: list[str],
        tools: list[str],
        days_back: int,
    ) -> list[Article]:
        max_results: int = self.config.get("max_results", 30)
        keywords = {kw.lower() for kw in topics + tools}
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        articles: list[Article] = []

        # ── Trending papers (by date) ─────────────────────────────────────────
        try:
            resp = requests.get(
                f"{_API_BASE}/papers/",
                params={
                    "ordering": "-published",
                    "items_per_page": max_results,
                    "page": 1,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            papers = data.get("results", [])

            for paper in papers:
                pub_str = paper.get("published") or ""
                try:
                    pub = datetime.fromisoformat(pub_str).replace(tzinfo=timezone.utc)
                except Exception:
                    continue

                if pub < cutoff:
                    continue

                title = paper.get("title", "")
                abstract = self._truncate(paper.get("abstract") or "")
                url = paper.get("url_abs") or paper.get("paper_url") or ""
                stars = paper.get("github_link_count") or 0

                text = f"{title} {abstract}".lower()
                if keywords and not any(kw in text for kw in keywords):
                    continue

                articles.append(
                    Article(
                        title=title,
                        link=url or f"https://paperswithcode.com",
                        summary=abstract or "No abstract available.",
                        date=pub,
                        source="Papers with Code",
                        content_type="Research",
                        tier=1,
                        popularity_score=self._normalise_popularity(stars, 500),
                    )
                )
        except Exception as exc:
            logger.warning("Papers with Code error: %s", exc)

        logger.debug("Papers with Code -> %d articles", len(articles))
        return articles
