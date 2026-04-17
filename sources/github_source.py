"""GitHub source — repo search, releases, and trending approximation.

Tier 1: structured, high-signal code data with popularity signals (stars).
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone

import requests

from sources.base import Article, BaseSource
from utils.logger import get_logger

logger = get_logger("source.github")

_GH_API = "https://api.github.com"

_DEFAULT_WATCHED_REPOS = [
    "apache/airflow",
    "apache/spark",
    "kubernetes/kubernetes",
    "docker/compose",
    "huggingface/transformers",
    "huggingface/peft",
    "langchain-ai/langchain",
    "run-llama/llama_index",
    "ollama/ollama",
    "microsoft/autogen",
    "openai/openai-python",
    "anthropics/anthropic-sdk-python",
    "Teradata/teradataml",
]


class GitHubSource(BaseSource):
    name = "GitHub"
    default_tier = 1

    def _headers(self) -> dict:
        h = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = os.getenv("GITHUB_TOKEN", "").strip()
        if token and not token.startswith("ghp_..."):
            h["Authorization"] = f"Bearer {token}"
        return h

    async def fetch(
        self,
        topics: list[str],
        tools: list[str],
        days_back: int = 7,
    ) -> list[Article]:
        return await asyncio.to_thread(self._fetch_sync, topics, tools, days_back)

    def _fetch_sync(
        self,
        topics: list[str],
        tools: list[str],
        days_back: int,
    ) -> list[Article]:
        articles: list[Article] = []
        articles.extend(self._fetch_releases(days_back))
        articles.extend(self._fetch_repo_search(topics, tools, days_back))
        articles.extend(self._fetch_trending(days_back))
        logger.debug("GitHub -> %d articles total", len(articles))
        return articles

    # ── Releases ──────────────────────────────────────────────────────────────

    def _fetch_releases(self, days_back: int) -> list[Article]:
        watched: list[str] = self.config.get("watched_repos", _DEFAULT_WATCHED_REPOS)
        articles: list[Article] = []
        for repo_path in watched:
            try:
                resp = requests.get(
                    f"{_GH_API}/repos/{repo_path}/releases/latest",
                    headers=self._headers(),
                    timeout=10,
                )
                if resp.status_code in (404, 403):
                    continue
                resp.raise_for_status()
                rel = resp.json()
                pub = datetime.strptime(
                    rel["published_at"], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)
                if not self._is_recent(pub, days_back):
                    continue

                body = self._truncate(rel.get("body") or "")
                articles.append(
                    Article(
                        title=f"{repo_path} — {rel.get('name') or rel['tag_name']}",
                        link=rel["html_url"],
                        summary=body or "New release published.",
                        date=pub,
                        source="GitHub Releases",
                        content_type="Tools & Releases",
                        tier=1,
                    )
                )
            except Exception as exc:
                logger.debug("GitHub release %s: %s", repo_path, exc)
        return articles

    # ── Repo search ───────────────────────────────────────────────────────────

    def _fetch_repo_search(
        self, topics: list[str], tools: list[str], days_back: int
    ) -> list[Article]:
        queries: list[str] = self.config.get("search_queries", [])
        max_per_query: int = self.config.get("max_results_per_query", 10)
        min_stars: int = self.config.get("min_stars", 10)
        articles: list[Article] = []

        for q in queries:
            try:
                resp = requests.get(
                    f"{_GH_API}/search/repositories",
                    params={
                        "q": f"{q} stars:>{min_stars}",
                        "sort": "updated",
                        "order": "desc",
                        "per_page": max_per_query,
                    },
                    headers=self._headers(),
                    timeout=15,
                )
                resp.raise_for_status()
                for repo in resp.json().get("items", []):
                    pushed = datetime.strptime(
                        repo["pushed_at"], "%Y-%m-%dT%H:%M:%SZ"
                    ).replace(tzinfo=timezone.utc)
                    if not self._is_recent(pushed, days_back):
                        continue
                    stars = repo.get("stargazers_count", 0)
                    desc = self._truncate(repo.get("description") or "")
                    articles.append(
                        Article(
                            title=f"[GitHub] {repo['full_name']}",
                            link=repo["html_url"],
                            summary=desc or "No description provided.",
                            date=pushed,
                            source="GitHub",
                            tags=repo.get("topics", []),
                            content_type="Open Source",
                            tier=1,
                            popularity_score=self._normalise_popularity(stars, 50_000),
                        )
                    )
            except Exception as exc:
                logger.warning("GitHub search '%s': %s", q, exc)
        return articles

    # ── Trending (approximated via star-sorted recent repos) ──────────────────

    def _fetch_trending(self, days_back: int) -> list[Article]:
        if not self.config.get("include_trending", True):
            return []

        trending_queries: list[str] = self.config.get(
            "trending_topics",
            ["LLM", "agent", "RAG", "spark", "airflow", "kubernetes"],
        )
        max_per_query: int = self.config.get("max_trending_per_query", 5)
        min_stars: int = self.config.get("trending_min_stars", 50)
        since_date = (
            datetime.now(timezone.utc) - timedelta(days=days_back)
        ).strftime("%Y-%m-%d")

        articles: list[Article] = []
        for q in trending_queries:
            try:
                resp = requests.get(
                    f"{_GH_API}/search/repositories",
                    params={
                        "q": f"{q} created:>{since_date} stars:>{min_stars}",
                        "sort": "stars",
                        "order": "desc",
                        "per_page": max_per_query,
                    },
                    headers=self._headers(),
                    timeout=15,
                )
                resp.raise_for_status()
                for repo in resp.json().get("items", []):
                    created = datetime.strptime(
                        repo["created_at"], "%Y-%m-%dT%H:%M:%SZ"
                    ).replace(tzinfo=timezone.utc)
                    stars = repo.get("stargazers_count", 0)
                    desc = self._truncate(repo.get("description") or "")
                    articles.append(
                        Article(
                            title=f"[Trending] {repo['full_name']} ⭐ {stars:,}",
                            link=repo["html_url"],
                            summary=desc or "No description provided.",
                            date=created,
                            source="GitHub Trending",
                            tags=repo.get("topics", []),
                            content_type="Open Source",
                            tier=1,
                            popularity_score=self._normalise_popularity(stars, 10_000),
                        )
                    )
            except Exception as exc:
                logger.debug("GitHub trending '%s': %s", q, exc)
        return articles
