# A* KG Repair Literature Map

CLI pipeline for building a curated literature map of recent A* venue papers relevant to verified neuro-symbolic knowledge graph repair.

## Usage

Fill `.env` from `.env.example` as needed. API keys are optional where the upstream service allows unauthenticated requests.

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
- `data/scored/papers_scored.csv`
- `data/final/relevant_papers.csv`
- `data/final/relevant_papers.bib`
- `data/final/reading_list.md`

Command logs are written under `logs/` with timestamped filenames such as `20260506_153000_run-all.log`.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
