"""Topic → Source affinity routing.

Defines which sources are most authoritative for each topic, and applies
a score boost when an article comes from a preferred source for its topic.

The mapping is intentionally declarative so it reads like a policy document
and can be extended without touching scoring logic.
"""
from __future__ import annotations

from sources.base import Article

# ── Topic → preferred source names ───────────────────────────────────────────
# Source names must match Article.source values (or substrings thereof).
# Affinity boost is added to relevance_score when the article's source
# appears in the preferred list for the assigned topic.

TOPIC_SOURCE_MAP: dict[str, dict] = {
    "LLMs": {
        "sources": ["arXiv", "Hugging Face", "Papers with Code", "OpenAI Blog",
                    "DeepMind Blog", "Anthropic", "Reddit r/LocalLLaMA",
                    "Import AI", "The Batch"],
        "boost": 0.25,
    },
    "GenAI": {
        "sources": ["arXiv", "Hugging Face", "OpenAI Blog", "DeepMind Blog",
                    "Meta AI Blog", "Databricks Blog", "Papers with Code",
                    "Import AI", "The Batch"],
        "boost": 0.25,
    },
    "AI": {
        "sources": ["arXiv", "Semantic Scholar", "Papers with Code",
                    "OpenAI Blog", "DeepMind Blog", "Meta AI Blog",
                    "Hugging Face Blog", "Import AI"],
        "boost": 0.20,
    },
    "AI Agents": {
        "sources": ["arXiv", "Papers with Code", "GitHub", "GitHub Trending",
                    "OpenAI Blog", "Hugging Face Blog", "Import AI"],
        "boost": 0.25,
    },
    "NLP": {
        "sources": ["arXiv", "ACL Anthology", "Semantic Scholar",
                    "Hugging Face Blog", "Towards Data Science"],
        "boost": 0.30,
    },
    "Machine Learning": {
        "sources": ["arXiv", "Papers with Code", "Semantic Scholar",
                    "Hugging Face Blog", "Databricks Blog",
                    "Towards Data Science", "Reddit r/MachineLearning"],
        "boost": 0.20,
    },
    "Teradata ML": {
        "sources": ["Teradata Blog", "GitHub Releases", "GitHub"],
        "boost": 0.40,
    },
    "Spark": {
        "sources": ["Databricks Blog", "GitHub Releases", "GitHub",
                    "Reddit r/dataengineering"],
        "boost": 0.30,
    },
    "Airflow": {
        "sources": ["Airflow Blog", "GitHub Releases", "GitHub",
                    "Reddit r/apacheairflow"],
        "boost": 0.35,
    },
    "Docker": {
        "sources": ["Docker Blog", "GitHub Releases", "GitHub",
                    "Reddit r/docker"],
        "boost": 0.30,
    },
    "Kubernetes": {
        "sources": ["Kubernetes Blog", "GitHub Releases", "GitHub",
                    "Reddit r/kubernetes"],
        "boost": 0.30,
    },
    "MCPs": {
        "sources": ["arXiv", "GitHub", "GitHub Trending", "Hugging Face Blog",
                    "OpenAI Blog"],
        "boost": 0.30,
    },
    "Analysis": {
        "sources": ["arXiv", "Semantic Scholar", "Towards Data Science",
                    "Databricks Blog", "GitHub"],
        "boost": 0.20,
    },
}


def apply_affinity_boost(articles: list[Article]) -> list[Article]:
    """Apply a source-affinity bonus to each article's relevance score.

    Called after score_articles() has assigned topics. The boost rewards
    articles from authoritative sources for their assigned topic.
    """
    for article in articles:
        topic = article.assigned_topic
        if not topic or topic not in TOPIC_SOURCE_MAP:
            continue

        mapping = TOPIC_SOURCE_MAP[topic]
        preferred = mapping["sources"]
        boost = mapping["boost"]

        # Partial match: article.source only needs to contain the preferred name
        source_lower = article.source.lower()
        if any(p.lower() in source_lower for p in preferred):
            article.relevance_score = min(1.0, article.relevance_score + boost)

    return articles


def get_preferred_sources(topic: str) -> list[str]:
    """Return the list of preferred source names for a given topic."""
    return TOPIC_SOURCE_MAP.get(topic, {}).get("sources", [])
