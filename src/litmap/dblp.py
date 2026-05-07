from __future__ import annotations

import html
import logging
from html.parser import HTMLParser
import time
import xml.etree.ElementTree as ET
from typing import Any

import requests

from litmap.dedupe import deduplicate
from litmap.text import clean_text, normalize_doi


PUBLICATION_TAGS = {"article", "inproceedings", "proceedings"}
DEFAULT_USER_AGENT = "a-star-kg-repair-litmap/0.1 (academic metadata harvester; polite DBLP requests)"
logger = logging.getLogger(__name__)


def source_url_for(config: dict[str, Any], venue: str, year: int) -> list[str]:
    overrides = config.get("venues", {}).get("dblp_overrides", {})
    venue_overrides = overrides.get(venue, {})
    if str(year) in venue_overrides:
        return _source_urls(venue_overrides[str(year)])
    if year in venue_overrides:
        return _source_urls(venue_overrides[year])

    templates = config.get("venues", {}).get("dblp_sources", {})
    template = templates.get(venue)
    if not template:
        return []
    return [str(template).format(year=year)]


def parse_dblp_xml(xml_text: str, venue: str, source_url: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    records: list[dict[str, Any]] = []
    for element in root.iter():
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


def parse_dblp_html(html_text: str, venue: str, source_url: str, year: int | None = None) -> list[dict[str, Any]]:
    parser = _DblpTocHtmlParser()
    parser.feed(html_text)
    records: list[dict[str, Any]] = []
    for entry in parser.entries:
        title = clean_text(entry.get("title"))
        if not title:
            continue
        dblp_key = entry.get("dblp_key")
        doi_url = entry.get("doi_url")
        persistent_url = f"https://dblp.org/rec/{dblp_key}" if dblp_key else entry.get("persistent_url")
        records.append(
            {
                "dblp_key": dblp_key,
                "title": title,
                "authors": entry.get("authors", []),
                "year": entry.get("year") or year,
                "venue": venue,
                "doi": normalize_doi(doi_url),
                "url": doi_url or persistent_url,
                "source": source_url,
            }
        )
    return records


def harvest_dblp(config: dict[str, Any], *, limit: int | None = None) -> list[dict[str, Any]]:
    years = _configured_years(config)
    venues = config.get("venues", {}).get("core", [])
    sleep_seconds = float(config.get("rate_limits", {}).get("dblp_sleep_seconds", 2.0))
    timeout = float(config.get("rate_limits", {}).get("request_timeout_seconds", 30))
    retries = int(config.get("rate_limits", {}).get("dblp_retries", 3))
    backoff_seconds = float(config.get("rate_limits", {}).get("dblp_backoff_seconds", 5.0))
    headers = {
        "User-Agent": str(config.get("rate_limits", {}).get("user_agent", DEFAULT_USER_AGENT)),
        "Accept": "text/html, application/xml;q=0.9, text/xml;q=0.9, */*;q=0.1",
        "Connection": "close",
    }

    records: list[dict[str, Any]] = []
    for venue in venues:
        for year in years:
            urls = source_url_for(config, venue, year)
            if not urls:
                logger.warning("[harvest] no DBLP URL configured for %s %s; skipping", venue, year)
                continue
            parsed_for_year: list[dict[str, Any]] = []
            available = False
            for url in urls:
                response = _fetch_with_retries(
                    url,
                    headers=headers,
                    timeout=timeout,
                    retries=retries,
                    backoff_seconds=backoff_seconds,
                    label=f"{venue} {year}",
                )
                if response is None:
                    continue
                if response.status_code == 404:
                    continue
                available = True
                if response.status_code >= 400:
                    logger.warning("[harvest] %s %s HTTP %s; skipping %s", venue, year, response.status_code, url)
                    continue
                try:
                    parsed = parse_dblp_response(response.text, venue, url, year)
                except ET.ParseError as exc:
                    logger.warning("[harvest] %s %s parse failed: %s", venue, year, exc)
                    continue
                parsed_for_year.extend(record for record in parsed if record.get("year") in {None, year})
                time.sleep(sleep_seconds)
            if not available:
                logger.info("[harvest] %s %s not available on DBLP yet; skipping", venue, year)
                continue
            records.extend(parsed_for_year)
            logger.info("[harvest] %s %s: %s records", venue, year, len(parsed_for_year))
            if limit and len(records) >= limit:
                return deduplicate(records[:limit])
    return deduplicate(records)


def _source_urls(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def parse_dblp_response(text: str, venue: str, source_url: str, year: int | None = None) -> list[dict[str, Any]]:
    stripped = text.lstrip()
    if stripped.startswith("<?xml") or stripped.startswith("<dblp"):
        return parse_dblp_xml(text, venue, source_url)
    return parse_dblp_html(text, venue, source_url, year)


def _fetch_with_retries(
    url: str,
    *,
    headers: dict[str, str],
    timeout: float,
    retries: int,
    backoff_seconds: float,
    label: str,
) -> requests.Response | None:
    for attempt in range(retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
        except requests.RequestException as exc:
            if attempt >= retries:
                logger.warning("[harvest] %s failed after %s attempts: %s", label, attempt + 1, exc)
                return None
            wait_seconds = backoff_seconds * (2**attempt)
            logger.warning("[harvest] %s request failed: %s; retrying in %.1fs", label, exc, wait_seconds)
            time.sleep(wait_seconds)
            continue

        if response.status_code in {429, 500, 502, 503, 504} and attempt < retries:
            retry_after = response.headers.get("Retry-After")
            wait_seconds = float(retry_after) if retry_after and retry_after.isdigit() else backoff_seconds * (2**attempt)
            logger.warning("[harvest] %s HTTP %s; retrying in %.1fs", label, response.status_code, wait_seconds)
            time.sleep(wait_seconds)
            continue
        return response
    return None


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


class _DblpTocHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.entries: list[dict[str, Any]] = []
        self._entry: dict[str, Any] | None = None
        self._li_depth = 0
        self._author_depth = 0
        self._author_name_depth = 0
        self._title_depth = 0
        self._author_buffer: list[str] = []
        self._title_buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "li" and _class_contains(attr.get("class"), "entry"):
            self._entry = {"dblp_key": attr.get("id"), "authors": []}
            self._li_depth = 1
            return
        if self._entry is None:
            return
        if tag == "li":
            self._li_depth += 1
        if tag == "span" and attr.get("itemprop") == "author":
            self._author_depth += 1
        if tag == "span" and self._author_depth and attr.get("itemprop") == "name":
            self._author_name_depth += 1
            self._author_buffer = []
        if tag == "span" and _class_contains(attr.get("class"), "title"):
            self._title_depth += 1
            self._title_buffer = []
        if tag == "meta" and attr.get("itemprop") == "datePublished" and attr.get("content"):
            year = str(attr["content"])[:4]
            if year.isdigit():
                self._entry["year"] = int(year)
        if tag == "a" and attr.get("href"):
            href = str(attr["href"])
            if "doi.org/" in href and not self._entry.get("doi_url"):
                self._entry["doi_url"] = href
            if "dblp.org/rec/" in href and not self._entry.get("persistent_url"):
                self._entry["persistent_url"] = href
                if not self._entry.get("dblp_key"):
                    self._entry["dblp_key"] = href.split("/rec/", 1)[1].removesuffix(".html")

    def handle_endtag(self, tag: str) -> None:
        if self._entry is None:
            return
        if tag == "span" and self._author_name_depth:
            author = clean_text(" ".join(self._author_buffer))
            if author:
                self._entry.setdefault("authors", []).append(author)
            self._author_name_depth -= 1
            self._author_buffer = []
        elif tag == "span" and self._title_depth:
            self._entry["title"] = clean_text(" ".join(self._title_buffer))
            self._title_depth -= 1
            self._title_buffer = []
        elif tag == "span" and self._author_depth:
            self._author_depth -= 1
        elif tag == "li":
            self._li_depth -= 1
            if self._li_depth <= 0:
                if self._entry.get("dblp_key") and self._entry.get("title"):
                    self.entries.append(self._entry)
                self._entry = None
                self._li_depth = 0

    def handle_data(self, data: str) -> None:
        if self._entry is None:
            return
        if self._author_name_depth:
            self._author_buffer.append(data)
        if self._title_depth:
            self._title_buffer.append(data)


def _class_contains(value: str | None, class_name: str) -> bool:
    return class_name in (value or "").split()
