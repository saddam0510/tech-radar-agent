"""ACL Anthology source — NLP/CL papers from ACL, EMNLP, NAACL, EACL, etc.

Tier 1: premier NLP venue papers.
Strategy: query Semantic Scholar filtered to ACL venues for recent papers,
plus parse the ACL Anthology RSS if available.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import feedparser
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from sources.base import Article, BaseSource
from utils.logger import get_logger

logger = get_logger("source.acl")

_S2_API = "https://api.semanticscholar.org/graph/v1/paper/search"
_S2_FIELDS = "title,abstract,url,publicationDate,citationCount,venue"

# ACL Anthology RSS feeds (new papers added to proceedings)
_ACL_FEEDS = [
    "https://aclanthology.org/anthology.rss",            # main feed (if available)
]

# Venue keywords to filter S2 results to ACL-family
_ACL_VENUES = {"acl", "emnlp", "naacl", "eacl", "coling", "findings", "aclanthology"}

_NLP_QUERIES = [
    "NLP natural language processing",
    "large language model fine-tuning",
    "machine translation neural",
    "text generation transformer",
]


class ACLSource(BaseSource):
    name = "ACL Anthology"
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
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        seen: set[str] = set()

        # ── Try ACL RSS feeds ─────────────────────────────────────────────────
        for feed_url in _ACL_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                if feed.bozo or not feed.entries:
                    continue
                for entry in feed.entries:
                    try:
                        pub = parsedate_to_datetime(entry.get("published", ""))
                    except Exception:
                        pub = datetime.now(timezone.utc)
                    if pub < cutoff:
                        continue
                    link = entry.get("link", "")
                    if link in seen:
                        continue
                    seen.add(link)
                    articles.append(
                        Article(
                            title=entry.title,
                            link=link,
                            summary=self._truncate(entry.get("summary", entry.title)),
                            date=pub,
                            source="ACL Anthology",
                            content_type="Research",
                            tier=1,
                        )
                    )
            except Exception as exc:
                logger.debug("ACL RSS '%s' error: %s", feed_url, exc)

        # ── Semantic Scholar fallback for ACL-venue papers ────────────────────
        max_per_query: int = self.config.get("max_results_per_query", 8)
        queries: list[str] = self.config.get("queries", _NLP_QUERIES)

        retry = Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 503], raise_on_status=False)
        session = requests.Session()
        session.mount("https://", HTTPAdapter(max_retries=retry))

        for i, query in enumerate(queries):
            if i > 0:
                time.sleep(3)   # stagger to avoid competing with semantic_scholar_source
            try:
                resp = session.get(
                    _S2_API,
                    params={
                        "query": query,
                        "fields": _S2_FIELDS,
                        "limit": max_per_query * 3,
                        "sort": "publicationDate:desc",
                    },
                    timeout=20,
                )
                resp.raise_for_status()
                for paper in resp.json().get("data", []):
                    venue = (paper.get("venue") or "").lower()
                    if not any(v in venue for v in _ACL_VENUES):
                        continue

                    paper_id = paper.get("paperId", "")
                    url = paper.get("url") or f"https://www.semanticscholar.org/paper/{paper_id}"
                    if url in seen:
                        continue
                    seen.add(url)

                    pub_str = paper.get("publicationDate") or ""
                    try:
                        pub = datetime.fromisoformat(pub_str).replace(tzinfo=timezone.utc)
                    except Exception:
                        pub = datetime.now(timezone.utc)
                    if pub < cutoff:
                        continue

                    citations = paper.get("citationCount") or 0
                    articles.append(
                        Article(
                            title=paper.get("title", ""),
                            link=url,
                            summary=self._truncate(paper.get("abstract") or ""),
                            date=pub,
                            source="ACL Anthology",
                            content_type="Research",
                            tier=1,
                            popularity_score=self._normalise_popularity(citations, 500),
                        )
                    )
            except Exception as exc:
                logger.warning("ACL S2 query '%s' error: %s", query, exc)

        logger.debug("ACL Anthology -> %d articles", len(articles))
        return articles
