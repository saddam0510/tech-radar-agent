"""LangChain tools that wrap the existing source and pipeline modules.

Three tools are exposed to the agent:
  fetch_from_source  — fetch articles from one named source
  check_coverage     — inspect what has been collected so far
  build_newsletter   — run the processing pipeline and send / preview
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging

from langchain_core.tools import tool

from agent.state import get_state
from sources import SOURCE_REGISTRY

logger = logging.getLogger(__name__)

# Config is injected once at agent startup via configure()
_config: dict = {}


def configure(config: dict) -> None:
    """Inject pipeline config before running the agent."""
    global _config
    _config = config


def _run_async(coro):
    """Run an async coroutine from a sync context (safe on Windows)."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


# ── Tool 1: fetch from a named source ─────────────────────────────────────────

@tool
def fetch_from_source(source_name: str, limit: int = 25) -> str:
    """Fetch recent AI/tech articles from a named source.

    source_name: one of arxiv, github, huggingface, papers_with_code,
                 semantic_scholar, acl, official_blogs, medium, reddit, youtube
    limit: max articles to fetch (default 25, lower = faster)

    Returns a text summary of what was found.
    """
    state = get_state()

    if source_name in state.fetched_sources:
        return f"Already fetched '{source_name}' this run — skipping to avoid duplicates."

    if source_name not in SOURCE_REGISTRY:
        available = ", ".join(SOURCE_REGISTRY.keys())
        return f"Unknown source '{source_name}'. Available: {available}"

    topics: list[str] = _config.get("topics", [])
    tools_list: list[str] = _config.get("tools", [])
    days_back: int = _config.get("newsletter", {}).get("days_back", 7)
    sources_config: dict = _config.get("sources", {})

    cls, default_tier = SOURCE_REGISTRY[source_name]
    cfg = dict(sources_config.get(source_name, {}))
    cfg.setdefault("tier", default_tier)
    cfg["enabled"] = True

    # Apply limit to whichever key the source uses
    for limit_key in ("max_results", "max_results_per_query", "limit_per_subreddit", "max_models"):
        if limit_key in cfg:
            cfg[limit_key] = min(cfg[limit_key], limit)

    try:
        src = cls(cfg)
        articles = _run_async(src.fetch(topics, tools_list, days_back))
        added = state.add(articles, source_name)

        if not articles:
            return f"'{source_name}' returned 0 articles. Total collected: {len(state.articles)}."

        # Build a topic summary from assigned_topic if available
        from collections import Counter
        topic_hits = Counter(
            getattr(a, "assigned_topic", None) or "?" for a in articles
        )
        top = ", ".join(f"{t}({n})" for t, n in topic_hits.most_common(4))

        return (
            f"Fetched {len(articles)} articles from '{source_name}' "
            f"({added} new after dedup check). "
            f"Topics: {top or 'not yet scored'}. "
            f"Total collected so far: {len(state.articles)}."
        )
    except Exception as exc:
        logger.error("fetch_from_source(%s) failed: %s", source_name, exc)
        return f"Error fetching '{source_name}': {exc}. Move on to the next source."


# ── Tool 2: check coverage ─────────────────────────────────────────────────────

@tool
def check_coverage() -> str:
    """Check how many articles have been collected and which topics are covered.

    Call this after fetching from a few sources to decide whether to fetch more
    or proceed to build_newsletter.
    """
    return get_state().summary()


# ── Tool 3: build and send newsletter ─────────────────────────────────────────

@tool
def build_newsletter(preview: bool = False) -> str:
    """Run the processing pipeline on collected articles and send (or preview) the newsletter.

    preview=True  → save HTML to disk, do NOT send email (safe for testing)
    preview=False → build HTML and send email to all configured recipients

    Call this once you are satisfied with article coverage.
    """
    state = get_state()

    if not state.articles:
        return "No articles collected yet. Fetch from at least one source first."

    from processing.deduplicator import deduplicate
    from processing.filter import score_articles
    from processing.topic_router import apply_affinity_boost
    from processing.ranker import group_and_rank
    from newsletter.builder import build_html, save_preview
    from delivery.email_sender import send_newsletter

    topics: list[str] = _config.get("topics", [])
    tools_list: list[str] = _config.get("tools", [])
    newsletter_cfg: dict = _config.get("newsletter", {})
    proc_cfg: dict = _config.get("processing", {})
    topic_phrases: dict = _config.get("topic_phrases", {})
    users: list[dict] = _config.get("users", [])

    raw = state.articles
    logger.info("Agent collected %d raw articles — running processing pipeline", len(raw))

    articles = deduplicate(raw, title_threshold=proc_cfg.get("dedup_title_similarity", 0.85))
    articles = score_articles(
        articles,
        topics=topics,
        tools=tools_list,
        use_semantic=proc_cfg.get("semantic_matching", False),
        min_score=proc_cfg.get("min_relevance_score", 0.2),
        topic_phrases=topic_phrases,
    )
    articles = apply_affinity_boost(articles)

    sections = group_and_rank(
        articles,
        topics=topics,
        max_per_topic=newsletter_cfg.get("max_articles_per_topic", 5),
        max_per_section=newsletter_cfg.get("max_per_section", 5),
    )

    total = sum(len(v) for v in sections.values())
    if total == 0:
        return "Processing pipeline returned 0 articles above the relevance threshold. Try fetching from more sources."

    html = build_html(
        sections,
        title=newsletter_cfg.get("title", "Weekly Tech Radar"),
        subtitle=newsletter_cfg.get("subtitle", "Your curated AI & Technology digest"),
    )
    preview_path = save_preview(html)

    if preview:
        return (
            f"Newsletter built in preview mode. "
            f"{total} articles across {len(sections)} sections. "
            f"HTML saved to: {preview_path}. Email NOT sent."
        )

    send_newsletter(html, recipients=users)
    return (
        f"Newsletter sent! "
        f"{total} articles across {len(sections)} sections. "
        f"Recipients: {', '.join(u['email'] for u in users)}."
    )


def get_tools() -> list:
    return [fetch_from_source, check_coverage, build_newsletter]
