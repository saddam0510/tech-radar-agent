"""Tier-aware grouping and ranking by content section."""
from __future__ import annotations

from collections import defaultdict

from sources.base import Article
from utils.logger import get_logger

logger = get_logger("processing.ranker")

# Newsletter section order
SECTIONS = [
    "Research",
    "Tools & Releases",
    "News & Articles",
    "Open Source",
]

# Source → section fallback (for articles without content_type set)
_SOURCE_SECTION: dict[str, str] = {
    "arXiv": "Research",
    "Semantic Scholar": "Research",
    "Papers with Code": "Research",
    "ACL Anthology": "Research",
    "Google Scholar": "Research",
    "GitHub Releases": "Tools & Releases",
    "PyPI New Packages": "Tools & Releases",
    "Hugging Face Hub": "Tools & Releases",
    "GitHub": "Open Source",
    "GitHub Trending": "Open Source",
    "Medium": "News & Articles",
    "Reddit": "News & Articles",
    "YouTube": "News & Articles",
}


def _resolve_section(article: Article) -> str:
    if article.content_type:
        return article.content_type
    # Partial-match fallback
    src = article.source
    for key, section in _SOURCE_SECTION.items():
        if key.lower() in src.lower():
            return section
    return "News & Articles"


def _composite_rank(article: Article) -> tuple:
    """Sort key: (tier asc, relevance desc, popularity desc, recency desc)."""
    return (
        article.tier,                   # lower tier number = better
        -article.relevance_score,
        -article.popularity_score,
        article.age_days(),             # lower age = more recent
    )


def group_and_rank(
    articles: list[Article],
    topics: list[str],
    max_per_topic: int = 5,
    max_per_section: int = 5,
) -> dict[str, list[Article]]:
    """Group articles into sections; within each section rank by composite score.

    Strategy per section:
    1. Bucket articles by assigned topic.
    2. Take top-N from each topic (tier-aware sort).
    3. Merge and re-sort the full section — Tier 1 articles naturally bubble up.

    Returns an ordered dict: section_name → article list.
    """
    section_buckets: dict[str, list[Article]] = defaultdict(list)
    for article in articles:
        section = _resolve_section(article)
        section_buckets[section].append(article)

    result: dict[str, list[Article]] = {}
    for section in SECTIONS:
        items = section_buckets.get(section, [])
        if not items:
            continue

        # Per-topic selection (fair quota)
        topic_buckets: dict[str, list[Article]] = defaultdict(list)
        for a in items:
            topic_buckets[a.assigned_topic or "General"].append(a)

        selected: list[Article] = []
        for topic in topics + ["General"]:
            bucket = topic_buckets.get(topic, [])
            bucket.sort(key=_composite_rank)
            selected.extend(bucket[:max_per_topic])

        # Deduplicate (same article may appear via multiple topic buckets)
        seen: set[str] = set()
        unique: list[Article] = []
        for a in selected:
            if a.link not in seen:
                seen.add(a.link)
                unique.append(a)

        # Final section sort: tier first, then relevance + popularity; cap at max_per_section
        unique.sort(key=_composite_rank)
        result[section] = unique[:max_per_section]

    total = sum(len(v) for v in result.values())
    tier_counts = defaultdict(int)
    for arts in result.values():
        for a in arts:
            tier_counts[a.tier] += 1

    logger.info(
        "Ranked %d articles across %d sections | T1=%d T2=%d T3=%d",
        total,
        len(result),
        tier_counts[1],
        tier_counts[2],
        tier_counts[3],
    )
    return result
