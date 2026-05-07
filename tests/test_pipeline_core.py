from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from litmap.config import Secrets, load_project_config, load_secrets
from litmap.dblp import parse_dblp_html, parse_dblp_xml, source_url_for
from litmap.dedupe import deduplicate
from litmap.enrich import enrich_records, reconstruct_openalex_abstract
from litmap.export import escape_bibtex, to_bibtex, top_scored_records
from litmap.io import read_jsonl, write_jsonl
from litmap.scoring import assign_priority, score_record


DBLP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<dblp>
  <inproceedings key="conf/test/Smith25">
    <author>Jane Smith</author>
    <author>Max Müller</author>
    <title>Constraint-Aware Knowledge Graph Repair with Symbolic Validation.</title>
    <year>2025</year>
    <ee>https://doi.org/10.1145/example</ee>
    <url>db/conf/test/test2025.html#Smith25</url>
  </inproceedings>
  <proceedings key="conf/test/2025">
    <title>Proceedings of TestConf 2025</title>
    <year>2025</year>
  </proceedings>
</dblp>
"""

DBLP_HTML = """
<html>
  <body>
    <ul class="publ-list">
      <li class="entry inproceedings" id="conf/kr/BienvenuB23">
        <cite class="data tts-content">
          <span itemprop="author"><a><span itemprop="name">Meghyn Bienvenu</span></a></span>,
          <span itemprop="author"><a><span itemprop="name">Camille Bourgaux</span></a></span>:
          <span class="title" itemprop="name">Inconsistency Handling in Prioritized Databases with Universal Constraints.</span>
          <meta itemprop="datePublished" content="2023"/>
        </cite>
        <nav>
          <a href="https://doi.org/10.24963/kr.2023/10">electronic edition via DOI</a>
          <a href="https://dblp.org/rec/conf/kr/BienvenuB23">persistent URL</a>
        </nav>
      </li>
    </ul>
  </body>
