from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Secrets:
    semantic_scholar_api_key: str | None
    openalex_api_key: str | None
    openalex_mailto: str | None
    crossref_mailto: str | None
    openai_api_key: str | None
    openreview_username: str | None
    openreview_password: str | None


def load_secrets() -> Secrets:
    load_dotenv(PROJECT_ROOT / ".env")

    return Secrets(
        semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY"),
        openalex_api_key=os.getenv("OPENALEX_API_KEY"),
        openalex_mailto=os.getenv("OPENALEX_MAILTO"),
        crossref_mailto=os.getenv("CROSSREF_MAILTO"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openreview_username=os.getenv("OPENREVIEW_USERNAME"),
        openreview_password=os.getenv("OPENREVIEW_PASSWORD"),
    )


def load_project_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or PROJECT_ROOT / "config.toml"

    with config_path.open("rb") as f:
        return tomllib.load(f)
