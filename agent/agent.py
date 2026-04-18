"""Hybrid agentic runner.

Architecture:
  Phase 1 — Mandatory fetches (deterministic, always runs)
  Phase 2 — Agentic loop: LLM decides each iteration whether to fetch one
             more optional source OR finalize the newsletter
  Phase 3 — Fallback build if loop exits without building

This design is reliable with smaller Ollama models that lose tool-calling
fidelity after multi-turn conversations, while preserving genuine
agentic decision-making in Phase 2.
"""
from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from langchain_core.messages import ToolMessage

from agent.state import get_state, reset_state
from agent.tools import (
    configure, get_tools,
    fetch_from_source, check_coverage, build_newsletter,
)

logger = logging.getLogger(__name__)

# Mandatory Tier 1 sources — always fetched regardless of LLM
_MANDATORY_SOURCES = ["arxiv", "github", "huggingface"]

# Optional sources — LLM decides whether to use these based on coverage
_OPTIONAL_SOURCES = [
    "official_blogs",
    "papers_with_code",
    "semantic_scholar",
    "acl",
    "medium",
]


def run_agent(config: dict, preview: bool = False) -> None:
    reset_state()
    configure(config)

    agent_cfg: dict = config.get("agent", {})
    model: str = agent_cfg.get("model", "llama3.1")
    base_url: str = agent_cfg.get("ollama_base_url", "http://localhost:11434")
    max_iterations: int = agent_cfg.get("max_iterations", 20)
    min_target: int = agent_cfg.get("min_articles_target", 15)

    logger.info("Agent starting — model=%s", model)

    llm = ChatOllama(model=model, base_url=base_url, temperature=0)
    # Decision tools only: fetch one source or finalize
    decision_tools = [fetch_from_source, build_newsletter]
    decision_llm = llm.bind_tools(decision_tools)
    tools_by_name = {t.name: t for t in get_tools()}

    preview_flag = "True" if preview else "False"

    # ── Phase 1: Mandatory fetches ─────────────────────────────────────────────
    logger.info("Phase 1: mandatory fetches (%s)", ", ".join(_MANDATORY_SOURCES))
    for source in _MANDATORY_SOURCES:
        result = fetch_from_source.invoke({"source_name": source, "limit": 25})
        logger.info("[mandatory] %s -> %s", source, result)

    # ── Phase 2: Agentic loop ──────────────────────────────────────────────────
    logger.info("Phase 2: agentic coverage loop (target=%d articles)", min_target)
    newsletter_built = False

    for iteration in range(max_iterations):
        state = get_state()
        coverage = check_coverage.invoke({})
        remaining = [s for s in _OPTIONAL_SOURCES if s not in state.fetched_sources]

        if not remaining:
            logger.info("All optional sources exhausted — proceeding to build.")
            break

        decision_msg = (
            f"Current article coverage:\n{coverage}\n\n"
            f"Target: {min_target} articles minimum.\n"
            f"Optional sources not yet fetched: {remaining}\n\n"
            f"Decision: "
            f"- If you need more articles (fewer than {min_target}), call fetch_from_source "
            f"with ONE source from the remaining list.\n"
            f"- If you have {min_target}+ articles with good coverage, call build_newsletter "
            f"with preview={preview_flag}.\n\n"
            f"Call exactly ONE tool now."
        )

        resp = decision_llm.invoke([HumanMessage(content=decision_msg)])

        if not resp.tool_calls:
            logger.info("[agentic iter %d] LLM made no tool call — using coverage count.", iteration + 1)
            if len(state.articles) >= min_target:
                break
            # Force next optional source
            source = remaining[0]
            result = fetch_from_source.invoke({"source_name": source, "limit": 20})
            logger.info("[agentic fallback] %s -> %s", source, result)
            continue

        for tc in resp.tool_calls:
            tool_name = tc["name"]
            tool_args = tc.get("args", {})
            logger.info("[agentic iter %d] %s(%s)", iteration + 1, tool_name, tool_args)

            result = tools_by_name[tool_name].invoke(tool_args)
            logger.info("[agentic iter %d] result: %s", iteration + 1, str(result)[:200])

            if tool_name == "build_newsletter":
                newsletter_built = True
                break

        if newsletter_built:
            break

    # ── Phase 3: Fallback build ────────────────────────────────────────────────
    if not newsletter_built:
        logger.info("Phase 3: building newsletter (fallback)")
        result = build_newsletter.invoke({"preview": preview})
        logger.info("Newsletter: %s", result)

    state = get_state()
    logger.info(
        "Agent done. Articles: %d | Sources: %s",
        len(state.articles),
        ", ".join(sorted(state.fetched_sources)),
    )
