#!/usr/bin/env python3
"""Tech Radar Agent — main pipeline orchestrator.

Usage:
  python main.py              # run the full pipeline once (fetch → email)
  python main.py --preview    # run pipeline, save HTML to disk, skip email
  python main.py --schedule   # start the weekly scheduler (blocking)
  python main.py --dry-run    # fetch only; print article counts; no email
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

# ── bootstrap ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")  # load .env before any other import that reads os.environ

import yaml  # noqa: E402

from delivery.email_sender import send_newsletter  # noqa: E402
from llm.summarizer import enrich_summaries  # noqa: E402
from newsletter.builder import build_html, save_preview  # noqa: E402
from processing.deduplicator import deduplicate  # noqa: E402
from processing.filter import score_articles  # noqa: E402
from processing.ranker import group_and_rank  # noqa: E402
from sources import build_sources  # noqa: E402
from utils.logger import get_logger  # noqa: E402

logger = get_logger("main")


def load_config() -> dict:
    config_path = ROOT / "config" / "config.yaml"
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


async def _fetch_all(sources, topics, tools, days_back):
    """Fetch from all sources concurrently."""
    tasks = [src.fetch(topics, tools, days_back) for src in sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    articles = []
    for src, result in zip(sources, results):
        if isinstance(result, Exception):
            logger.error("Source '%s' failed: %s", src.name, result)
        else:
            logger.info("Source '%s' -> %d articles", src.name, len(result))
            articles.extend(result)
    return articles


def run(preview: bool = False, dry_run: bool = False) -> None:
    """Execute the full pipeline."""
    config = load_config()

    topics: list[str] = config["topics"]
    tools: list[str] = config["tools"]
    users: list[dict] = config["users"]
    newsletter_cfg: dict = config.get("newsletter", {})
    llm_cfg: dict = config.get("llm", {})
    proc_cfg: dict = config.get("processing", {})
    days_back: int = newsletter_cfg.get("days_back", 7)
    max_per_topic: int = newsletter_cfg.get("max_articles_per_topic", 5)

    # ── 1. Build sources ──────────────────────────────────────────────────────
    sources = build_sources(config.get("sources", {}))
    if not sources:
        logger.warning("No sources are enabled. Check config/config.yaml.")
        return

    logger.info("Pipeline starting: %d sources, %d topics", len(sources), len(topics))

    # ── 2. Fetch (async) ──────────────────────────────────────────────────────
    raw_articles = asyncio.run(_fetch_all(sources, topics, tools, days_back))
    logger.info("Total raw articles fetched: %d", len(raw_articles))

    if not raw_articles:
        logger.warning("No articles fetched. Aborting.")
        return

    # ── 3. Deduplicate ────────────────────────────────────────────────────────
    articles = deduplicate(
        raw_articles,
        title_threshold=proc_cfg.get("dedup_title_similarity", 0.85),
    )

    # ── 4. Score & filter ─────────────────────────────────────────────────────
    articles = score_articles(
        articles,
        topics=topics,
        tools=tools,
        use_semantic=proc_cfg.get("semantic_matching", False),
        min_score=proc_cfg.get("min_relevance_score", 0.2),
    )

    # ── 5. Group & rank by topic ──────────────────────────────────────────────
    sections = group_and_rank(articles, topics=topics, max_per_topic=max_per_topic)

    if dry_run:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print("\n=== DRY RUN RESULTS ===")
        for section, arts in sections.items():
            print(f"\n{'='*60}")
            print(f"  {section} - {len(arts)} articles")
            print(f"{'='*60}")
            for a in arts:
                title = a.title[:75].encode("ascii", errors="replace").decode("ascii")
                topic = f"[{a.assigned_topic}]" if a.assigned_topic else ""
                print(f"  * {topic} {title} ({a.source}) score={a.relevance_score:.2f}")
        return

    # ── 6. LLM enrichment (optional) ─────────────────────────────────────────
    if llm_cfg.get("enabled", False):
        logger.info("LLM summarisation enabled (provider=%s)", llm_cfg.get("provider"))
        sections = enrich_summaries(
            sections,
            provider=llm_cfg.get("provider", "claude"),
            model=llm_cfg.get("model", "claude-sonnet-4-6"),
            summarize_threshold=llm_cfg.get("summarize_threshold", 300),
        )

    # ── 7. Build HTML ─────────────────────────────────────────────────────────
    html = build_html(
        sections,
        title=newsletter_cfg.get("title", "Weekly Tech Radar"),
        subtitle=newsletter_cfg.get("subtitle", "Your curated AI & Technology digest"),
    )

    # ── 8. Save preview ───────────────────────────────────────────────────────
    preview_path = save_preview(html)

    if preview:
        logger.info("Preview mode — email NOT sent. Open: %s", preview_path)
        return

    # ── 9. Send email ─────────────────────────────────────────────────────────
    send_newsletter(html, recipients=users)
    logger.info("Pipeline complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Tech Radar Agent")
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Generate newsletter HTML and save to disk; do NOT send email.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch articles and print counts; do NOT build HTML or send email.",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Start the weekly scheduler (blocking — runs forever).",
    )
    args = parser.parse_args()

    if args.schedule:
        from scheduler.local_scheduler import start

        config = load_config()
        sched = config.get("schedule", {})
        start(weekday=sched.get("weekday", "monday"), time=sched.get("time", "08:00"))
        return

    run(preview=args.preview, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
