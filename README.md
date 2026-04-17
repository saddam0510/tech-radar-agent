# 🔭 Tech Radar Agent

A local, fully automated weekly newsletter agent that fetches AI & tech content from multiple sources, filters it by topic relevance, and delivers a clean HTML email digest — all running on your machine with no cloud dependency.

---

## ✨ Features

- **11 source connectors** across 3 tiers — arXiv, GitHub (search + releases + trending), HuggingFace (blog + models hub), Papers with Code, Semantic Scholar, ACL Anthology, Official Blogs (OpenAI, DeepMind, Meta AI, Databricks, Teradata, Docker, K8s, Airflow, TDS, Import AI, The Batch), Medium, Reddit, YouTube, LinkedIn (placeholder)
- **3-tier source system** — Tier 1 (high-signal) surfaces above Tier 2 (community) in every section
- **Topic → source affinity routing** — each topic has preferred sources that receive a relevance boost
- **Composite ranking** — tier + relevance + popularity (stars/upvotes/views/citations) + recency
- **Content-type sections** — Research 🔬 · Tools & Releases 🔧 · News & Articles 📰 · Open Source 💻
- **Topic badges** — each article tagged with its matched topic (LLMs, Docker, Airflow, etc.)
- **Deduplication** — URL-exact + fuzzy Jaccard title similarity
- **Optional LLM summarization** — Claude or OpenAI condenses long article summaries
- **Optional semantic matching** — sentence-transformers for embedding-based relevance scoring
- **Clean HTML email** — responsive, mobile-friendly, dark-header design with stats bar + TOC
- **Weekly scheduler** — APScheduler (local) or Apache Airflow DAG
- **Configurable everything** — topics, users, sources, schedule, filters via `config/config.yaml`

---

## 📁 Project Structure

```
tech_radar/
├── config/
│   └── config.yaml           # topics, users, sources, schedule, filters
├── sources/                  # pluggable source connectors
│   ├── base.py               # Article dataclass (tier, popularity_score) + BaseSource ABC
│   ├── arxiv_source.py       # Tier 1
│   ├── github_source.py      # Tier 1 — releases + search + trending
│   ├── huggingface_source.py # Tier 1 — blog RSS + models hub
│   ├── papers_with_code_source.py  # Tier 1 — HF Papers API
│   ├── semantic_scholar_source.py  # Tier 1 — academic search + citations
│   ├── acl_source.py         # Tier 1 — NLP venue papers
│   ├── official_blogs_source.py    # Tier 1 — 11 curated official blogs
│   ├── medium_source.py
│   ├── youtube_source.py
│   ├── reddit_source.py
│   ├── docs_source.py
│   ├── scholar_source.py
│   ├── linkedin_source.py
│   └── __init__.py          # source registry
│   ├── medium_source.py      # Tier 2
│   ├── reddit_source.py      # Tier 2 — hot posts, min_upvotes filter
│   ├── youtube_source.py     # Tier 2 — channel allowlist, min_views filter
│   ├── docs_source.py        # Tier 2 — generic RSS (disabled by default)
│   ├── scholar_source.py     # Tier 3 (disabled)
│   ├── linkedin_source.py    # Tier 3 placeholder (disabled)
│   └── __init__.py           # source registry with tier metadata
├── processing/
│   ├── filter.py             # scoring: keywords + tools + recency + tier + popularity
│   ├── ranker.py             # tier-aware composite ranking per section
│   ├── topic_router.py       # topic → source affinity map + boost
│   └── deduplicator.py       # URL-exact + Jaccard title dedup
├── llm/
│   └── summarizer.py        # Claude / OpenAI enrichment (optional)
├── newsletter/
│   ├── builder.py           # Jinja2 renderer
│   └── templates/
│       └── newsletter.html  # responsive HTML email template
├── delivery/
│   └── email_sender.py      # SMTP sender
├── scheduler/
│   ├── local_scheduler.py   # APScheduler (blocking)
│   └── airflow_dag.py       # optional Airflow DAG
├── utils/
│   └── logger.py
├── logs/                    # auto-created — run logs + HTML previews
├── main.py                  # CLI entry point
├── requirements.txt
└── .env.example
```

