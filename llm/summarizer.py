"""Optional LLM layer — condenses long article summaries via Claude or OpenAI."""
from __future__ import annotations

import os

from sources.base import Article
from utils.logger import get_logger

logger = get_logger("llm.summarizer")

_SYSTEM = (
    "You are a technical journalist. Given an article title and its raw description, "
    "write a crisp 1–2 sentence summary suitable for a newsletter. "
    "Be specific, factual, and omit marketing language."
)


def _summarize_with_claude(title: str, text: str, model: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model=model,
        max_tokens=120,
        system=_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": f"Title: {title}\n\nDescription: {text[:1500]}",
            }
        ],
    )
    return msg.content[0].text.strip()


def _summarize_with_openai(title: str, text: str, model: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = client.chat.completions.create(
        model=model,
        max_tokens=120,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": f"Title: {title}\n\nDescription: {text[:1500]}"},
        ],
    )
    return resp.choices[0].message.content.strip()


def enrich_summaries(
    sections: dict[str, list[Article]],
    provider: str = "claude",
    model: str = "claude-sonnet-4-6",
    summarize_threshold: int = 300,
) -> dict[str, list[Article]]:
    """Replace long/low-quality summaries with LLM-generated ones.

    Only articles whose summary exceeds *summarize_threshold* characters
    OR is very short (<30 chars) are sent to the LLM.
    """
    _summarize = (
        lambda t, s: _summarize_with_claude(t, s, model)
        if provider == "claude"
        else _summarize_with_openai(t, s, model)
    )

    for topic, articles in sections.items():
        for article in articles:
            raw_len = len(article.summary)
            if raw_len > summarize_threshold or raw_len < 30:
                try:
                    article.summary = _summarize(article.title, article.summary)
                    logger.debug("Summarised: %s", article.title[:60])
                except Exception as exc:
                    logger.warning("LLM summarisation failed for '%s': %s", article.title[:60], exc)

    return sections
