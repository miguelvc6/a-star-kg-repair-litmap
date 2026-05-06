from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import quote

import requests

from litmap.config import Secrets
from litmap.text import normalize_doi


S2_FIELDS = ",".join(
    [
        "paperId",
        "title",
        "abstract",
        "year",
        "venue",
        "publicationDate",
        "citationCount",
        "influentialCitationCount",
        "fieldsOfStudy",
        "tldr",
        "externalIds",
        "url",
    ]
)
logger = logging.getLogger(__name__)


def enrich_records(
    records: list[dict[str, Any]],
    config: dict[str, Any],
    secrets: Secrets,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    sleep_s2 = float(config.get("rate_limits", {}).get("semantic_scholar_sleep_seconds", 1.0))
    sleep_oa = float(config.get("rate_limits", {}).get("openalex_sleep_seconds", 0.2))
    timeout = float(config.get("rate_limits", {}).get("request_timeout_seconds", 30))
    session = requests.Session()
    enriched: list[dict[str, Any]] = []

    for index, record in enumerate(records[:limit] if limit else records, start=1):
        merged = dict(record)
        s2 = fetch_semantic_scholar(session, record, secrets, timeout=timeout)
        if s2:
            merged.update(_semantic_scholar_fields(s2))
        time.sleep(sleep_s2)

        oa = fetch_openalex(session, record, secrets, timeout=timeout)
        if oa:
            merged.update(_openalex_fields(oa, merged))
        time.sleep(sleep_oa)

        merged["metadata_sources"] = [source for source in ["dblp", "semantic_scholar" if s2 else None, "openalex" if oa else None] if source]
        enriched.append(merged)
        logger.info("[enrich] %s/%s %s", index, len(records[:limit] if limit else records), record.get("title", "")[:80])
    return enriched


def fetch_semantic_scholar(
    session: requests.Session,
    record: dict[str, Any],
    secrets: Secrets,
    *,
    timeout: float,
) -> dict[str, Any] | None:
    headers = {"x-api-key": secrets.semantic_scholar_api_key} if secrets.semantic_scholar_api_key else {}
    doi = normalize_doi(record.get("doi"))
    try:
        if doi:
            url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{quote(doi, safe='')}"
            response = session.get(url, params={"fields": S2_FIELDS}, headers=headers, timeout=timeout)
            if response.status_code == 200:
                return response.json()
            if response.status_code not in {404, 429}:
                logger.warning("[enrich] Semantic Scholar DOI lookup HTTP %s: %s", response.status_code, doi)

        title = record.get("title")
        if not title:
            return None
        response = session.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={"query": title, "limit": 1, "fields": S2_FIELDS},
            headers=headers,
            timeout=timeout,
        )
        if response.status_code == 200:
            data = response.json().get("data", [])
            return data[0] if data else None
        logger.warning("[enrich] Semantic Scholar title lookup HTTP %s: %s", response.status_code, title[:80])
    except requests.RequestException as exc:
        logger.warning("[enrich] Semantic Scholar failed: %s", exc)
    return None


def fetch_openalex(
    session: requests.Session,
    record: dict[str, Any],
    secrets: Secrets,
    *,
    timeout: float,
) -> dict[str, Any] | None:
    params: dict[str, Any] = {}
    headers: dict[str, str] = {}
    if secrets.openalex_mailto:
        params["mailto"] = secrets.openalex_mailto
    if secrets.openalex_api_key:
        headers["Authorization"] = f"Bearer {secrets.openalex_api_key}"

    doi = normalize_doi(record.get("doi"))
    try:
        if doi:
            response = session.get(f"https://api.openalex.org/works/doi:{doi}", params=params, headers=headers, timeout=timeout)
            if response.status_code == 200:
                return response.json()
            if response.status_code not in {404, 429}:
                logger.warning("[enrich] OpenAlex DOI lookup HTTP %s: %s", response.status_code, doi)

        title = record.get("title")
        if not title:
            return None
        search_params = dict(params)
        search_params.update({"search": title, "per-page": 1})
        response = session.get("https://api.openalex.org/works", params=search_params, headers=headers, timeout=timeout)
        if response.status_code == 200:
            results = response.json().get("results", [])
            return results[0] if results else None
        logger.warning("[enrich] OpenAlex title lookup HTTP %s: %s", response.status_code, title[:80])
    except requests.RequestException as exc:
        logger.warning("[enrich] OpenAlex failed: %s", exc)
    return None


def reconstruct_openalex_abstract(index: dict[str, list[int]] | None) -> str | None:
    if not index:
        return None
    positions: dict[int, str] = {}
    for word, offsets in index.items():
        for offset in offsets:
            positions[int(offset)] = word
    return " ".join(positions[position] for position in sorted(positions))


def _semantic_scholar_fields(data: dict[str, Any]) -> dict[str, Any]:
    tldr = data.get("tldr") or {}
    external_ids = data.get("externalIds") or {}
    return {
        "semantic_scholar_id": data.get("paperId"),
        "semantic_scholar_url": data.get("url"),
        "abstract": data.get("abstract"),
        "abstract_source": "semantic_scholar" if data.get("abstract") else None,
        "tldr": tldr.get("text") if isinstance(tldr, dict) else None,
        "fields_of_study": data.get("fieldsOfStudy") or [],
        "citation_count": data.get("citationCount"),
        "citation_count_source": "semantic_scholar" if data.get("citationCount") is not None else None,
        "influential_citation_count": data.get("influentialCitationCount"),
        "semantic_scholar_external_ids": external_ids,
    }


def _openalex_fields(data: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    abstract = reconstruct_openalex_abstract(data.get("abstract_inverted_index"))
    concepts = [concept.get("display_name") for concept in data.get("concepts", []) if concept.get("display_name")]
    fields: dict[str, Any] = {
        "openalex_id": data.get("id"),
        "openalex_url": data.get("id"),
        "openalex_concepts": concepts,
        "openalex_cited_by_count": data.get("cited_by_count"),
        "openalex_publication_date": data.get("publication_date"),
        "openalex_open_access_url": (data.get("open_access") or {}).get("oa_url"),
    }
    if not current.get("abstract") and abstract:
        fields["abstract"] = abstract
        fields["abstract_source"] = "openalex"
    if current.get("citation_count") is None and data.get("cited_by_count") is not None:
        fields["citation_count"] = data.get("cited_by_count")
        fields["citation_count_source"] = "openalex"
    return fields
