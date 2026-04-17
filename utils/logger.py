import logging
import sys
from pathlib import Path
from datetime import datetime


def get_logger(name: str = "tech_radar") -> logging.Logger:
    """Return a configured logger that writes to both console and a daily log file."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler (INFO and above) — force UTF-8 on Windows
    ch = logging.StreamHandler(
        open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1, closefd=False)
        if hasattr(sys.stdout, "fileno") else sys.stdout
    )
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler (DEBUG and above)
    log_dir = Path(__file__).resolve().parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"tech_radar_{datetime.now().strftime('%Y-%m-%d')}.log"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger
