"""Source registry — maps source names to their classes."""
from __future__ import annotations

from sources.arxiv_source import ArxivSource
from sources.docs_source import DocsSource
from sources.github_source import GitHubSource
from sources.linkedin_source import LinkedInSource
from sources.medium_source import MediumSource
from sources.reddit_source import RedditSource
from sources.scholar_source import GoogleScholarSource
from sources.youtube_source import YouTubeSource

SOURCE_REGISTRY: dict[str, type] = {
    "reddit": RedditSource,
    "arxiv": ArxivSource,
    "github": GitHubSource,
    "youtube": YouTubeSource,
    "medium": MediumSource,
    "google_scholar": GoogleScholarSource,
    "docs": DocsSource,
    "linkedin": LinkedInSource,
}


def build_sources(sources_config: dict) -> list:
    """Instantiate all enabled sources from the config block."""
    instances = []
    for key, cls in SOURCE_REGISTRY.items():
        cfg = sources_config.get(key, {})
        if cfg.get("enabled", False):
            instances.append(cls(cfg))
    return instances
