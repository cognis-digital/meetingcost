"""Command-line interface for MEETINGCOST."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from . import TOOL_NAME, TOOL_VERSION
from .core import (
    ICSParseError,
    MeetingReport,
    blended_hourly_rate,
    compute_costs,
    parse_ics,
)


def _read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _fmt_money(v: float) -> str:
    return f"${v:,.2f}"


def _render_table(report: MeetingReport) -> str:
    lines: List[str] = []
    lines.append(f"Blended hourly rate: {_fmt_money(report.hourly_rate)}")
    lines.append("")
    header = f"{'COST':>12}  {'PPL':>4}  {'HOURS':>6}  TITLE"
    lines.append(header)
    lines.append("-" * max(len(header), 40))
    for m in sorted(report.meetings, key=lambda x: x.cost, reverse=True):
        lines.append(
            f"{_fmt_money(m.cost):>12}  {m.attendees:>4}  "
            f"{m.duration_hours:>6.2f}  {m.summary}"
        )
    lines.append("-" * max(len(header), 40))
    lines.append(f"Meetings:          {report.meeting_count}")
    lines.append(f"Total hours:       {report.total_hours:.2f}")
    lines.append(f"Total person-hours:{report.total_person_hours:>8.2f}")
    lines.append(f"TOTAL COST:        {_fmt_money(report.total_cost)}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Compute the dollar cost of meetings from a calendar (.ics).",
    )
    parser.add_argument(
        "--version", action="version", version=f"{TOOL_NAME} {TOOL_VERSION}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_cost = sub.add_parser(
        "cost", help="Compute meeting costs from an .ics file (use - for stdin)."
    )
    p_cost.add_argument("path", help="Path to .ics file, or - to read stdin.")
    p_cost.add_argument(
        "--salary",
        type=float,
        default=100_000.0,
        help="Average annual salary per attendee (default: 100000).",
    )
    p_cost.add_argument(
        "--overhead",
        type=float,
        default=1.4,
        help="Fully-loaded overhead multiplier (default: 1.4).",
    )
    p_cost.add_argument(
        "--hourly-rate",
        type=float,
        default=None,
        help="Override blended hourly rate directly (bypasses salary/overhead).",
    )
    p_cost.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table).",
    )
    return parser


def _validate_numeric_args(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> None:
    """Validate numeric CLI arguments and exit with a helpful message on failure."""
    if args.command != "cost":
        return
    if hasattr(args, "salary") and args.salary < 0:
        parser.error("--salary must be non-negative")
    if hasattr(args, "overhead") and args.overhead <= 0:
        parser.error("--overhead must be a positive number (e.g. 1.4)")
    hr = getattr(args, "hourly_rate", None)
    if hr is not None and hr < 0:
        parser.error("--hourly-rate must be non-negative")


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "cost":
        _validate_numeric_args(args, parser)

        if args.path != "-" and not os.path.exists(args.path):
            print(f"error: file not found: {args.path}", file=sys.stderr)
            return 2

        try:
            text = _read_input(args.path)
        except OSError as exc:
            print(f"error: cannot read {args.path}: {exc}", file=sys.stderr)
            return 2

        if not text.strip():
            print("error: input is empty — expected .ics data", file=sys.stderr)
            return 1

        try:
            rate = (
                args.hourly_rate
                if args.hourly_rate is not None
                else blended_hourly_rate(args.salary, args.overhead)
            )
            meetings = parse_ics(text)
            report = compute_costs(meetings, rate)
        except ICSParseError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        if args.format == "json":
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(_render_table(report))
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
