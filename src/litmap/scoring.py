from __future__ import annotations

from typing import Any

from litmap.text import clean_text


AXIS_KEYS = [
    "kg",
    "repair",
    "neurosymbolic",
    "graph_ml",
    "llm_agent",
    "data_quality",
    "benchmark",
]


def score_records(records: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    return [score_record(record, config) for record in records]


def score_record(record: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    scoring = config.get("scoring", {})
    weights = scoring.get("weights", {})
    axes = scoring.get("axes", {})
    haystack = _paper_text(record)

    scored = dict(record)
    matched_axes: list[str] = []
    matched_terms: dict[str, list[str]] = {}
    positive_total = 0

    for axis in AXIS_KEYS:
        axis_config = axes.get(axis, {})
        terms = [term for term in axis_config.get("keywords", []) if _contains_term(haystack, term)]
        weight = int(weights.get(axis, axis_config.get("weight", 0)))
        score = weight if terms else 0
        scored[f"{axis}_score"] = score
        if terms:
            positive_total += score
            matched_axes.append(axis)
            matched_terms[axis] = terms

    negative_terms = [term for term in scoring.get("negative_keywords", []) if _contains_term(haystack, term)]
    max_negative_penalty = int(scoring.get("max_negative_penalty", 3))
    negative_penalty = min(len(negative_terms), max_negative_penalty)
    total_score = max(0, positive_total - negative_penalty)

    scored["matched_axes"] = matched_axes
    scored["matched_terms"] = matched_terms
    scored["negative_terms"] = negative_terms
    scored["negative_penalty"] = negative_penalty
    scored["total_score"] = total_score
    scored["priority"] = assign_priority(total_score, config)
    scored["reason_for_inclusion"] = reason_for_inclusion(matched_axes, axes, negative_terms)
    scored["primary_category"] = primary_category(scored, config)
    return scored


def assign_priority(total_score: int, config: dict[str, Any]) -> str:
    scoring = config.get("scoring", {})
    min_score = int(scoring.get("min_relevance_score", 5))
    likely_score = int(scoring.get("likely_useful_score", 8))
    must_score = int(scoring.get("must_read_score", 11))
    if total_score >= must_score:
        return "A"
    if total_score >= likely_score:
        return "B"
    if total_score >= min_score:
        return "C"
    return "Reject"


def reason_for_inclusion(matched_axes: list[str], axes: dict[str, Any], negative_terms: list[str]) -> str:
    if not matched_axes:
        return "No configured relevance axes matched."
    labels = [axes.get(axis, {}).get("label", axis) for axis in matched_axes]
    reason = "Matches: " + "; ".join(labels) + "."
    if negative_terms:
        reason += " Low-priority terms also matched: " + "; ".join(negative_terms) + "."
    return reason


def primary_category(record: dict[str, Any], config: dict[str, Any]) -> str:
    categories = config.get("categories", {})
    best_category = "Uncategorized"
    best_score = 0
    for category, axes in categories.items():
        category_score = sum(int(record.get(f"{axis}_score", 0)) for axis in axes)
        if category_score > best_score:
            best_category = category
            best_score = category_score
    return best_category


def _paper_text(record: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ["title", "abstract", "tldr", "venue"]:
        value = record.get(key)
        if value:
            parts.append(str(value))
    for key in ["fields_of_study", "openalex_concepts"]:
        value = record.get(key) or []
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
    return clean_text(" ".join(parts)).casefold()


def _contains_term(haystack: str, term: str) -> bool:
    return clean_text(term).casefold() in haystack
