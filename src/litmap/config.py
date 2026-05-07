from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv as _load_dotenv
except ModuleNotFoundError:  # pragma: no cover - dependency is present in uv env
    def _load_dotenv(*_args: object, **_kwargs: object) -> bool:
        return False

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib  # type: ignore[no-redef]


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Secrets:
    semantic_scholar_api_key: str | None
    openalex_api_key: str | None
    openalex_mailto: str | None
    crossref_mailto: str | None
    openai_api_key: str | None
    openreview_username: str | None
    openreview_password: str | None


def load_secrets(env_path: Path | None = None) -> Secrets:
    _load_env_file(env_path or PROJECT_ROOT / ".env")

    return Secrets(
        semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY") or None,
        openalex_api_key=os.getenv("OPENALEX_API_KEY") or None,
        openalex_mailto=os.getenv("OPENALEX_MAILTO") or None,
        crossref_mailto=os.getenv("CROSSREF_MAILTO") or None,
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openreview_username=os.getenv("OPENREVIEW_USERNAME") or None,
        openreview_password=os.getenv("OPENREVIEW_PASSWORD") or None,
    )


def _load_env_file(path: Path) -> None:
    _load_dotenv(path)
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_env_value(value.strip())
        if key and value and not os.getenv(key):
            os.environ[key] = value


def _strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_project_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or PROJECT_ROOT / "config.toml"

    with config_path.open("rb") as f:
        return tomllib.load(f)


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path
