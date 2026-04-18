"""Context-aware relevance filtering.

Scoring has two layers:
1. Base relevance (keyword + tier + recency + popularity) — unchanged
2. Domain + personalization layer — scores against Saddam's stack, industries,
   and use cases; assigns a personalization tier (🔥 / ⚙️ / 🧠) to each article
   and generates a "why it matters" note.
"""
from __future__ import annotations

import re
from typing import Optional

from sources.base import Article
from utils.logger import get_logger

logger = get_logger("processing.filter")

_TIER_BONUS = {1: 1.0, 2: 0.5, 3: 0.0}

# ── Domain context ─────────────────────────────────────────────────────────────

_INDUSTRY_KEYWORDS = {
    "telco", "telecom", "telecommunications", "churn", "subscriber",
    "network", "5g", "billing",
    "banking", "financial", "finance", "fraud", "credit", "loan",
    "anti-money laundering", "aml", "kyc", "know your customer",
    "government", "public sector", "regulatory", "compliance",
    "enterprise", "production", "at scale", "large-scale",
}

_USE_CASE_KEYWORDS = {
    "entity resolution", "record linkage", "deduplication", "dedup",
    "fuzzy matching", "name matching", "data matching",
    "customer 360", "single customer view",
    "fraud detection", "anomaly detection",
    "data quality", "data cleansing",
    "graph", "relationship modelling", "knowledge graph",
    "feature engineering", "feature store",
    "tabular", "structured data", "data warehouse",
    "nlp", "text processing", "named entity", "ner",
}

_STACK_KEYWORDS = {
    "pyspark", "spark", "apache spark",
    "teradata", "teradataml", "teradata ml", "teradata vantage",
    "airflow", "apache airflow", "dag",
    "kubernetes", "k8s",
    "docker", "container",
    "mlops", "ml pipeline", "model monitoring", "model serving",
    "data pipeline", "etl", "elt",
    "llm agent", "ai agent", "autonomous agent",
    "rag", "retrieval augmented",
}

# Signals that indicate tool/framework releases (→ ⚙️)
_RELEASE_SIGNALS = {
    " v", "version ", "release", "released", "launches", "introduces",
    "new feature", "update:", "what's new", "changelog", "upgrade",
}

# Low-quality / irrelevant content to exclude entirely
_EXCLUSION_SIGNALS = [
    "what is ai", "what is machine learning", "introduction to machine learning",
    "beginners guide", "beginner's guide", "for beginners", "getting started with ai",
    "learn python in", "learn ai in", "top 10 ai tools", "top 10 tips",
    "you should know in 2025", "must know in 2025",
    "raises funding", "valued at $", "acquires", "ipo ",
    "chatgpt vs", "gpt-4o vs", "best ai tools for students",
    "ai will replace", "robots taking jobs",
]


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"\b[\w\-]+\b", text.lower()))


# ── Base relevance score ───────────────────────────────────────────────────────

def _keyword_score(article: Article, topic: str, tools: list[str]) -> float:
    topic_tokens = _tokenize(topic)
    tool_tokens = {t.lower() for t in tools}
    haystack = _tokenize(f"{article.title} {article.summary}")

    topic_hits = len(topic_tokens & haystack) / max(len(topic_tokens), 1)
    tool_hit = 1.0 if haystack & tool_tokens else 0.0
    recency = max(0.0, 1.0 - article.age_days() / 7.0)
    tier_bonus = _TIER_BONUS.get(article.tier, 0.5)
    popularity = article.popularity_score

    return (
        0.45 * topic_hits
        + 0.18 * tool_hit
        + 0.17 * recency
        + 0.10 * tier_bonus
        + 0.10 * popularity
    )


# ── Domain / personalization layer ────────────────────────────────────────────

def _haystack(article: Article) -> str:
    return f"{article.title} {article.summary}".lower()


def _domain_score(article: Article) -> float:
    """Score 0–1 for how well the article matches Saddam's domain context."""
    text = _haystack(article)
    tokens = _tokenize(text)

    industry_hits = sum(1 for kw in _INDUSTRY_KEYWORDS if kw in text)
    use_case_hits = sum(1 for kw in _USE_CASE_KEYWORDS if kw in text)
    stack_hits = sum(1 for kw in _STACK_KEYWORDS if kw in text)

    # Weighted: use-case matches are highest signal, then stack, then industry
    raw = (use_case_hits * 0.5) + (stack_hits * 0.35) + (industry_hits * 0.15)
    return min(1.0, raw / 3.0)


def _is_tool_release(article: Article) -> bool:
    text = _haystack(article)
    return any(sig in text for sig in _RELEASE_SIGNALS)


def _is_low_quality(article: Article) -> bool:
    text = _haystack(article)
    return any(sig in text for sig in _EXCLUSION_SIGNALS)


