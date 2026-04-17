"""YouTube source — requires YOUTUBE_API_KEY environment variable."""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone, timedelta

import requests

from sources.base import Article, BaseSource
from utils.logger import get_logger

logger = get_logger("source.youtube")

_YT_API = "https://www.googleapis.com/youtube/v3"


class YouTubeSource(BaseSource):
    name = "YouTube"

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
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            logger.warning("YouTube source disabled: YOUTUBE_API_KEY not set")
            return []

        queries: list[str] = self.config.get("search_queries", [])
        max_per_query: int = self.config.get("max_results_per_query", 10)
        published_after = (
            datetime.now(timezone.utc) - timedelta(days=days_back)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        articles: list[Article] = []

        for q in queries:
            try:
                resp = requests.get(
                    f"{_YT_API}/search",
                    params={
                        "part": "snippet",
                        "q": q,
                        "type": "video",
                        "order": "date",
                        "publishedAfter": published_after,
                        "maxResults": max_per_query,
                        "key": api_key,
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                for item in resp.json().get("items", []):
                    snippet = item["snippet"]
                    pub_str = snippet["publishedAt"]  # ISO 8601
                    pub = datetime.strptime(pub_str, "%Y-%m-%dT%H:%M:%SZ").replace(
                        tzinfo=timezone.utc
                    )
                    video_id = item["id"]["videoId"]
                    articles.append(
                        Article(
                            title=snippet["title"],
                            link=f"https://www.youtube.com/watch?v={video_id}",
                            summary=self._truncate(snippet.get("description", "")),
                            date=pub,
                            source="YouTube",
                            tags=[snippet.get("channelTitle", "")],
                        )
                    )
            except Exception as exc:
                logger.warning("YouTube search '%s' error: %s", q, exc)

        logger.debug("YouTube → %d articles", len(articles))
        return articles