---

## 🚀 Quick Start

### 1. Clone & install

```bash
git clone https://github.com/YOUR_USERNAME/tech-radar-agent.git
cd tech-radar-agent
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env with your credentials (see below)
```

### 3. Run

```bash
# Dry run — fetch articles, print counts, no email
python main.py --dry-run

# Preview — generate HTML newsletter, save to logs/, no email
python main.py --preview

# Full run — fetch, build, send email
python main.py

# Start weekly scheduler (blocking)
python main.py --schedule
```

---

## ⚙️ Configuration

### `config/config.yaml`

```yaml
schedule:
  weekday: monday   # day to send the newsletter
  time: "08:00"     # local time (24h)

topics:
  - LLMs
  - GenAI
  - AI Agents
  - Docker
  - Kubernetes
  - Airflow
  # ... add/remove freely

users:
  - email: you@example.com
    name: Your Name

sources:
  arxiv:
    enabled: true
  github:
    enabled: true
  medium:
    enabled: true
  reddit:
    enabled: false   # requires Reddit API credentials
```

### `.env`

```env
# Email (required)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your_app_password   # Gmail App Password, not your login password

# GitHub (optional — raises rate limit from 60 to 5000 req/hr)
GITHUB_TOKEN=ghp_...

# Reddit (optional)
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USER_AGENT=TechRadarBot/1.0

# YouTube (optional)
YOUTUBE_API_KEY=AIza...

# LLM summarization (optional — set llm.enabled: true in config.yaml)
ANTHROPIC_API_KEY=sk-ant-...
```

---

## 📰 Newsletter Sections

| Section | Sources | Description |
|---|---|---|
| 🔬 **Research** | arXiv, Google Scholar | Academic papers & preprints |
| 🔧 **Tools & Releases** | GitHub Releases, PyPI | New releases & packages |
| 📰 **News & Articles** | Medium, Blog RSS | Industry news & tutorials |
| 💻 **Open Source** | GitHub repos | Trending & relevant repositories |

Each article shows:
- **Topic badge** — matched topic (e.g. `LLMs`, `Docker`, `Airflow`)
- **Source tag** — where it came from
- **1–2 line summary** — optionally enriched by LLM
- **Clickable title** and "Read more" link

---

## 🔌 Adding a New Source

1. Create `sources/my_source.py`, subclass `BaseSource`, implement `async def fetch(...) -> list[Article]`
2. Register it in `sources/__init__.py` → `SOURCE_REGISTRY`
3. Add a config block under `sources:` in `config.yaml` with `enabled: true`

---

## 🧠 Semantic Matching (optional)

For better relevance scoring beyond keyword overlap, install sentence-transformers:

```bash
pip install sentence-transformers torch
```

Then enable in `config.yaml`:

```yaml
processing:
  semantic_matching: true
```

Uses `all-MiniLM-L6-v2` locally — no API key required.

---

## 🗓️ Scheduling

### Local (APScheduler)
```bash
python main.py --schedule
# Keep the terminal open — runs every configured weekday at the configured time
```

### Apache Airflow
Drop `scheduler/airflow_dag.py` into your Airflow DAGs folder. Set `PROJECT_ROOT` to your installation path. The DAG runs every Monday at 08:00 by default.

---

## 📋 Topics Tracked

Teradata ML · LLMs · GenAI · AI · AI Agents · NLP · Spark · Docker · Kubernetes · MCPs · Airflow · Analysis · Machine Learning

---

## 🛠️ Tech Stack

- **Python 3.12+**
- `praw` · `arxiv` · `feedparser` · `requests` — source connectors
- `jinja2` — HTML templating
- `APScheduler` — local scheduling
- `anthropic` — optional LLM summarization
- `sentence-transformers` — optional semantic matching

---

## 📄 License

MIT
