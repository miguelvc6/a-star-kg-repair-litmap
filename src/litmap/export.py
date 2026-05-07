from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from litmap.io import ensure_parent
from litmap.text import compact_authors, normalize_title


CSV_COLUMNS = [
    "priority",
    "total_score",
    "primary_category",
    "year",
    "venue",
    "title",
    "authors",
    "abstract",
    "url",
    "doi",
    "citation_count",
    "kg_score",
    "repair_score",
    "neurosymbolic_score",
    "graph_ml_score",
    "llm_agent_score",
    "data_quality_score",
    "benchmark_score",
    "negative_penalty",
    "reason_for_inclusion",
    "matched_terms",
    "dblp_key",
    "semantic_scholar_id",
    "openalex_id",
]


def write_csv(path: Path, records: list[dict[str, Any]]) -> int:
    ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            row = dict(record)
            row["authors"] = compact_authors(record.get("authors"))
            row["matched_terms"] = json.dumps(record.get("matched_terms", {}), ensure_ascii=False, sort_keys=True)
            writer.writerow(row)
    return len(records)


def write_bibtex(path: Path, records: list[dict[str, Any]]) -> int:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(to_bibtex(record))
            f.write("\n\n")
    return len(records)


def write_markdown_reading_list(path: Path, records: list[dict[str, Any]], config: dict[str, Any]) -> int:
    ensure_parent(path)
    categories = list(config.get("categories", {}).keys()) + ["Uncategorized"]
    with path.open("w", encoding="utf-8") as f:
        f.write("# A* KG Repair Literature Map\n\n")
        for category in categories:
            grouped = [record for record in records if record.get("primary_category") == category]
            if not grouped:
                continue
            f.write(f"## {category}\n\n")
            for record in sorted(grouped, key=lambda r: (-int(r.get("total_score", 0)), r.get("year") or 0, r.get("title") or "")):
                authors = compact_authors(record.get("authors"), limit=4)
                url = record.get("url") or record.get("semantic_scholar_url") or record.get("openalex_url") or ""
                citation = f", citations: {record.get('citation_count')}" if record.get("citation_count") is not None else ""
                f.write(
                    f"- **{record.get('priority')}** [{record.get('title', 'Untitled')}]({url}) "
                    f"({record.get('venue')}, {record.get('year')}{citation})\n"
                )
                if authors:
                    f.write(f"  Authors: {authors}\n")
                f.write(f"  {record.get('reason_for_inclusion', '')}\n\n")
    return len(records)


def top_scored_records(records: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    ranked = sorted(
        records,
        key=lambda r: (
            -int(r.get("total_score", 0)),
            -int(r.get("citation_count") or 0),
            -(int(r.get("year")) if r.get("year") else 0),
            r.get("title") or "",
        ),
    )
    return ranked[:limit]


def export_outputs(records: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, int]:
    paths = config.get("paths", {})
    scoring = config.get("scoring", {})
    shortlist = [record for record in records if record.get("priority") != "Reject"]
    core_limit = int(scoring.get("core_limit", 200))
    core_shortlist = top_scored_records(shortlist, core_limit)
    counts = {
        "full_csv": write_csv(Path(paths["full_scored_csv"]), records),
        "shortlist_csv": write_csv(Path(paths["shortlist_csv"]), shortlist),
        "bibtex": write_bibtex(Path(paths["bibtex"]), shortlist),
        "reading_list": write_markdown_reading_list(Path(paths["reading_list_md"]), shortlist, config),
        "core_shortlist_csv": write_csv(Path(paths["core_shortlist_csv"]), core_shortlist),
        "core_bibtex": write_bibtex(Path(paths["core_bibtex"]), core_shortlist),
        "core_reading_list": write_markdown_reading_list(Path(paths["core_reading_list_md"]), core_shortlist, config),
    }
    return counts


def to_bibtex(record: dict[str, Any]) -> str:
    key = bibtex_key(record)
    authors = " and ".join(record.get("authors") or [])
    fields = {
        "title": record.get("title"),
        "author": authors or None,
        "year": record.get("year"),
        "booktitle": record.get("venue"),
        "doi": record.get("doi"),
        "url": record.get("url") or record.get("semantic_scholar_url") or record.get("openalex_url"),
    }
    lines = [f"@inproceedings{{{key},"]
    for name, value in fields.items():
        if value is None or value == "":
            continue
        lines.append(f"  {name} = {{{escape_bibtex(str(value))}}},")
    lines[-1] = lines[-1].rstrip(",")
    lines.append("}")
    return "\n".join(lines)


def bibtex_key(record: dict[str, Any]) -> str:
    dblp_key = record.get("dblp_key")
    if dblp_key:
        return re.sub(r"[^A-Za-z0-9_:-]", "_", str(dblp_key).replace("/", ":"))
    title = normalize_title(record.get("title")) or "untitled"
    first = (record.get("authors") or ["paper"])[0].split()[-1]
    year = record.get("year") or "nd"
    slug = "".join(part.capitalize() for part in title.split()[:4])
    return re.sub(r"[^A-Za-z0-9_:-]", "_", f"{first}{year}{slug}")


def escape_bibtex(value: str) -> str:
    return (
        value.replace("\\", "\\textbackslash{}")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("&", "\\&")
    )
