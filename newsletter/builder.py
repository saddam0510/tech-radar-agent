"""Newsletter HTML builder — renders the Jinja2 template."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from sources.base import Article
from utils.logger import get_logger

logger = get_logger("newsletter.builder")

_TEMPLATE_DIR = Path(__file__).parent / "templates"

# Visual identity per section
SECTION_COLORS = {
    "🔥 Directly Applicable":  "#ef4444",   # red — highest urgency
    "⚙️ Tools & Stack Updates": "#0ea5e9",  # sky blue — engineering
    "🧠 Worth Knowing":         "#8b5cf6",  # violet — knowledge
}

SECTION_ICONS = {
    "🔥 Directly Applicable":  "🔥",
    "⚙️ Tools & Stack Updates": "⚙️",
    "🧠 Worth Knowing":         "🧠",
}


def build_html(
    sections: dict[str, list[Article]],
    title: str = "Weekly Tech Radar",
    subtitle: str = "Your curated AI & Technology digest",
) -> str:
    """Render the newsletter HTML given a dict of section → articles."""

    total_articles = sum(len(v) for v in sections.values())
    total_sections = len(sections)
    source_names = sorted(
        {a.source for articles in sections.values() for a in articles}
    )
    total_sources = len(source_names)
    generated_at = datetime.now(timezone.utc).strftime("%A, %B %d %Y")

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
    )
    template = env.get_template("newsletter.html")

    html = template.render(
        title=title,
        subtitle=subtitle,
        sections=sections,
        generated_at=generated_at,
        total_articles=total_articles,
        total_sections=total_sections,
        total_sources=total_sources,
        source_names=source_names,
        section_colors=SECTION_COLORS,
        section_icons=SECTION_ICONS,
    )

    logger.info(
        "Newsletter rendered: %d sections, %d articles, %d sources",
        total_sections,
        total_articles,
        total_sources,
    )
    return html


def save_preview(html: str, output_path: str | None = None) -> Path:
    """Write the rendered HTML to disk for local preview."""
    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(__file__).parent.parent / "logs" / f"newsletter_{ts}.html"
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    logger.info("Preview saved: %s", output_path)
    return output_path
