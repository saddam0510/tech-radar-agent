"""Topic → Source affinity routing.

Defines which sources are most authoritative for each topic, and applies
a score boost when an article comes from a preferred source for its topic.

Topics are aligned to the user's professional context:
Senior Data Scientist at Teradata — Govt / Telco / Banking domains.
"""
from __future__ import annotations

from sources.base import Article

TOPIC_SOURCE_MAP: dict[str, dict] = {
    # ── Core stack ──────────────────────────────────────────────────────────
    "Teradata ML": {
        "sources": ["Teradata Blog", "GitHub Releases", "GitHub"],
        "boost": 0.40,
    },
    "PySpark": {
        "sources": ["Databricks Blog", "GitHub Releases", "GitHub",
                    "Reddit r/dataengineering", "Towards Data Science"],
        "boost": 0.35,
    },
    "Airflow": {
        "sources": ["Airflow Blog", "GitHub Releases", "GitHub",
                    "Reddit r/apacheairflow", "Towards Data Science"],
        "boost": 0.35,
    },

    # ── Domain use cases ────────────────────────────────────────────────────
    "Entity Resolution": {
        "sources": ["arXiv", "Semantic Scholar", "Papers with Code",
                    "ACL Anthology", "Towards Data Science"],
        "boost": 0.35,
    },
    "Record Linkage": {
        "sources": ["arXiv", "Semantic Scholar", "Papers with Code",
                    "ACL Anthology", "GitHub"],
        "boost": 0.35,
    },
    "Fraud Detection": {
        "sources": ["arXiv", "Semantic Scholar", "Papers with Code",
                    "Databricks Blog", "GitHub"],
        "boost": 0.30,
    },
    "Data Quality": {
        "sources": ["arXiv", "Databricks Blog", "Towards Data Science",
                    "GitHub", "Reddit r/dataengineering"],
        "boost": 0.25,
    },

    # ── Data & ML engineering ───────────────────────────────────────────────
    "Data Engineering": {
        "sources": ["Databricks Blog", "arXiv", "GitHub",
                    "Reddit r/dataengineering", "Towards Data Science"],
        "boost": 0.25,
    },
    "Feature Engineering": {
        "sources": ["arXiv", "Papers with Code", "Databricks Blog",
                    "Towards Data Science", "GitHub"],
        "boost": 0.25,
    },
    "MLOps": {
        "sources": ["arXiv", "Databricks Blog", "GitHub Releases",
                    "GitHub", "Towards Data Science"],
        "boost": 0.30,
    },

    # ── AI / NLP ────────────────────────────────────────────────────────────
    "NLP": {
        "sources": ["arXiv", "ACL Anthology", "Semantic Scholar",
                    "Hugging Face Blog", "Towards Data Science"],
        "boost": 0.30,
    },
    "LLMs": {
        "sources": ["arXiv", "Hugging Face", "Papers with Code",
                    "Databricks Blog", "Import AI", "The Batch"],
        "boost": 0.25,
    },
    "AI Agents": {
        "sources": ["arXiv", "Papers with Code", "GitHub", "GitHub Trending",
                    "Hugging Face Blog", "Import AI"],
        "boost": 0.25,
    },

    # ── Infrastructure ──────────────────────────────────────────────────────
    "Kubernetes": {
        "sources": ["Kubernetes Blog", "GitHub Releases", "GitHub",
                    "Reddit r/kubernetes"],
        "boost": 0.30,
    },
    "Docker": {
        "sources": ["Docker Blog", "GitHub Releases", "GitHub",
                    "Reddit r/docker"],
        "boost": 0.30,
    },
}


def apply_affinity_boost(articles: list[Article]) -> list[Article]:
    """Apply a source-affinity bonus to each article's relevance score."""
    for article in articles:
        topic = article.assigned_topic
        if not topic or topic not in TOPIC_SOURCE_MAP:
            continue

        mapping = TOPIC_SOURCE_MAP[topic]
        preferred = mapping["sources"]
        boost = mapping["boost"]

        source_lower = article.source.lower()
        if any(p.lower() in source_lower for p in preferred):
            article.relevance_score = min(1.0, article.relevance_score + boost)

    return articles


def get_preferred_sources(topic: str) -> list[str]:
    return TOPIC_SOURCE_MAP.get(topic, {}).get("sources", [])