def _why_matters(article: Article) -> str:
    """Rule-based 'why it matters to you' note."""
    text = _haystack(article)

    if any(k in text for k in ("entity resolution", "record linkage", "fuzzy matching", "name matching")):
        return "Improves entity matching / deduplication pipelines"
    if any(k in text for k in ("fraud detection", "fraud", "anti-money laundering", "aml")):
        return "Directly applicable to banking fraud detection use cases"
    if any(k in text for k in ("customer 360", "single customer view", "churn")):
        return "Relevant to Telco/Banking customer analytics use cases"
    if any(k in text for k in ("data quality", "data cleansing", "dedup")):
        return "Improves data quality in warehouse pipelines"
    if any(k in text for k in ("pyspark", "apache spark", " spark ")):
        return "Enhances PySpark distributed data processing"
    if any(k in text for k in ("teradata", "teradataml")):
        return "Directly extends your Teradata ML workflow"
    if any(k in text for k in ("airflow", "apache airflow", " dag ")):
        return "Improves Airflow orchestration capabilities"
    if any(k in text for k in ("kubernetes", "k8s")):
        return "Relevant to your Kubernetes deployment stack"
    if any(k in text for k in ("docker", "container")):
        return "Applicable to your containerization infrastructure"
    if any(k in text for k in ("mlops", "model monitoring", "model serving")):
        return "Strengthens MLOps monitoring and deployment practices"
    if any(k in text for k in ("llm agent", "ai agent", "autonomous agent", "rag")):
        return "Applicable to enterprise AI agent / automation work"
    if any(k in text for k in ("tabular", "structured data", "data warehouse", "feature engineering")):
        return "Applies to tabular ML on warehouse-scale data"
    if any(k in text for k in ("nlp", "text processing", "ner", "named entity")):
        return "Relevant to your NLP-on-tabular-data use cases"
    if any(k in text for k in ("government", "public sector", "regulatory")):
        return "Relevant to government sector domain work"
    return ""


def _personalization_tier(article: Article, base_score: float, d_score: float) -> str:
    """Assign one of three personalized sections.

    🔥 Directly Applicable  — high domain match OR specific use-case hit
    ⚙️ Tools & Stack Updates — framework/tool release in his stack
    🧠 Worth Knowing         — passes relevance threshold but lower personal signal
    """
    text = _haystack(article)

    # 🔥 Directly applicable: strong domain signal or key use case
    high_use_case = any(k in text for k in _USE_CASE_KEYWORDS)
    strong_stack = any(k in text for k in {"pyspark", "teradata", "teradataml", "airflow"})
    if d_score >= 0.35 or (strong_stack and base_score >= 0.35) or high_use_case:
        return "🔥 Directly Applicable"

    # ⚙️ Tools & stack updates: release in a relevant tool
    stack_mentioned = any(k in text for k in _STACK_KEYWORDS)
    if _is_tool_release(article) and stack_mentioned:
        return "⚙️ Tools & Stack Updates"
    if article.tier == 1 and stack_mentioned:
        return "⚙️ Tools & Stack Updates"

    # 🧠 Worth knowing: still relevant, just not directly applicable
    return "🧠 Worth Knowing"


# ── Optional semantic matching ─────────────────────────────────────────────────

_encoder = None


def _get_encoder():
    global _encoder
    if _encoder is None:
        try:
            from sentence_transformers import SentenceTransformer
            _encoder = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Semantic matching enabled (all-MiniLM-L6-v2)")
        except ImportError:
            logger.info("sentence-transformers not installed — keyword-only scoring")
            _encoder = False
    return _encoder


def _semantic_score(article: Article, topic: str) -> Optional[float]:
    enc = _get_encoder()
    if not enc:
        return None
    try:
        import numpy as np
        topic_emb = enc.encode(topic, convert_to_numpy=True)
        art_emb = enc.encode(
            f"{article.title}. {article.summary[:300]}", convert_to_numpy=True
        )
        cosine = float(
            np.dot(topic_emb, art_emb)
            / (np.linalg.norm(topic_emb) * np.linalg.norm(art_emb) + 1e-8)
        )
        return max(0.0, cosine)
    except Exception as exc:
        logger.debug("Semantic scoring error: %s", exc)
        return None


# ── Phrase gate ────────────────────────────────────────────────────────────────

def _passes_phrase_gate(article: Article, topic: str, topic_phrases: dict[str, list[str]]) -> bool:
    phrases = topic_phrases.get(topic)
    if not phrases:
        return True
    haystack = f"{article.title} {article.summary}".lower()
    return any(p.lower() in haystack for p in phrases)


# ── Public API ─────────────────────────────────────────────────────────────────

def score_articles(
    articles: list[Article],
    topics: list[str],
    tools: list[str],
    use_semantic: bool = False,
    min_score: float = 0.2,
    topic_phrases: dict[str, list[str]] | None = None,
) -> list[Article]:
    """Score and filter articles; assign personalization tier and why_matters.

    Scoring:
      45% topic keyword overlap
      18% tool keyword match
      17% recency (7-day decay)
      10% tier bonus
      10% popularity

    After scoring:
    - Low-quality articles (hype, beginner tutorials) are dropped
    - Each article gets a personalization tier (🔥 / ⚙️ / 🧠) stored in content_type
    - Each article gets a why_matters note
    """
    _phrases = topic_phrases or {}
    scored: list[Article] = []
    excluded = 0

    for article in articles:
        # Drop low-quality content early
        if _is_low_quality(article):
            excluded += 1
            continue

        best_score = 0.0
        best_topic = None

        for topic in topics:
            if not _passes_phrase_gate(article, topic, _phrases):
                continue

            kw = _keyword_score(article, topic, tools)

            if use_semantic:
                sem = _semantic_score(article, topic)
                score = 0.5 * kw + 0.5 * sem if sem is not None else kw
            else:
                score = kw

            if score > best_score:
                best_score = score
                best_topic = topic

        if best_score >= min_score:
            article.relevance_score = round(best_score, 4)
            article.assigned_topic = best_topic

            # Personalization layer
            d_score = _domain_score(article)
            article.content_type = _personalization_tier(article, best_score, d_score)
            article.why_matters = _why_matters(article)

            scored.append(article)

    logger.info(
        "Scored %d -> %d articles (min_score=%.2f, excluded=%d low-quality)",
        len(articles),
        len(scored),
        min_score,
        excluded,
    )
    return scored
