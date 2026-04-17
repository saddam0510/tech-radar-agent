"""Relevance filtering — keyword + tier + popularity scoring pipeline."""
from __future__ import annotations

import re
from typing import Optional

from sources.base import Article
from utils.logger import get_logger

logger = get_logger("processing.filter")

# Tier score contribution (tier 1 = full bonus, tier 3 = none)
_TIER_BONUS = {1: 1.0, 2: 0.5, 3: 0.0}


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"\b\w+\b", text.lower()))


def _keyword_score(article: Article, topic: str, tools: list[str]) -> float:
    """Base relevance: keyword overlap against topic + tools."""
    topic_tokens = _tokenize(topic)
    tool_tokens = {t.lower() for t in tools}
    haystack = _tokenize(f"{article.title} {article.summary}")

    topic_hits = len(topic_tokens & haystack) / max(len(topic_tokens), 1)
    tool_hit = 1.0 if haystack & tool_tokens else 0.0
    recency = max(0.0, 1.0 - article.age_days() / 7.0)
    tier_bonus = _TIER_BONUS.get(article.tier, 0.5)
    popularity = article.popularity_score  # already 0–1

    # Weighted sum — must equal 1.0
    return (
        0.45 * topic_hits
        + 0.18 * tool_hit
        + 0.17 * recency
        + 0.10 * tier_bonus
        + 0.10 * popularity
    )


# ── Optional semantic matching ────────────────────────────────────────────────

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


# ── Public API ────────────────────────────────────────────────────────────────

def score_articles(
    articles: list[Article],
    topics: list[str],
    tools: list[str],
    use_semantic: bool = False,
    min_score: float = 0.2,
) -> list[Article]:
    """Score each article against all topics; assign the best-matching one.

    Scoring components (keyword mode):
      45% topic keyword overlap
      18% tool keyword match
      17% recency (7-day decay)
      10% tier bonus (tier 1 = full, tier 3 = none)
      10% popularity (stars / upvotes / views / citations)

    When semantic mode is on, keyword and semantic scores are blended 50/50.
    Affinity boost is applied separately by topic_router.apply_affinity_boost().
    """
    scored: list[Article] = []

    for article in articles:
        best_score = 0.0
        best_topic = None

        for topic in topics:
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
            scored.append(article)

    logger.info(
        "Scored %d -> %d articles (min_score=%.2f, semantic=%s)",
        len(articles),
        len(scored),
        min_score,
        use_semantic,
    )
    return scored
