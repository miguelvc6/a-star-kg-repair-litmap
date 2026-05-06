from __future__ import annotations

from typing import Any

from litmap.text import normalize_doi, normalize_title


def paper_identity(record: dict[str, Any]) -> tuple[str, str]:
    doi = normalize_doi(record.get("doi"))
    if doi:
        return ("doi", doi)
    dblp_key = record.get("dblp_key")
    if dblp_key:
        return ("dblp", str(dblp_key))
    return ("title", normalize_title(record.get("title")))


def deduplicate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for record in records:
        identity = paper_identity(record)
        if not identity[1] or identity in seen:
            continue
        seen.add(identity)
        deduped.append(record)
    return deduped
