"""Relevance filtering — keyword-based with optional semantic matching."""
from __future__ import annotations

import re
from typing import Optional

from sources.base import Article
from utils.logger import get_logger

logger = get_logger("processing.filter")


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"\b\w+\b", text.lower()))


def _keyword_score(article: Article, topic: str, tools: list[str]) -> float:
    """Return a 0–1 score based on keyword overlap."""
    topic_tokens = _tokenize(topic)
    tool_tokens = {t.lower() for t in tools}

    haystack = _tokenize(f"{article.title} {article.summary}")

    topic_hits = len(topic_tokens & haystack) / max(len(topic_tokens), 1)

    # Bonus for matching tool keywords
    tool_hit = 1.0 if haystack & tool_tokens else 0.0

    # Recency bonus (decays over 7 days)
    recency = max(0.0, 1.0 - article.age_days() / 7.0)

    return 0.55 * topic_hits + 0.25 * tool_hit + 0.20 * recency


# ── Optional semantic matching ────────────────────────────────────────────────

_encoder = None


def _get_encoder():
    global _encoder
    if _encoder is None:
        try:
            from sentence_transformers import SentenceTransformer
            _encoder = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Semantic matching enabled (sentence-transformers)")
        except ImportError:
            logger.info("sentence-transformers not installed — using keyword matching only")
            _encoder = False
    return _encoder


def _semantic_score(article: Article, topic: str) -> Optional[float]:
    enc = _get_encoder()
    if not enc:
        return None
    try:
        import numpy as np
        topic_emb = enc.encode(topic, convert_to_numpy=True)
        article_text = f"{article.title}. {article.summary[:300]}"
        art_emb = enc.encode(article_text, convert_to_numpy=True)
        cosine = float(
            np.dot(topic_emb, art_emb)
            / (np.linalg.norm(topic_emb) * np.linalg.norm(art_emb) + 1e-8)
        )
        return max(0.0, cosine)
    except Exception as exc:
        logger.debug("Semantic scoring error: %s", exc)
        return None


# ── Public API ─────────────────────────────────────────────────────────────────

def score_articles(
    articles: list[Article],
    topics: list[str],
    tools: list[str],
    use_semantic: bool = False,
    min_score: float = 0.2,
) -> list[Article]:
    """Assign relevance scores and filter out below-threshold articles.

    Each article is evaluated against every topic; the best-matching topic
    is assigned as article.assigned_topic and its score as article.relevance_score.
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
        "Filtered %d -> %d articles (min_score=%.2f)",
        len(articles),
        len(scored),
        min_score,
    )
    return scored
