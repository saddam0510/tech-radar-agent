"""YouTube source — AI-focused videos with view count filtering.

Tier 2: video content with configurable channel allowlist and view threshold.
Requires YOUTUBE_API_KEY environment variable.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone

import requests

from sources.base import Article, BaseSource
from utils.logger import get_logger

logger = get_logger("source.youtube")

_YT_API = "https://www.googleapis.com/youtube/v3"

# High-signal AI/ML channels (channel IDs)
_DEFAULT_CHANNELS = {
    "UCbmNph6atAoGfqLoCL_duAg": "Two Minute Papers",
    "UCWN3xxRkmTPmbKwht9FuE5A": "Siraj Raval",
    "UCZHmQk67mSJgfCCTn7xBfew": "Yannic Kilcher",
    "UCP4bf6IHJJQehibu6ai__cg": "AI Explained",
    "UCnUYZLuoy1rq1aVMwx4aTzw": "sentdex",
    "UCVHFbw7woebKtHkue7LnkBQ": "Lex Fridman",
}


class YouTubeSource(BaseSource):
    name = "YouTube"
    default_tier = 2

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
        api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
        if not api_key or api_key.startswith("AIza..."):
            logger.info("YouTube source skipped: YOUTUBE_API_KEY not set")
            return []

        queries: list[str] = self.config.get("search_queries", [])
        channel_ids: list[str] = self.config.get("channel_ids", list(_DEFAULT_CHANNELS.keys()))
        max_per_query: int = self.config.get("max_results_per_query", 10)
        min_views: int = self.config.get("filters", {}).get("min_views", 10_000)
        published_after = (
            datetime.now(timezone.utc) - timedelta(days=days_back)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        articles: list[Article] = []
        seen_ids: set[str] = set()

        # ── Channel-specific fetch ────────────────────────────────────────────
        for channel_id in channel_ids:
            channel_name = _DEFAULT_CHANNELS.get(channel_id, channel_id)
            try:
                resp = requests.get(
                    f"{_YT_API}/search",
                    params={
                        "part": "snippet",
                        "channelId": channel_id,
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
                    video_id = item["id"].get("videoId", "")
                    if not video_id or video_id in seen_ids:
                        continue
                    seen_ids.add(video_id)
                    snippet = item["snippet"]
                    pub = datetime.strptime(
                        snippet["publishedAt"], "%Y-%m-%dT%H:%M:%SZ"
                    ).replace(tzinfo=timezone.utc)
                    views = self._get_view_count(api_key, video_id)
                    if views < min_views:
                        continue
                    articles.append(
                        Article(
                            title=snippet["title"],
                            link=f"https://www.youtube.com/watch?v={video_id}",
                            summary=self._truncate(snippet.get("description", "")),
                            date=pub,
                            source=f"YouTube ({channel_name})",
                            tags=[channel_name],
                            content_type="News & Articles",
                            tier=2,
                            popularity_score=self._normalise_popularity(views, 1_000_000),
                        )
                    )
            except Exception as exc:
                logger.warning("YouTube channel %s error: %s", channel_name, exc)

        # ── Keyword search ────────────────────────────────────────────────────
        for q in queries:
            try:
                resp = requests.get(
                    f"{_YT_API}/search",
                    params={
                        "part": "snippet",
                        "q": q,
                        "type": "video",
                        "order": "viewCount",
                        "publishedAfter": published_after,
                        "maxResults": max_per_query,
                        "key": api_key,
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                for item in resp.json().get("items", []):
                    video_id = item["id"].get("videoId", "")
                    if not video_id or video_id in seen_ids:
                        continue
                    seen_ids.add(video_id)
                    snippet = item["snippet"]
                    pub = datetime.strptime(
                        snippet["publishedAt"], "%Y-%m-%dT%H:%M:%SZ"
                    ).replace(tzinfo=timezone.utc)
                    views = self._get_view_count(api_key, video_id)
                    if views < min_views:
                        continue
                    articles.append(
                        Article(
                            title=snippet["title"],
                            link=f"https://www.youtube.com/watch?v={video_id}",
                            summary=self._truncate(snippet.get("description", "")),
                            date=pub,
                            source="YouTube",
                            tags=[snippet.get("channelTitle", "")],
                            content_type="News & Articles",
                            tier=2,
                            popularity_score=self._normalise_popularity(views, 1_000_000),
                        )
                    )
            except Exception as exc:
                logger.warning("YouTube search '%s' error: %s", q, exc)

        logger.debug("YouTube -> %d videos (min_views=%d)", len(articles), min_views)
        return articles

    def _get_view_count(self, api_key: str, video_id: str) -> int:
        """Fetch view count for a single video. Returns 0 on failure."""
        try:
            resp = requests.get(
                f"{_YT_API}/videos",
                params={
                    "part": "statistics",
                    "id": video_id,
                    "key": api_key,
                },
                timeout=8,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            if items:
                return int(items[0].get("statistics", {}).get("viewCount", 0))
        except Exception:
            pass
        return 0
