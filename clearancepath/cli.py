"""Command-line interface for CLEARANCEPATH.

Subcommands:
  assess   Assess a roster JSON file (or a single person) for clearance hygiene.
  due      List only items that need attention (WARN/CRITICAL).

Global:
  --version            print tool version
  --format {table,json}

Exit codes:
  0  clean (no WARN/CRITICAL findings)
  1  CRITICAL findings present
  2  WARN findings present (but no CRITICAL)
  3  usage / input error
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from typing import Any, Optional

from clearancepath import TOOL_NAME, TOOL_VERSION
from clearancepath.core import (
    Person,
    Severity,
    assess_roster,
    parse_date,
)

_USAGE_ERR = 3


def _load_roster(path: str) -> list[Person]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        raise SystemExit(f"{TOOL_NAME}: file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{TOOL_NAME}: invalid JSON in {path}: {exc}")

    if isinstance(data, dict) and "people" in data:
        records = data["people"]
    elif isinstance(data, dict):
        records = [data]               # single person object
    elif isinstance(data, list):
        records = data
    else:
        raise SystemExit(f"{TOOL_NAME}: unexpected JSON shape in {path}")

    try:
        return [Person.from_dict(r) for r in records]
    except ValueError as exc:
        raise SystemExit(f"{TOOL_NAME}: {exc}")


def _exit_code(reports) -> int:
    status = max((r.status for r in reports), default=Severity.OK)
    if status >= Severity.CRITICAL:
        return 1
    if status >= Severity.WARN:
        return 2
    return 0


def _render_table(reports, only_attention: bool) -> str:
    lines: list[str] = []
    for rep in reports:
        lines.append(f"=== {rep.name}  [{rep.eligibility}]  status={rep.status.label}")
        rows = [
            f
            for f in rep.findings
            if (not only_attention) or f.severity >= Severity.WARN
        ]
        if not rows:
            lines.append("    (no items needing attention)")
        for f in rows:
            tag = f.severity.label.ljust(9)
            cat = f.category.ljust(13)
            lines.append(f"    {tag}{cat}{f.message}")
        lines.append("")
    crit = sum(
        1 for r in reports for f in r.findings if f.severity >= Severity.CRITICAL
    )
    warn = sum(
        1 for r in reports for f in r.findings if f.severity == Severity.WARN
    )
    lines.append(
        f"-- {len(reports)} personnel | {crit} CRITICAL | {warn} WARN --"
    )
    return "\n".join(lines)


def _render_json(reports, only_attention: bool) -> str:
    out = []
    for rep in reports:
        d = rep.to_dict()
        if only_attention:
            d["findings"] = [
                f for f in d["findings"] if f["severity"] in ("WARN", "CRITICAL")
            ]
        out.append(d)
    payload: dict[str, Any] = {
        "tool": TOOL_NAME,
        "version": TOOL_VERSION,
        "generated": _dt.date.today().isoformat(),
        "personnel": out,
        "summary": {
            "count": len(reports),
            "critical": sum(
                1 for r in reports for f in r.findings
                if f.severity >= Severity.CRITICAL
            ),
            "warn": sum(
                1 for r in reports for f in r.findings
                if f.severity == Severity.WARN
            ),
        },
    }
    return json.dumps(payload, indent=2)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Personnel clearance hygiene tracker "
        "(SF-86 PR cadence, SEAD-3/4, training currency).",
    )
    p.add_argument("--version", action="version",
                   version=f"{TOOL_NAME} {TOOL_VERSION}")
    p.add_argument("--format", choices=("table", "json"), default="table")
    p.add_argument("--as-of", metavar="YYYY-MM-DD",
                   help="evaluate as of this date (default: today)")

    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("assess", help="full hygiene assessment of a roster")
    a.add_argument("roster", help="path to roster JSON")

    d = sub.add_parser("due", help="only items needing attention (WARN/CRITICAL)")
    d.add_argument("roster", help="path to roster JSON")

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        as_of = parse_date(args.as_of) if args.as_of else _dt.date.today()
    except ValueError as exc:
        print(f"{TOOL_NAME}: {exc}", file=sys.stderr)
        return _USAGE_ERR

    people = _load_roster(args.roster)
    reports = assess_roster(people, as_of=as_of)
    only_attention = args.command == "due"

    if args.format == "json":
        print(_render_json(reports, only_attention))
    else:
        print(_render_table(reports, only_attention))

    return _exit_code(reports)


if __name__ == "__main__":
    sys.exit(main())
