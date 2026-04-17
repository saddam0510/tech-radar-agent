"""Medium source — reads per-tag RSS feeds (no API key required)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

from sources.base import Article, BaseSource
from utils.logger import get_logger

logger = get_logger("source.medium")

_MEDIUM_RSS = "https://medium.com/feed/tag/{tag}"


class MediumSource(BaseSource):
    name = "Medium"

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
        tags: list[str] = self.config.get("tags", [])
        keywords = {kw.lower() for kw in topics + tools}
        articles: list[Article] = []

        for tag in tags:
            url = _MEDIUM_RSS.format(tag=tag)
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    try:
                        pub = parsedate_to_datetime(entry.published)
                    except Exception:
                        pub = datetime.now(timezone.utc)

                    if not self._is_recent(pub, days_back):
                        continue

                    text = f"{entry.title} {entry.get('summary', '')}".lower()
                    if not any(kw in text for kw in keywords):
                        continue

                    summary = self._truncate(
                        entry.get("summary", entry.title)
                    )
                    articles.append(
                        Article(
                            title=entry.title,
                            link=entry.link,
                            summary=summary,
                            date=pub,
                            source="Medium",
                            tags=[tag],
                            content_type="News & Articles",
                        )
                    )
            except Exception as exc:
                logger.warning("Medium tag '%s' error: %s", tag, exc)

        logger.debug("Medium → %d articles", len(articles))
        return articles
