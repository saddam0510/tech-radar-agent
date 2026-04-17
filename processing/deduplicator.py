"""Deduplication — removes identical/near-duplicate articles."""
from __future__ import annotations

import re
from collections import defaultdict

from sources.base import Article
from utils.logger import get_logger

logger = get_logger("processing.dedup")


def _normalize(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def _jaccard(a: str, b: str) -> float:
    sa = set(_normalize(a).split())
    sb = set(_normalize(b).split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def deduplicate(
    articles: list[Article],
    url_exact: bool = True,
    title_threshold: float = 0.85,
) -> list[Article]:
    """Remove duplicate articles.

    Strategy:
    1. Exact URL match (fast hash set).
    2. Fuzzy title similarity via Jaccard coefficient.

    Args:
        articles: Raw article list.
        url_exact: Remove articles with identical URLs.
        title_threshold: Jaccard threshold above which two titles are considered duplicates.

    Returns:
        Deduplicated list (earlier/first occurrence is kept).
    """
    seen_urls: set[str] = set()
    kept: list[Article] = []

    for article in articles:
        # 1. URL dedup
        if url_exact and article.link in seen_urls:
            continue

        # 2. Title similarity dedup
        is_dup = any(
            _jaccard(article.title, k.title) >= title_threshold
            for k in kept
        )
        if is_dup:
            continue

        seen_urls.add(article.link)
        kept.append(article)

    removed = len(articles) - len(kept)
    if removed:
        logger.info("Deduplication removed %d articles (%d kept)", removed, len(kept))
    return kept
