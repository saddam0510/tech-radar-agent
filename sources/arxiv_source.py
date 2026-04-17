"""arXiv source — no API key required."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import arxiv

from sources.base import Article, BaseSource
from utils.logger import get_logger

logger = get_logger("source.arxiv")


class ArxivSource(BaseSource):
    name = "arXiv"

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
        categories: list[str] = self.config.get("categories", ["cs.AI", "cs.LG"])
        max_results: int = self.config.get("max_results", 50)

        # Build a combined arXiv query: category filter + keyword OR
        keywords = list({kw.lower() for kw in topics + tools})
        # arXiv query syntax: cat:cs.AI AND (keyword1 OR keyword2 ...)
        cat_filter = " OR ".join(f"cat:{c}" for c in categories)
        kw_filter = " OR ".join(f'all:"{kw}"' for kw in keywords[:10])  # cap to avoid URL length issues
        query = f"({cat_filter}) AND ({kw_filter})"

        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        articles: list[Article] = []
        try:
            for result in client.results(search):
                pub_date = result.published
                if pub_date.tzinfo is None:
                    pub_date = pub_date.replace(tzinfo=timezone.utc)
                if not self._is_recent(pub_date, days_back):
                    continue

                summary = self._truncate(result.summary)
                articles.append(
                    Article(
                        title=result.title,
                        link=result.entry_id,
                        summary=summary,
                        date=pub_date,
                        source="arXiv",
                        tags=list(result.categories) if result.categories else [],
                    content_type="Research",
                    )
                )
        except Exception as exc:
            logger.warning("arXiv fetch error: %s", exc)

        logger.debug("arXiv → %d articles", len(articles))
        return articles
