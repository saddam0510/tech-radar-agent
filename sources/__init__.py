"""Source registry — maps config keys to source classes.

To add a new source:
1. Create sources/my_source.py, subclass BaseSource, implement fetch()
2. Import and register it below
3. Add a config block in config.yaml with enabled: true
"""
from __future__ import annotations

from sources.acl_source import ACLSource
from sources.arxiv_source import ArxivSource
from sources.docs_source import DocsSource
from sources.github_source import GitHubSource
from sources.huggingface_source import HuggingFaceSource
from sources.linkedin_source import LinkedInSource
from sources.medium_source import MediumSource
from sources.official_blogs_source import OfficialBlogsSource
from sources.papers_with_code_source import PapersWithCodeSource
from sources.reddit_source import RedditSource
from sources.scholar_source import GoogleScholarSource
from sources.semantic_scholar_source import SemanticScholarSource
from sources.youtube_source import YouTubeSource

# Registry: config key → (class, default_tier)
SOURCE_REGISTRY: dict[str, tuple[type, int]] = {
    # ── Tier 1: High signal ────────────────────────────────────────────────
    "arxiv":             (ArxivSource,          1),
    "github":            (GitHubSource,         1),
    "huggingface":       (HuggingFaceSource,    1),
    "papers_with_code":  (PapersWithCodeSource, 1),
    "semantic_scholar":  (SemanticScholarSource, 1),
    "acl":               (ACLSource,            1),
    "official_blogs":    (OfficialBlogsSource,  1),
    # ── Tier 2: Semi-structured ────────────────────────────────────────────
    "medium":            (MediumSource,         2),
    "reddit":            (RedditSource,         2),
    "youtube":           (YouTubeSource,        2),
    "docs":              (DocsSource,           2),
    # ── Tier 3: Optional / noisy ──────────────────────────────────────────
    "google_scholar":    (GoogleScholarSource,  3),
    "linkedin":          (LinkedInSource,       3),
}


def build_sources(sources_config: dict) -> list:
    """Instantiate all enabled sources, injecting their tier from the registry."""
    instances = []
    for key, (cls, default_tier) in SOURCE_REGISTRY.items():
        cfg = dict(sources_config.get(key, {}))
        if not cfg.get("enabled", False):
            continue
        # Ensure tier is set (config can override the default)
        cfg.setdefault("tier", default_tier)
        instances.append(cls(cfg))

    tier_summary = {1: 0, 2: 0, 3: 0}
    for src in instances:
        tier_summary[getattr(src, "tier", 2)] += 1

    from utils.logger import get_logger
    log = get_logger("sources")
    log.info(
        "Sources loaded: %d total | T1=%d T2=%d T3=%d",
        len(instances),
        tier_summary[1],
        tier_summary[2],
        tier_summary[3],
    )
    return instances
