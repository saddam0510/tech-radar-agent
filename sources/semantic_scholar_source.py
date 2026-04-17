"""Semantic Scholar source — academic paper search API.

Tier 1: structured research with citation signals.
API docs: https://api.semanticscholar.org/graph/v1
Rate limit: 100 req/5min unauthenticated; set S2_API_KEY for 1 req/s.
"""
from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timezone, timedelta

import requests

from sources.base import Article, BaseSource
from utils.logger import get_logger

logger = get_logger("source.semantic_scholar")

_API_BASE = "https://api.semanticscholar.org/graph/v1"
_FIELDS = "title,abstract,url,year,publicationDate,citationCount,externalIds"


class SemanticScholarSource(BaseSource):
    name = "Semantic Scholar"
    default_tier = 1

    def _headers(self) -> dict:
        h: dict = {}
        key = os.getenv("S2_API_KEY", "").strip()
        if key:
            h["x-api-key"] = key
        return h

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
        queries: list[str] = self.config.get(
            "queries",
            [
                "large language models",
                "generative AI agents",
                "NLP transformer",
                "machine learning",
            ],
        )
        max_per_query: int = self.config.get("max_results_per_query", 10)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        articles: list[Article] = []
        seen: set[str] = set()

        for i, query in enumerate(queries):
            if i > 0:
                time.sleep(0.5)  # gentle rate-limiting
            try:
                resp = requests.get(
                    f"{_API_BASE}/paper/search",
                    params={
                        "query": query,
                        "fields": _FIELDS,
                        "limit": max_per_query,
                        "sort": "publicationDate:desc",
                    },
                    headers=self._headers(),
                    timeout=15,
                )
                resp.raise_for_status()

                for paper in resp.json().get("data", []):
                    paper_id = paper.get("paperId", "")
                    if paper_id in seen:
                        continue
                    seen.add(paper_id)

                    pub_str = paper.get("publicationDate") or ""
                    year = paper.get("year")
                    if pub_str:
                        try:
                            pub = datetime.fromisoformat(pub_str).replace(tzinfo=timezone.utc)
                        except Exception:
                            pub = datetime(year or 2020, 1, 1, tzinfo=timezone.utc)
                    elif year:
                        pub = datetime(year, 1, 1, tzinfo=timezone.utc)
                    else:
                        continue

                    if pub < cutoff:
                        continue

                    title = paper.get("title") or ""
                    abstract = self._truncate(paper.get("abstract") or "")
                    url = paper.get("url") or (
                        f"https://www.semanticscholar.org/paper/{paper_id}"
                    )
                    citations = paper.get("citationCount") or 0

                    articles.append(
                        Article(
                            title=title,
                            link=url,
                            summary=abstract or "No abstract available.",
                            date=pub,
                            source="Semantic Scholar",
                            content_type="Research",
                            tier=1,
                            popularity_score=self._normalise_popularity(citations, 1000),
                        )
                    )
            except Exception as exc:
                logger.warning("Semantic Scholar query '%s' error: %s", query, exc)

        logger.debug("Semantic Scholar -> %d articles", len(articles))
        return articles
