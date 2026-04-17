"""Groups articles by section/topic and ranks within each group."""
from __future__ import annotations

from collections import defaultdict

from sources.base import Article
from utils.logger import get_logger

logger = get_logger("processing.ranker")

# Ordered sections shown in the newsletter
SECTIONS = [
    "Research",
    "Tools & Releases",
    "News & Articles",
    "Open Source",
]

# Fallback for articles whose source didn't set content_type
_SOURCE_SECTION: dict[str, str] = {
    "arXiv": "Research",
    "Google Scholar": "Research",
    "GitHub Releases": "Tools & Releases",
    "PyPI New Packages": "Tools & Releases",
    "GitHub": "Open Source",
    "Medium": "News & Articles",
}


def _resolve_section(article: Article) -> str:
    if article.content_type:
        return article.content_type
    return _SOURCE_SECTION.get(article.source, "News & Articles")


def group_and_rank(
    articles: list[Article],
    topics: list[str],
    max_per_topic: int = 5,
) -> dict[str, list[Article]]:
    """Return an ordered dict: section → top articles sorted by relevance.

    Each section collects all articles of that content type.
    Within each section, articles are sorted by relevance then recency.
    The total per section is capped at max_per_topic * 3 to keep the
    newsletter readable, but each topic gets a fair share.
    """
    # Bucket by section
    buckets: dict[str, list[Article]] = defaultdict(list)
    for article in articles:
        section = _resolve_section(article)
        buckets[section].append(article)

    result: dict[str, list[Article]] = {}
    for section in SECTIONS:
        items = buckets.get(section, [])
        if not items:
            continue

        # Within each section, pick top-N per topic so every topic is represented
        topic_buckets: dict[str, list[Article]] = defaultdict(list)
        for a in items:
            topic_buckets[a.assigned_topic or "General"].append(a)

        selected: list[Article] = []
        for topic in topics + ["General"]:
            topic_items = topic_buckets.get(topic, [])
            topic_items.sort(key=lambda a: (a.relevance_score, -a.age_days()), reverse=True)
            selected.extend(topic_items[:max_per_topic])

        # Final sort of the whole section by relevance
        selected.sort(key=lambda a: (a.relevance_score, -a.age_days()), reverse=True)
        result[section] = selected

    total = sum(len(v) for v in result.values())
    logger.info(
        "Ranked %d articles across %d sections",
        total,
        len(result),
    )
    return result
