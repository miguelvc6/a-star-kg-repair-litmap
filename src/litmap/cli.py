from __future__ import annotations

import argparse
from pathlib import Path

from litmap.config import load_project_config, load_secrets, resolve_project_path
from litmap.dblp import harvest_dblp
from litmap.enrich import enrich_records
from litmap.export import export_outputs
from litmap.io import read_jsonl, write_jsonl
from litmap.scoring import score_records


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_project_config(args.config)
    config = _resolve_paths(config)

    if args.command == "harvest-dblp":
        return command_harvest(config, args)
    if args.command == "enrich":
        return command_enrich(config, args)
    if args.command == "score":
        return command_score(config, args)
    if args.command == "export":
        return command_export(config, args)
    if args.command == "run-all":
        command_harvest(config, args)
        command_enrich(config, args)
        command_score(config, args)
        return command_export(config, args)
    parser.print_help()
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="litmap", description="Build a literature map for A* KG repair research.")
    parser.add_argument("--config", type=Path, default=None, help="Path to config.toml.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ["harvest-dblp", "enrich", "score", "export", "run-all"]:
        command = subparsers.add_parser(name)
        command.add_argument("--limit", type=int, default=None, help="Process at most N records for smoke tests.")
    return parser


def command_harvest(config: dict, args: argparse.Namespace) -> int:
    records = harvest_dblp(config, limit=args.limit)
    path = Path(config["paths"]["raw_dblp_jsonl"])
    count = write_jsonl(path, records)
    print(f"[harvest] wrote {count} records to {path}")
    return 0


def command_enrich(config: dict, args: argparse.Namespace) -> int:
    input_path = Path(config["paths"]["raw_dblp_jsonl"])
    output_path = Path(config["paths"]["enriched_jsonl"])
    records = read_jsonl(input_path)
    enriched = enrich_records(records, config, load_secrets(), limit=args.limit)
    count = write_jsonl(output_path, enriched)
    print(f"[enrich] wrote {count} records to {output_path}")
    return 0


def command_score(config: dict, args: argparse.Namespace) -> int:
    input_path = Path(config["paths"]["enriched_jsonl"])
    output_path = Path(config["paths"]["scored_jsonl"])
    records = read_jsonl(input_path)
    if args.limit:
        records = records[: args.limit]
    scored = score_records(records, config)
    count = write_jsonl(output_path, scored)
    print(f"[score] wrote {count} records to {output_path}")
    return 0


def command_export(config: dict, args: argparse.Namespace) -> int:
    input_path = Path(config["paths"]["scored_jsonl"])
    records = read_jsonl(input_path)
    if args.limit:
        records = records[: args.limit]
    counts = export_outputs(records, config)
    for name, count in counts.items():
        print(f"[export] {name}: {count} records")
    return 0


def _resolve_paths(config: dict) -> dict:
    resolved = dict(config)
    resolved["paths"] = {key: str(resolve_project_path(value)) for key, value in config.get("paths", {}).items()}
    return resolved


if __name__ == "__main__":
    raise SystemExit(main())
