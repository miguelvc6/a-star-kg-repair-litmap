from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from litmap.config import load_project_config
from litmap.dblp import parse_dblp_xml
from litmap.dedupe import deduplicate
from litmap.enrich import reconstruct_openalex_abstract
from litmap.export import escape_bibtex, to_bibtex
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

    def test_reconstruct_openalex_abstract(self) -> None:
        index = {"Knowledge": [0], "graphs": [1], "repair": [2], "matter": [3]}

        self.assertEqual(reconstruct_openalex_abstract(index), "Knowledge graphs repair matter")

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

    def test_jsonl_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            records = [{"title": "A"}, {"title": "B"}]

            count = write_jsonl(path, records)

            self.assertEqual(count, 2)
            self.assertEqual(read_jsonl(path), records)


if __name__ == "__main__":
    unittest.main()
