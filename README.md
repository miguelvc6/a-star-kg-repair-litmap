# A* KG Repair Literature Map

CLI pipeline for building a curated literature map of recent A* venue papers relevant to verified neuro-symbolic knowledge graph repair.

## What This Pipeline Does

The pipeline starts from A* conference and journal venues configured in `config.toml` and builds a focused reading list for research around knowledge graph repair, validation, constraints, neuro-symbolic methods, graph ML, LLM-assisted KG editing, data quality, and evaluation benchmarks.

It is designed to turn broad venue proceedings into a ranked literature map:

1. **Harvest DBLP records** from configured venues and years, including split-volume overrides where DBLP uses multiple pages for a venue year.
2. **Normalize and deduplicate papers** using DOI, DBLP key, or normalized title as stable identities.
3. **Enrich metadata** with abstracts, citation counts, fields of study, OpenAlex concepts, and external IDs from Semantic Scholar and OpenAlex.
4. **Score relevance** against configurable keyword axes such as KG/RDF/Wikidata, repair and constraints, neuro-symbolic reasoning, graph ML, LLM agents, data quality, and benchmarks.
5. **Assign priorities and categories** so the output separates likely must-read papers from weaker matches.
6. **Export researcher-friendly artifacts** for inspection, citation management, and reading.

The scoring is intentionally transparent: each paper keeps its matched axes, matched terms, negative keyword penalty, total score, priority, primary category, and reason for inclusion. That makes the final shortlist auditable rather than a black-box ranking.

## End Result

After `uv run litmap run-all`, the project produces a literature map under `data/`:

- a raw DBLP corpus of recent configured A* venue papers,
- an enriched JSONL dataset with metadata from DBLP, Semantic Scholar when enabled, and OpenAlex,
- a scored dataset with relevance signals for every harvested paper,
- a final CSV shortlist of non-rejected papers,
- a BibTeX file for citation managers,
- and a Markdown reading list grouped by research category.

The main artifact to read first is `data/final/reading_list.md`. For spreadsheet filtering and manual review, use `data/final/relevant_papers.csv`. For citation workflows, use `data/final/relevant_papers.bib`.

## Usage

Fill `.env` from `.env.example` as needed. Semantic Scholar is skipped unless `SEMANTIC_SCHOLAR_API_KEY` is set; the pipeline uses OpenAlex as the fallback enrichment source.

```bash
uv run litmap harvest-dblp
uv run litmap enrich
uv run litmap score
uv run litmap export
```

Or run the full pipeline:

```bash
uv run litmap run-all
```

For a small smoke run:

```bash
uv run litmap run-all --limit 10
```

Outputs are written under `data/`:

- `data/raw/dblp_core_a_star_2023_2026.jsonl`
- `data/enriched/papers_enriched.jsonl`
- `data/scored/papers_scored.jsonl`
- `data/scored/papers_scored.csv`
- `data/final/relevant_papers.csv`
- `data/final/relevant_papers.bib`
- `data/final/reading_list.md`
- `data/final/core_relevant_papers.csv`
- `data/final/core_relevant_papers.bib`
- `data/final/core_reading_list.md`

The core artifacts contain the top 200 non-rejected papers by `total_score`, with citation count, year, and title used as deterministic tie-breakers. Change `scoring.core_limit` in `config.toml` to make that core list shorter or longer.

Command logs are written under `logs/` with timestamped filenames such as `20260506_153000_run-all.log`.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
