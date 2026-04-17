"""GitHub source — searches repos and fetches recent releases."""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

import requests

from sources.base import Article, BaseSource
from utils.logger import get_logger

logger = get_logger("source.github")

_GH_API = "https://api.github.com"


class GitHubSource(BaseSource):
    name = "GitHub"

    def _headers(self) -> dict:
        h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
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
        queries: list[str] = self.config.get("search_queries", [])
        max_per_query: int = self.config.get("max_results_per_query", 10)
        include_releases: bool = self.config.get("include_releases", True)

        articles: list[Article] = []

        # ── Repo search ───────────────────────────────────────────────────────
        for q in queries:
            try:
                resp = requests.get(
                    f"{_GH_API}/search/repositories",
                    params={"q": q, "sort": "updated", "order": "desc", "per_page": max_per_query},
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
                        )
                    )
            except Exception as exc:
                logger.warning("GitHub search '%s' error: %s", q, exc)

        # ── Latest releases from watched repos ────────────────────────────────
        if include_releases:
            watched = [
                "apache/airflow",
                "apache/spark",
                "kubernetes/kubernetes",
                "docker/compose",
                "huggingface/transformers",
                "langchain-ai/langchain",
                "run-llama/llama_index",
                "Teradata/teradataml",
            ]
            for repo_path in watched:
                try:
                    resp = requests.get(
                        f"{_GH_API}/repos/{repo_path}/releases/latest",
                        headers=self._headers(),
                        timeout=10,
                    )
                    if resp.status_code == 404:
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
                            title=f"{repo_path} — {rel['name'] or rel['tag_name']}",
                            link=rel["html_url"],
                            summary=body or "New release published.",
                            date=pub,
                            source="GitHub Releases",
                            content_type="Tools & Releases",
                        )
                    )
                except Exception as exc:
                    logger.warning("GitHub release %s error: %s", repo_path, exc)

        logger.debug("GitHub → %d articles", len(articles))
        return articles
