"""Google Scholar source — uses the `scholarly` library.

⚠️  Rate-limited by Google. Keep enabled=false unless running infrequently.
    Consider adding a delay or proxy if you enable this source.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sources.base import Article, BaseSource
from utils.logger import get_logger

logger = get_logger("source.scholar")


class GoogleScholarSource(BaseSource):
    name = "Google Scholar"

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
        try:
            from scholarly import scholarly
        except ImportError:
            logger.warning("scholarly not installed — run: pip install scholarly")
            return []

        queries: list[str] = self.config.get("queries", [])
        max_per_query: int = self.config.get("max_results_per_query", 5)
        articles: list[Article] = []
        current_year = datetime.now().year

        for q in queries:
            try:
                results = scholarly.search_pubs(q)
                count = 0
                for pub in results:
                    if count >= max_per_query:
                        break
                    bib = pub.get("bib", {})
                    year = bib.get("pub_year")
                    if year and int(year) < current_year:
                        continue  # skip old papers

                    title = bib.get("title", "")
                    abstract = self._truncate(bib.get("abstract", "No abstract available."))
                    link = pub.get("pub_url") or pub.get("eprint_url") or ""
                    pub_date = datetime(int(year), 1, 1, tzinfo=timezone.utc) if year else datetime.now(timezone.utc)

                    articles.append(
                        Article(
                            title=title,
                            link=link,
                            summary=abstract,
                            date=pub_date,
                            source="Google Scholar",
                        )
                    )
                    count += 1
            except Exception as exc:
                logger.warning("Scholar query '%s' error: %s", q, exc)

        logger.debug("Google Scholar → %d articles", len(articles))
        return articles
