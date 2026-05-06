from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable


SPACE_RE = re.compile(r"\s+")
PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = "".join(ch for ch in value if unicodedata.category(ch) != "Cf")
    text = SPACE_RE.sub(" ", text)
    return text.strip()


def normalize_title(value: str | None) -> str:
    text = clean_text(value).casefold()
    text = PUNCT_RE.sub(" ", text)
    return SPACE_RE.sub(" ", text).strip()


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    doi = clean_text(value)
    doi = doi.removeprefix("https://doi.org/")
    doi = doi.removeprefix("http://doi.org/")
    doi = doi.removeprefix("doi:")
    doi = doi.strip().lower()
    return doi or None


def compact_authors(authors: Iterable[str] | None, limit: int = 12) -> str:
    values = [clean_text(author) for author in authors or [] if clean_text(author)]
    if len(values) <= limit:
        return "; ".join(values)
    return "; ".join(values[:limit]) + f"; et al. ({len(values)} authors)"
