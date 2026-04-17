"""LinkedIn source — placeholder.

LinkedIn restricts automated access to its platform. Official options:

1. LinkedIn Marketing Developer Platform API (requires approved application):
   https://developer.linkedin.com/

2. LinkedIn RSS (for personal feeds — available on some account types):
   Your feed RSS: https://www.linkedin.com/feed/

3. Third-party services (Phantombuster, Apify) for scraping — check ToS.

To implement: subclass BaseSource, fill in `_fetch_sync`, and set enabled=true
in config.yaml along with any required credentials.
"""
from __future__ import annotations

from sources.base import Article, BaseSource
from utils.logger import get_logger

logger = get_logger("source.linkedin")


class LinkedInSource(BaseSource):
    name = "LinkedIn"

    async def fetch(
        self,
        topics: list[str],
        tools: list[str],
        days_back: int = 7,
    ) -> list[Article]:
        logger.info(
            "LinkedIn source is a placeholder. "
            "See sources/linkedin_source.py for implementation options."
        )
        return []