</html>
"""


class PipelineCoreTests(unittest.TestCase):
    def test_load_project_config(self) -> None:
        config = load_project_config()
        self.assertEqual(config["project"]["name"], "a_star_literature_map")
        self.assertIn("raw_dblp_jsonl", config["paths"])
        self.assertIn("kg", config["scoring"]["weights"])

    def test_parse_dblp_xml_normalizes_records(self) -> None:
        records = parse_dblp_xml(DBLP_XML, "TEST", "https://dblp.example/test.xml")

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["dblp_key"], "conf/test/Smith25")
        self.assertEqual(records[0]["authors"], ["Jane Smith", "Max Müller"])
        self.assertEqual(records[0]["year"], 2025)
        self.assertEqual(records[0]["doi"], "10.1145/example")

    def test_parse_dblp_html_toc_normalizes_records(self) -> None:
        records = parse_dblp_html(DBLP_HTML, "KR", "https://dblp.org/db/conf/kr/kr2023.html", 2023)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["dblp_key"], "conf/kr/BienvenuB23")
        self.assertEqual(records[0]["authors"], ["Meghyn Bienvenu", "Camille Bourgaux"])
        self.assertEqual(records[0]["year"], 2023)
        self.assertEqual(records[0]["doi"], "10.24963/kr.2023/10")
        self.assertEqual(
            records[0]["title"],
            "Inconsistency Handling in Prioritized Databases with Universal Constraints.",
        )

    def test_dblp_source_url_supports_split_volume_overrides(self) -> None:
        config = {
            "venues": {
                "dblp_sources": {"KDD": "https://dblp.org/db/conf/kdd/kdd{year}.html"},
                "dblp_overrides": {
                    "KDD": {
                        2025: [
                            "https://dblp.org/db/conf/kdd/kdd2025-1.html",
                            "https://dblp.org/db/conf/kdd/kdd2025-2.html",
                        ]
                    }
                },
            }
        }

        self.assertEqual(
            source_url_for(config, "KDD", 2025),
            [
                "https://dblp.org/db/conf/kdd/kdd2025-1.html",
                "https://dblp.org/db/conf/kdd/kdd2025-2.html",
            ],
        )
        self.assertEqual(source_url_for(config, "KDD", 2024), ["https://dblp.org/db/conf/kdd/kdd2024.html"])

    def test_reconstruct_openalex_abstract(self) -> None:
        index = {"Knowledge": [0], "graphs": [1], "repair": [2], "matter": [3]}

        self.assertEqual(reconstruct_openalex_abstract(index), "Knowledge graphs repair matter")

    def test_enrich_disables_semantic_scholar_after_denial_status(self) -> None:
        records = [{"title": "First", "doi": "10.1/first"}, {"title": "Second", "doi": "10.1/second"}]
        secrets = Secrets(None, None, None, None, None, None, None)
        config = {
            "metadata_sources": {"semantic_scholar_allow_unauthenticated": True},
            "rate_limits": {"semantic_scholar_sleep_seconds": 0, "openalex_sleep_seconds": 0},
        }

        for status in [403, 429]:
            with self.subTest(status=status):
                with (
                    patch("litmap.enrich.fetch_semantic_scholar", return_value=(None, status)) as fetch_s2,
                    patch("litmap.enrich.fetch_openalex", return_value=None) as fetch_oa,
                    patch("litmap.enrich.time.sleep"),
                ):
                    enriched = enrich_records(records, config, secrets)

                self.assertEqual(len(enriched), 2)
                self.assertEqual(fetch_s2.call_count, 1)
                self.assertEqual(fetch_oa.call_count, 2)
                self.assertEqual([record["metadata_sources"] for record in enriched], [["dblp"], ["dblp"]])

    def test_enrich_skips_semantic_scholar_without_key_by_default(self) -> None:
        records = [{"title": "First", "doi": "10.1/first"}, {"title": "Second", "doi": "10.1/second"}]
        secrets = Secrets(None, None, None, None, None, None, None)
        config = {"rate_limits": {"semantic_scholar_sleep_seconds": 0, "openalex_sleep_seconds": 0}}

        with (
            patch("litmap.enrich.fetch_semantic_scholar") as fetch_s2,
            patch("litmap.enrich.fetch_openalex", return_value=None) as fetch_oa,
            patch("litmap.enrich.time.sleep"),
        ):
            enriched = enrich_records(records, config, secrets)

        fetch_s2.assert_not_called()
        self.assertEqual(fetch_oa.call_count, 2)
        self.assertEqual([record["metadata_sources"] for record in enriched], [["dblp"], ["dblp"]])

    def test_deduplicate_prefers_stable_identity(self) -> None:
        records = [
            {"doi": "https://doi.org/10.1/ABC", "title": "First"},
            {"doi": "10.1/abc", "title": "Duplicate"},
            {"dblp_key": "conf/x/1", "title": "Unique"},
            {"dblp_key": "conf/x/1", "title": "Duplicate key"},
            {"title": "A Knowledge Graph Paper!"},
            {"title": "a knowledge graph paper"},
        ]

        deduped = deduplicate(records)

        self.assertEqual(len(deduped), 3)
        self.assertEqual([record["title"] for record in deduped], ["First", "Unique", "A Knowledge Graph Paper!"])

    def test_score_record_and_priority(self) -> None:
        config = load_project_config()
        record = {
            "title": "Knowledge Graph Repair with Integrity Constraints",
            "abstract": "We build a benchmark for RDF validation and data cleaning.",
        }

        scored = score_record(record, config)

        self.assertEqual(scored["kg_score"], 3)
        self.assertEqual(scored["repair_score"], 3)
        self.assertEqual(scored["data_quality_score"], 2)
        self.assertEqual(scored["benchmark_score"], 2)
        self.assertEqual(scored["total_score"], 10)
        self.assertEqual(scored["priority"], "B")
        self.assertIn("KG / RDF", scored["reason_for_inclusion"])

    def test_assign_priority_thresholds(self) -> None:
        config = load_project_config()

        self.assertEqual(assign_priority(0, config), "Reject")
        self.assertEqual(assign_priority(5, config), "C")
        self.assertEqual(assign_priority(8, config), "B")
        self.assertEqual(assign_priority(11, config), "A")

    def test_top_scored_records_uses_score_then_citations(self) -> None:
        records = [
            {"title": "Lower", "total_score": 8, "citation_count": 100, "year": 2026},
            {"title": "Higher", "total_score": 11, "citation_count": 1, "year": 2024},
            {"title": "Tie winner", "total_score": 11, "citation_count": 3, "year": 2023},
        ]

        top = top_scored_records(records, 2)

        self.assertEqual([record["title"] for record in top], ["Tie winner", "Higher"])

    def test_bibtex_escaping(self) -> None:
        self.assertEqual(escape_bibtex("A & B {C}"), "A \\& B \\{C\\}")
        bibtex = to_bibtex(
            {
                "dblp_key": "conf/test/Smith25",
                "title": "A & B {C}",
                "authors": ["Jane Smith", "Max Mustermann"],
                "year": 2025,
                "venue": "TEST",
                "doi": "10.1145/example",
            }
        )

        self.assertIn("@inproceedings{conf:test:Smith25,", bibtex)
        self.assertIn("title = {A \\& B \\{C\\}}", bibtex)

    def test_config_can_be_loaded_from_custom_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text('[project]\nname = "custom"\n', encoding="utf-8")
            self.assertEqual(load_project_config(path)["project"]["name"], "custom")

    def test_load_secrets_reads_env_file_without_python_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text(
                'SEMANTIC_SCHOLAR_API_KEY="test-s2-key"\nOPENALEX_MAILTO=test@example.com\n',
                encoding="utf-8",
            )
            with patch.dict("os.environ", {}, clear=True):
                secrets = load_secrets(path)

        self.assertEqual(secrets.semantic_scholar_api_key, "test-s2-key")
        self.assertEqual(secrets.openalex_mailto, "test@example.com")

    def test_jsonl_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            records = [{"title": "A"}, {"title": "B"}]

            count = write_jsonl(path, records)

            self.assertEqual(count, 2)
            self.assertEqual(read_jsonl(path), records)


if __name__ == "__main__":
    unittest.main()
