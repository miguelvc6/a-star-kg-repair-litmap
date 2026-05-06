from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from litmap.config import PROJECT_ROOT


def configure_logging(command: str, log_dir: Path | None = None) -> Path:
    directory = log_dir or PROJECT_ROOT / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = directory / f"{timestamp}_{command}.log"

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(message)s"))

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))

    root.addHandler(console)
    root.addHandler(file_handler)
    logging.getLogger(__name__).info("[log] writing terminal log to %s", log_path)
    return log_path
