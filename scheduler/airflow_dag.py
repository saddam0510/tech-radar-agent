"""Optional Airflow DAG — alternative to the local APScheduler.

Drop this file into your Airflow DAGs folder.
Requires: apache-airflow, and the tech_radar project in PYTHONPATH.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

# fmt: off
try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
except ImportError as e:
    raise ImportError(
        "apache-airflow is not installed. Install it or use the local scheduler instead."
    ) from e
# fmt: on

import sys

# Adjust this path to wherever the project lives on your Airflow worker
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _run_pipeline(**context) -> None:
    import asyncio
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")

    from main import run  # noqa: PLC0415

    asyncio.run(run()) if asyncio.iscoroutinefunction(run) else run()


default_args = {
    "owner": "tech_radar",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="tech_radar_weekly",
    description="Weekly Tech Radar newsletter",
    schedule_interval="0 8 * * MON",   # every Monday at 08:00 — matches config.yaml
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["tech_radar", "newsletter"],
) as dag:

    run_newsletter = PythonOperator(
        task_id="run_tech_radar_pipeline",
        python_callable=_run_pipeline,
        doc_md="""
        ## Tech Radar Pipeline
        Fetches content from all configured sources, filters by topic relevance,
        generates an HTML newsletter, and emails it to all configured recipients.
        """,
    )
