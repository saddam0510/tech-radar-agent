"""Reddit source — community posts with upvote-based quality filtering.

Tier 2: semi-structured community signal with configurable upvote threshold.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

import praw

from sources.base import Article, BaseSource
from utils.logger import get_logger

logger = get_logger("source.reddit")

_DEFAULT_SUBREDDITS = [
    "MachineLearning",
    "LocalLLaMA",
    "dataengineering",
    "artificial",
    "docker",
    "kubernetes",
    "apacheairflow",
    "Python",
    "MLOps",
]


class RedditSource(BaseSource):
    name = "Reddit"
    default_tier = 2

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._reddit: praw.Reddit | None = None

    def _get_client(self) -> praw.Reddit:
        if self._reddit is None:
            self._reddit = praw.Reddit(
                client_id=os.environ["REDDIT_CLIENT_ID"],
                client_secret=os.environ["REDDIT_CLIENT_SECRET"],
                user_agent=os.getenv("REDDIT_USER_AGENT", "TechRadarBot/1.0"),
            )
        return self._reddit

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
        reddit = self._get_client()
        subreddits: list[str] = self.config.get("subreddits", _DEFAULT_SUBREDDITS)
        limit: int = self.config.get("limit_per_subreddit", 50)
        min_upvotes: int = self.config.get("filters", {}).get("min_upvotes", 50)
        articles: list[Article] = []
        keywords = {kw.lower() for kw in topics + tools}

        for sub_name in subreddits:
            try:
                subreddit = reddit.subreddit(sub_name)
                fetched = 0
                for post in subreddit.hot(limit=limit):  # hot = better quality than new
                    date = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
                    if not self._is_recent(date, days_back):
                        continue

                    # Upvote quality gate
                    if post.score < min_upvotes:
                        continue

                    text = f"{post.title} {post.selftext}".lower()
                    if not any(kw in text for kw in keywords):
                        continue

                    summary = self._truncate(
                        post.selftext if post.selftext else post.title
                    )
                    articles.append(
                        Article(
                            title=post.title,
                            link=f"https://reddit.com{post.permalink}",
                            summary=summary,
                            date=date,
                            source=f"Reddit r/{sub_name}",
                            tags=[sub_name],
                            content_type="News & Articles",
                            tier=2,
                            popularity_score=self._normalise_popularity(post.score, 5000),
                        )
                    )
                    fetched += 1
                logger.debug("Reddit r/%s -> %d posts", sub_name, fetched)
            except Exception as exc:
                logger.warning("Reddit r/%s error: %s", sub_name, exc)

        return articles
