"""Official blogs & newsletters source — curated high-signal RSS/Atom feeds.

Tier 1: official publications from AI labs, engineering teams, and industry blogs.
All feeds are defined in config.yaml under sources.official_blogs.feeds so users
can add/remove feeds without touching code.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

from sources.base import Article, BaseSource
from utils.logger import get_logger

logger = get_logger("source.official_blogs")

# ── Default curated feeds ─────────────────────────────────────────────────────
# Each entry: name, url, topic_hints, content_type
# These are used when the config doesn't override them.
_DEFAULT_FEEDS: list[dict] = [
    # ── AI Research Labs ──────────────────────────────────────────────────────
    {
        "name": "OpenAI Blog",
        "url": "https://openai.com/blog/rss.xml",
        "topic_hints": ["LLMs", "GenAI", "AI"],
        "content_type": "News & Articles",
    },
    {
        "name": "DeepMind Blog",
        "url": "https://deepmind.google/blog/rss.xml",
        "topic_hints": ["AI", "Machine Learning", "LLMs"],
        "content_type": "Research",
    },
    {
        "name": "Meta AI Blog",
        "url": "https://engineering.fb.com/feed/",
        "topic_hints": ["AI", "LLMs", "GenAI", "Machine Learning"],
        "content_type": "Research",
    },
    {
        "name": "Hugging Face Blog",
        "url": "https://huggingface.co/blog/feed.xml",
        "topic_hints": ["LLMs", "GenAI", "NLP", "Machine Learning"],
        "content_type": "News & Articles",
    },
    # ── Data / ML Platforms ───────────────────────────────────────────────────
    {
        "name": "Databricks Blog",
        "url": "https://www.databricks.com/feed",
        "topic_hints": ["Spark", "Machine Learning", "GenAI", "AI"],
        "content_type": "News & Articles",
    },
    {
        "name": "Teradata Blog",
        "url": "https://www.teradata.com/blogs/rss",
        "topic_hints": ["Teradata ML", "AI", "Analysis"],
        "content_type": "News & Articles",
    },
    # ── Engineering / DevOps ─────────────────────────────────────────────────
    {
        "name": "Airflow Blog",
        "url": "https://airflow.apache.org/blog/index.xml",
        "topic_hints": ["Airflow"],
        "content_type": "News & Articles",
    },
    {
        "name": "Docker Blog",
        "url": "https://www.docker.com/blog/feed/",
        "topic_hints": ["Docker"],
        "content_type": "News & Articles",
    },
    {
        "name": "Kubernetes Blog",
        "url": "https://kubernetes.io/feed.xml",
        "topic_hints": ["Kubernetes"],
        "content_type": "News & Articles",
    },
    # ── Newsletters & Industry ────────────────────────────────────────────────
    {
        "name": "Towards Data Science",
        "url": "https://towardsdatascience.com/feed",
        "topic_hints": ["Machine Learning", "AI", "Analysis", "NLP"],
        "content_type": "News & Articles",
    },
    {
        "name": "Import AI",
        "url": "https://importai.substack.com/feed",
        "topic_hints": ["AI", "LLMs", "GenAI", "AI Agents"],
        "content_type": "News & Articles",
    },
    {
        "name": "The Batch (DeepLearning.AI)",
        "url": "https://www.deeplearning.ai/the-batch/rss.xml",
        "topic_hints": ["AI", "Machine Learning", "LLMs"],
        "content_type": "News & Articles",
    },
    # ── PyPI packages ────────────────────────────────────────────────────────
    {
        "name": "PyPI New Packages",
        "url": "https://pypi.org/rss/updates.xml",
        "topic_hints": [],  # broad — keyword filter handles relevance
        "content_type": "Tools & Releases",
    },
]


class OfficialBlogsSource(BaseSource):
    name = "Official Blogs"
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
        # Merge default feeds with any extra feeds from config
        feeds: list[dict] = list(_DEFAULT_FEEDS)
        extra: list[dict] = self.config.get("extra_feeds", [])
        feeds.extend(extra)

        # Apply per-feed enabled overrides from config
        overrides: dict = {
            f["name"]: f
            for f in self.config.get("feed_overrides", [])
        }

        keywords = {kw.lower() for kw in topics + tools}
        articles: list[Article] = []

        for feed_cfg in feeds:
            feed_name = feed_cfg["name"]

            # Allow disabling individual feeds via config
            override = overrides.get(feed_name, {})
            if not override.get("enabled", True):
                continue

            url: str = feed_cfg["url"]
            topic_hints: list[str] = feed_cfg.get("topic_hints", [])
            content_type: str = feed_cfg.get("content_type", "News & Articles")

            try:
                feed = feedparser.parse(url)
                fetched = 0
                for entry in feed.entries:
                    pub = self._parse_date(entry)
                    if not self._is_recent(pub, days_back):
                        continue

                    text = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()

                    # For feeds with topic hints, allow all entries through (already curated)
                    # For broad feeds (no hints), apply keyword filter
                    if not topic_hints and keywords:
                        if not any(kw in text for kw in keywords):
                            continue

                    summary = self._truncate(entry.get("summary", entry.get("title", "")))
                    articles.append(
                        Article(
                            title=entry.get("title", "(no title)"),
                            link=entry.get("link", url),
                            summary=summary,
                            date=pub,
                            source=feed_name,
                            tags=topic_hints,
                            content_type=content_type,
                            tier=1,
                        )
                    )
                    fetched += 1

                if fetched:
                    logger.debug("'%s' -> %d articles", feed_name, fetched)
            except Exception as exc:
                logger.warning("Blog feed '%s' error: %s", feed_name, exc)

        logger.debug("Official Blogs total -> %d articles", len(articles))
        return articles

    @staticmethod
    def _parse_date(entry) -> datetime:
        for field in ("published", "updated", "created"):
            raw = entry.get(field)
            if not raw:
                continue
            try:
                return parsedate_to_datetime(raw)
            except Exception:
                pass
            try:
                return datetime.fromisoformat(raw.rstrip("Z")).replace(tzinfo=timezone.utc)
            except Exception:
                pass
        return datetime.now(timezone.utc)
