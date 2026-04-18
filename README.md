# 🔭 Tech Radar Agent

A fully local, agentic AI newsletter pipeline — an LLM agent decides what to fetch, filters content by professional context, and delivers a personalized HTML email digest. No cloud dependency, no subscription.

Built for a **Senior Data Scientist at Teradata** working in Government, Telco, and Banking.

---

## ✨ Features

### Agentic Core
- **LLM-driven orchestration** — Ollama (llama3.1) decides which sources to query and when to stop
- **Hybrid agent loop** — mandatory Tier 1 fetches + LLM coverage evaluation each iteration
- **Tool-use pattern** — sources, coverage check, and newsletter build are LangChain tools

### Context-Aware Filtering
- **Domain scoring** — articles scored against Telco / Banking / Government keywords
- **Use-case matching** — entity resolution, fraud detection, record linkage, NLP on tabular data
- **Stack relevance** — PySpark, Teradata ML, Airflow, Kubernetes, Docker, MLOps
- **Exclusion rules** — beginner tutorials, consumer AI hype, funding news filtered out
- **"Why it matters"** — each article gets a personalized relevance note

### Personalized Sections
| Section | What it contains |
|---|---|
| 🔥 **Directly Applicable** | High domain match — entity matching, fraud, Teradata, PySpark, Airflow |
| ⚙️ **Tools & Stack Updates** | New releases in your exact stack |
| 🧠 **Worth Knowing** | Relevant but less immediately actionable |

### Source Coverage — 11 connectors across 3 tiers
| Tier | Sources |
|---|---|
| Tier 1 (high signal) | arXiv · GitHub (releases + search + trending) · HuggingFace · Papers with Code · Semantic Scholar · ACL Anthology · Official Blogs (OpenAI, DeepMind, Meta AI, Databricks, Teradata, Docker, K8s, Airflow, TDS) |
| Tier 2 (community) | Medium · Reddit · YouTube |
| Tier 3 (disabled) | Google Scholar · LinkedIn |

### Other
- **3-tier source system** — Tier 1 surfaces above Tier 2 in ranking
- **Topic → source affinity routing** — preferred sources per topic receive a relevance boost
- **Composite ranking** — tier + domain score + relevance + popularity + recency
- **Deduplication** — URL-exact + fuzzy Jaccard title similarity
- **Top 10 per section** — up to 10 articles per personalized section (30 total)
- **Optional LLM summarization** — Claude or OpenAI condenses long summaries
- **Optional semantic matching** — sentence-transformers embedding-based scoring
- **Clean HTML email** — responsive, mobile-friendly, dark-header with stats bar + TOC
- **Weekly scheduler** — APScheduler (local) or Apache Airflow DAG

---

## 📁 Project Structure

```
tech_radar/
├── agent/
│   ├── agent.py          # hybrid agentic runner (mandatory fetches + LLM loop)
│   ├── prompts.py        # system prompt with user context
│   ├── state.py          # shared article accumulator across tool calls
│   └── tools.py          # LangChain tools: fetch_from_source, check_coverage, build_newsletter
├── config/
│   └── config.yaml       # topics, users, sources, schedule, filters, agent config
├── sources/              # pluggable source connectors
│   ├── base.py           # Article dataclass + BaseSource ABC
│   ├── arxiv_source.py
│   ├── github_source.py
│   ├── huggingface_source.py
│   ├── papers_with_code_source.py
│   ├── semantic_scholar_source.py
│   ├── acl_source.py
│   ├── official_blogs_source.py
│   ├── medium_source.py
│   ├── reddit_source.py
│   ├── youtube_source.py
│   └── __init__.py
├── processing/
│   ├── filter.py         # domain scoring, exclusion rules, personalization tier, why_matters
│   ├── ranker.py         # tier-aware composite ranking per section
│   ├── topic_router.py   # topic → source affinity map + boost
│   └── deduplicator.py   # URL-exact + Jaccard title dedup
├── llm/
│   └── summarizer.py     # Claude / OpenAI enrichment (optional)
├── newsletter/
│   ├── builder.py        # Jinja2 renderer
│   └── templates/
│       └── newsletter.html
├── delivery/
│   └── email_sender.py
├── scheduler/
│   ├── local_scheduler.py
│   └── airflow_dag.py
├── utils/
│   └── logger.py
├── logs/                 # auto-created — run logs + HTML previews
├── main.py               # CLI entry point
├── requirements.txt
└── .env.example
```

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Ollama + pull model

