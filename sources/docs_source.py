"""Documentation & blog RSS source — reads public RSS/Atom feeds."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

from sources.base import Article, BaseSource
from utils.logger import get_logger

logger = get_logger("source.docs")


class DocsSource(BaseSource):
    name = "Docs/Blog"

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
        feeds: list[dict] = self.config.get("feeds", [])
        keywords = {kw.lower() for kw in topics + tools}
        articles: list[Article] = []

        for feed_cfg in feeds:
            url: str = feed_cfg.get("url", "")
            feed_name: str = feed_cfg.get("name", url)
            topic_hint: str = feed_cfg.get("topic_hint", "")

            if not url:
                continue

            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    # Parse date from various fields
                    pub = None
                    for date_field in ("published", "updated", "created"):
                        raw = entry.get(date_field)
                        if raw:
                            try:
                                pub = parsedate_to_datetime(raw)
                                break
                            except Exception:
                                try:
                                    pub = datetime.fromisoformat(raw.rstrip("Z")).replace(tzinfo=timezone.utc)
                                    break
                                except Exception:
                                    pass
                    if pub is None:
                        pub = datetime.now(timezone.utc)

                    if not self._is_recent(pub, days_back):
                        continue

                    text = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
                    if keywords and not any(kw in text for kw in keywords):
                        continue

                    summary = self._truncate(entry.get("summary", entry.get("title", "")))
                    ctype = "Tools & Releases" if "pypi" in url.lower() else "News & Articles"
                    articles.append(
                        Article(
                            title=entry.get("title", "(no title)"),
                            link=entry.get("link", url),
                            summary=summary,
                            date=pub,
                            source=feed_name,
                            tags=[topic_hint] if topic_hint else [],
                            content_type=ctype,
                        )
                    )
            except Exception as exc:
                logger.warning("Docs feed '%s' error: %s", feed_name, exc)

        logger.debug("Docs/Blog → %d articles", len(articles))
        return articles
