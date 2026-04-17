"""Hugging Face source — blog RSS + new models from the Hub API.

Tier 1: high-signal, official HuggingFace content.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests

from sources.base import Article, BaseSource
from utils.logger import get_logger

logger = get_logger("source.huggingface")

_BLOG_RSS = "https://huggingface.co/blog/feed.xml"
_MODELS_API = "https://huggingface.co/api/models"


class HuggingFaceSource(BaseSource):
    name = "Hugging Face"
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
        articles: list[Article] = []
        keywords = {kw.lower() for kw in topics + tools}

        # ── Blog RSS ──────────────────────────────────────────────────────────
        try:
            feed = feedparser.parse(_BLOG_RSS)
            for entry in feed.entries:
                try:
                    pub = parsedate_to_datetime(entry.get("published", ""))
                except Exception:
                    pub = datetime.now(timezone.utc)

                if not self._is_recent(pub, days_back):
                    continue

                text = f"{entry.title} {entry.get('summary', '')}".lower()
                if keywords and not any(kw in text for kw in keywords):
                    continue

                articles.append(
                    Article(
                        title=entry.title,
                        link=entry.link,
                        summary=self._truncate(entry.get("summary", entry.title)),
                        date=pub,
                        source="Hugging Face Blog",
                        content_type="News & Articles",
                        tier=1,
                    )
                )
        except Exception as exc:
            logger.warning("HuggingFace blog error: %s", exc)

        # ── Models Hub (new models) ───────────────────────────────────────────
        fetch_models: bool = self.config.get("fetch_models", True)
        max_models: int = self.config.get("max_models", 20)

        if fetch_models:
            try:
                resp = requests.get(
                    _MODELS_API,
                    params={
                        "sort": "createdAt",
                        "direction": -1,
                        "limit": max_models * 3,  # over-fetch; many won't match
                        "full": "false",
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                count = 0
                for model in resp.json():
                    if count >= max_models:
                        break
                    created_str = model.get("createdAt", "")
                    try:
                        pub = datetime.fromisoformat(
                            created_str.replace("Z", "+00:00")
                        )
                    except Exception:
                        continue

                    if not self._is_recent(pub, days_back):
                        continue

                    model_id: str = model.get("modelId", model.get("id", ""))
                    model_tags: list[str] = model.get("tags", [])
                    tags_text = " ".join(model_tags).lower()

                    if keywords and not any(kw in f"{model_id} {tags_text}" for kw in keywords):
                        continue

                    downloads = model.get("downloads", 0) or 0
                    articles.append(
                        Article(
                            title=f"[HF Model] {model_id}",
                            link=f"https://huggingface.co/{model_id}",
                            summary=f"New model on Hugging Face Hub. Tags: {', '.join(model_tags[:8]) or 'none'}.",
                            date=pub,
                            source="Hugging Face Hub",
                            tags=model_tags[:10],
                            content_type="Tools & Releases",
                            tier=1,
                            popularity_score=self._normalise_popularity(downloads, 100_000),
                        )
                    )
                    count += 1
            except Exception as exc:
                logger.warning("HuggingFace models API error: %s", exc)

        logger.debug("HuggingFace -> %d articles", len(articles))
        return articles