```bash
# Install Ollama from https://ollama.com
ollama pull llama3.1
```

### 3. Configure credentials

```bash
cp .env.example .env
# Edit .env — SMTP credentials are required, others optional
```

### 4. Run

```bash
# Agentic mode (recommended) — LLM decides what to fetch
python main.py --agent

# Agentic preview — build HTML, skip email
python main.py --agent --preview

# Classic pipeline mode (no Ollama required)
python main.py

# Dry run — fetch only, print counts
python main.py --dry-run

# Weekly scheduler
python main.py --schedule
```

---

## ⚙️ Configuration

### `config/config.yaml`

```yaml
agent:
  model: llama3.1               # Ollama model
  ollama_base_url: http://localhost:11434
  min_articles_target: 15       # agent fetches until it hits this
  max_iterations: 20

newsletter:
  max_articles_per_topic: 10
  max_per_section: 10
  days_back: 7

topics:
  - Teradata ML
  - PySpark
  - Airflow
  - Entity Resolution
  - Record Linkage
  - Fraud Detection
  - Data Quality
  - Data Engineering
  - Feature Engineering
  - MLOps
  - NLP
  - LLMs
  - AI Agents
  - Kubernetes
  - Docker
```

### `.env`

```env
# Email (required)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your_app_password

# GitHub (optional — raises rate limit from 60 to 5000 req/hr)
GITHUB_TOKEN=ghp_...

# Reddit (optional — enable reddit source in config.yaml)
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USER_AGENT=TechRadarBot/1.0

# YouTube (optional)
YOUTUBE_API_KEY=AIza...

# LLM summarization (optional)
ANTHROPIC_API_KEY=sk-ant-...
```

---

## 🧠 Personalization Layer

The filter layer scores every article against the user's professional context:

| Signal | Examples | Weight |
|---|---|---|
| Use-case match | entity resolution, fraud, deduplication, customer 360 | High |
| Stack match | PySpark, Teradata ML, Airflow, Kubernetes | High |
| Industry match | telco, banking, government, enterprise | Medium |
| Tier bonus | arXiv > Medium | Low |

Articles are then assigned to one of three sections:
- **🔥 Directly Applicable** — strong domain + stack signal
- **⚙️ Tools & Stack Updates** — release/update in a stack tool
- **🧠 Worth Knowing** — relevant but less immediately actionable

Each article shows a **"Why it matters"** callout explaining the personal relevance.

---

## 🔌 Adding a New Source

1. Create `sources/my_source.py`, subclass `BaseSource`, implement `async def fetch(...) -> list[Article]`
2. Register it in `sources/__init__.py` → `SOURCE_REGISTRY`
3. Add a config block under `sources:` in `config.yaml` with `enabled: true`

---

## 🗓️ Scheduling

### Local (APScheduler)
```bash
python main.py --schedule
```

### Apache Airflow
Drop `scheduler/airflow_dag.py` into your DAGs folder.

---

## 🛠️ Tech Stack

- **Python 3.12+**
- `langchain` · `langchain-ollama` · `langgraph` — agentic orchestration
- `ollama` (llama3.1) — local LLM, free, no API key
- `praw` · `arxiv` · `feedparser` · `requests` — source connectors
- `jinja2` — HTML templating
- `APScheduler` — local scheduling
- `anthropic` — optional LLM summarization

---

## 📄 License

MIT
