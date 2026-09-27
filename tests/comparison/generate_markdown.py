#!/usr/bin/env python3
"""Refresh the generated tables in docs/comparison.md from comparison results.

The page itself is hand-written. Only the regions between the
``<!-- comparison-facts:start/end -->`` and
``<!-- comparison-results:start/end -->`` markers are replaced.
"""

import argparse
import json
import re
import sys
from pathlib import Path

FRAMEWORK_ORDER = ["Django Ninja AIO", "Django Ninja", "ADRF", "FastAPI"]
DISPLAY_NAMES = {"Django Ninja AIO": "django-ninja-aio-crud"}


def _ordered_frameworks(results: dict) -> list[str]:
    known = [fw for fw in FRAMEWORK_ORDER if fw in results]
    return known + [fw for fw in results if fw not in known]


def _name(framework: str) -> str:
    return DISPLAY_NAMES.get(framework, framework)


def build_facts_table(run: dict, frameworks: list[str], operations: list[str]) -> str:
    rows = [
        "| Fact | Value |",
        "| --- | --- |",
        f"| Operations tested | {len(operations)} (CRUD, filtering, relation serialization, bulk serialization) |",
        f"| Frameworks | {', '.join(_name(fw) for fw in frameworks)} |",
        f"| Python | {run.get('python_version', 'Unknown')} |",
        f"| Run date | {run.get('timestamp', 'Unknown')} |",
        "| Database | SQLite in-memory, same Django models for every framework |",
    ]
    return "\n".join(rows)


def build_results_table(results: dict, frameworks: list[str], operations: list[str]) -> str:
    rows = [
        "| Operation | " + " | ".join(_name(fw) for fw in frameworks) + " |",
        "| --- | " + " | ".join("---" for _ in frameworks) + " |",
    ]
    for op in operations:
        values = [
            f"{results[fw][op]['median_ms']:.2f}ms" if op in results[fw] else "N/A"
            for fw in frameworks
        ]
        rows.append(f"| {op.replace('_', ' ').capitalize()} | " + " | ".join(values) + " |")
    return "\n".join(rows)


def replace_region(text: str, name: str, content: str) -> str:
    pattern = re.compile(
        rf"(<!-- {name}:start -->\n).*?(\n<!-- {name}:end -->)", re.DOTALL
    )
    if not pattern.search(text):
        raise ValueError(f"Missing <!-- {name}:start/end --> markers")
    return pattern.sub(lambda m: m.group(1) + content + m.group(2), text)


def generate_markdown_report(results_file: Path, output_file: Path) -> None:
    """Update the facts and results tables of the comparison page."""
    if not results_file.exists():
        print(f"Error: Results file not found: {results_file}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(results_file.read_text())
    if not data.get("runs"):
        print("Error: No comparison runs found in results file", file=sys.stderr)
        sys.exit(1)

    run = data["runs"][-1]
    results = run.get("results", {})
    if not results:
        print("Error: No framework results found", file=sys.stderr)
        sys.exit(1)
    frameworks = _ordered_frameworks(results)
    operations = sorted(results[frameworks[0]])

    text = output_file.read_text()
    text = replace_region(
        text, "comparison-facts", build_facts_table(run, frameworks, operations)
    )
    text = replace_region(
        text, "comparison-results", build_results_table(results, frameworks, operations)
    )
    output_file.write_text(text)
    print(f"Comparison tables updated: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Update docs/comparison.md tables")
    root = Path(__file__).parent.parent.parent
    parser.add_argument("--input", type=Path, default=root / "comparison_results.json")
    parser.add_argument("--output", type=Path, default=root / "docs" / "comparison.md")
    args = parser.parse_args()
    generate_markdown_report(args.input, args.output)


if __name__ == "__main__":
    main()
