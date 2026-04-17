"""Papers with Code / HuggingFace Papers source — trending ML papers.

Papers with Code now redirects to HuggingFace Papers, so we use the
HuggingFace Papers API which provides upvotes, AI summaries, and rich metadata.

Tier 1: high-signal research with community-validated popularity (upvotes).
API: https://huggingface.co/api/papers
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta

import requests

from sources.base import Article, BaseSource
from utils.logger import get_logger

logger = get_logger("source.paperswithcode")

_HF_PAPERS_API = "https://huggingface.co/api/papers"


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
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        keywords = {kw.lower() for kw in topics + tools}
        articles: list[Article] = []
        seen: set[str] = set()

        # Search for each topic individually to get targeted results
        queries: list[str] = self.config.get(
            "queries",
            [
                "large language model",
                "machine learning",
                "NLP natural language",
                "generative AI",
                "deep learning",
                "AI agent",
            ],
        )
        max_per_query: int = self.config.get("max_results_per_query", 15)

        for query in queries:
            try:
                resp = requests.get(
                    _HF_PAPERS_API,
                    params={"q": query, "limit": max_per_query},
                    timeout=15,
                )
                resp.raise_for_status()
                papers = resp.json()
                if not isinstance(papers, list):
                    continue

                for paper in papers:
                    paper_id = paper.get("id", "")
                    if paper_id in seen:
                        continue
                    seen.add(paper_id)

                    pub_str = paper.get("publishedAt", "")
                    try:
                        pub = datetime.fromisoformat(
                            pub_str.replace("Z", "+00:00")
                        )
                    except Exception:
                        continue

                    if pub < cutoff:
                        continue

                    title = paper.get("title", "")
                    # Prefer AI summary, fall back to summary field
                    summary = (
                        paper.get("ai_summary")
                        or paper.get("summary")
                        or "No abstract available."
                    )
                    summary = self._truncate(summary)
                    upvotes = paper.get("upvotes", 0) or 0
                    link = f"https://huggingface.co/papers/{paper_id}"

                    text = f"{title} {summary}".lower()
                    if keywords and not any(kw in text for kw in keywords):
                        continue

                    articles.append(
                        Article(
                            title=title,
                            link=link,
                            summary=summary,
                            date=pub,
                            source="Papers with Code",
                            content_type="Research",
                            tier=1,
                            popularity_score=self._normalise_popularity(upvotes, 200),
                        )
                    )
            except Exception as exc:
                logger.warning("HF Papers query '%s' error: %s", query, exc)

        logger.debug("Papers with Code -> %d articles", len(articles))
        return articles
