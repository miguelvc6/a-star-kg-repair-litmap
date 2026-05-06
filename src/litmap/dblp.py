from __future__ import annotations

import html
import time
import xml.etree.ElementTree as ET
from typing import Any

import requests

from litmap.dedupe import deduplicate
from litmap.text import clean_text, normalize_doi


PUBLICATION_TAGS = {"article", "inproceedings", "proceedings"}


def source_url_for(config: dict[str, Any], venue: str, year: int) -> str | None:
    overrides = config.get("venues", {}).get("dblp_overrides", {})
    venue_overrides = overrides.get(venue, {})
    if str(year) in venue_overrides:
        return venue_overrides[str(year)]
    if year in venue_overrides:
        return venue_overrides[year]

    templates = config.get("venues", {}).get("dblp_sources", {})
    template = templates.get(venue)
    if not template:
        return None
    return str(template).format(year=year)


def parse_dblp_xml(xml_text: str, venue: str, source_url: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    records: list[dict[str, Any]] = []
    for element in root:
        tag = element.tag.rsplit("}", 1)[-1]
        if tag not in PUBLICATION_TAGS:
            continue
        if tag == "proceedings":
            continue
        title = _child_text(element, "title")
        if not title:
            continue
        year_text = _child_text(element, "year")
        doi = _first_ee_doi(element)
        records.append(
            {
                "dblp_key": element.attrib.get("key"),
                "title": title,
                "authors": [_element_text(child) for child in element if _local_name(child.tag) == "author"],
                "year": int(year_text) if year_text and year_text.isdigit() else None,
                "venue": venue,
                "doi": doi,
                "url": _child_text(element, "ee") or _child_text(element, "url"),
                "source": source_url,
            }
        )
    return records


def harvest_dblp(config: dict[str, Any], *, limit: int | None = None) -> list[dict[str, Any]]:
    years = _configured_years(config)
    venues = config.get("venues", {}).get("core", [])
    sleep_seconds = float(config.get("rate_limits", {}).get("dblp_sleep_seconds", 0.2))
    timeout = float(config.get("rate_limits", {}).get("request_timeout_seconds", 30))

    records: list[dict[str, Any]] = []
    session = requests.Session()
    for venue in venues:
        for year in years:
            url = source_url_for(config, venue, year)
            if not url:
                print(f"[harvest] no DBLP URL configured for {venue} {year}; skipping")
                continue
            try:
                response = session.get(url, timeout=timeout)
            except requests.RequestException as exc:
                print(f"[harvest] {venue} {year} failed: {exc}")
                continue
            if response.status_code == 404:
                print(f"[harvest] {venue} {year} not available on DBLP yet; skipping")
                continue
            if response.status_code >= 400:
                print(f"[harvest] {venue} {year} HTTP {response.status_code}; skipping")
                continue
            try:
                parsed = parse_dblp_xml(response.text, venue, url)
            except ET.ParseError as exc:
                print(f"[harvest] {venue} {year} XML parse failed: {exc}")
                continue
            records.extend(parsed)
            print(f"[harvest] {venue} {year}: {len(parsed)} records")
            if limit and len(records) >= limit:
                return deduplicate(records[:limit])
            time.sleep(sleep_seconds)
    return deduplicate(records)


def _configured_years(config: dict[str, Any]) -> list[int]:
    project = config.get("project", {})
    explicit = project.get("years")
    if explicit:
        return [int(year) for year in explicit]
    start = int(project.get("start_year", 2023))
    end = int(project.get("end_year", 2026))
    return list(range(start, end + 1))


def _child_text(element: ET.Element, child_name: str) -> str | None:
    for child in element:
        if _local_name(child.tag) == child_name:
            text = _element_text(child)
            return text or None
    return None


def _element_text(element: ET.Element) -> str:
    return clean_text(html.unescape("".join(element.itertext())))


def _first_ee_doi(element: ET.Element) -> str | None:
    for child in element:
        if _local_name(child.tag) != "ee":
            continue
        text = _element_text(child)
        doi = normalize_doi(text)
        if doi and "/" in doi:
            return doi
    return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
