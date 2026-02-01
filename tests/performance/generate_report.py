#!/usr/bin/env python
"""Generate an interactive HTML performance report from performance_results.json.

Uses Chart.js via CDN — no Python dependencies beyond the stdlib.

Usage:
    python tests/performance/generate_report.py
    python tests/performance/generate_report.py --input path/to/results.json --output report.html
"""

import argparse
import json
import html
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "performance_results.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "performance_report.html"

COLORS = [
    "rgba(54, 162, 235, 0.8)",
    "rgba(255, 99, 132, 0.8)",
    "rgba(75, 192, 192, 0.8)",
    "rgba(255, 206, 86, 0.8)",
    "rgba(153, 102, 255, 0.8)",
    "rgba(255, 159, 64, 0.8)",
    "rgba(46, 204, 113, 0.8)",
    "rgba(231, 76, 60, 0.8)",
]

BORDER_COLORS = [c.replace("0.8", "1") for c in COLORS]


def load_results(path: Path) -> dict:
    if not path.exists():
        print(f"Error: {path} not found. Run performance tests first.", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text())


def build_latest_run_charts(run: dict) -> str:
    """Build Chart.js chart configs for the latest run, one per test class."""
    results = run["results"]
    charts_html = ""
    chart_configs = ""
    idx = 0

    for cls_name, benchmarks in results.items():
        canvas_id = f"chart_{idx}"
        labels = list(benchmarks.keys())
        avg_values = [b["avg_ms"] for b in benchmarks.values()]
        min_values = [b["min_ms"] for b in benchmarks.values()]
        max_values = [b["max_ms"] for b in benchmarks.values()]
        median_values = [b["median_ms"] for b in benchmarks.values()]

        # Build the data table
        table_rows = ""
        for name, stats in benchmarks.items():
            table_rows += f"""
            <tr>
                <td>{html.escape(name)}</td>
                <td>{stats['iterations']}</td>
                <td>{stats['min_ms']:.4f}</td>
                <td>{stats['avg_ms']:.4f}</td>
                <td>{stats['median_ms']:.4f}</td>
                <td>{stats['max_ms']:.4f}</td>
            </tr>"""

        charts_html += f"""
        <div class="chart-section">
            <h2>{html.escape(cls_name)}</h2>
            <div class="chart-container">
                <canvas id="{canvas_id}"></canvas>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Benchmark</th>
                        <th>Iterations</th>
                        <th>Min (ms)</th>
                        <th>Avg (ms)</th>
                        <th>Median (ms)</th>
                        <th>Max (ms)</th>
                    </tr>
                </thead>
                <tbody>{table_rows}
                </tbody>
            </table>
        </div>"""

        labels_json = json.dumps(labels)
        chart_configs += f"""
        new Chart(document.getElementById('{canvas_id}'), {{
            type: 'bar',
            data: {{
                labels: {labels_json},
                datasets: [
                    {{
                        label: 'Avg (ms)',
                        data: {json.dumps(avg_values)},
                        backgroundColor: '{COLORS[0]}',
                        borderColor: '{BORDER_COLORS[0]}',
                        borderWidth: 1
                    }},
                    {{
                        label: 'Median (ms)',
                        data: {json.dumps(median_values)},
                        backgroundColor: '{COLORS[2]}',
                        borderColor: '{BORDER_COLORS[2]}',
                        borderWidth: 1
                    }},
                    {{
                        label: 'Min (ms)',
                        data: {json.dumps(min_values)},
                        backgroundColor: '{COLORS[3]}',
                        borderColor: '{BORDER_COLORS[3]}',
                        borderWidth: 1
                    }},
                    {{
                        label: 'Max (ms)',
                        data: {json.dumps(max_values)},
                        backgroundColor: '{COLORS[1]}',
                        borderColor: '{BORDER_COLORS[1]}',
                        borderWidth: 1
                    }}
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    title: {{
                        display: true,
                        text: '{html.escape(cls_name)}',
                        font: {{ size: 16 }}
                    }},
                    legend: {{ position: 'top' }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{ display: true, text: 'Time (ms)' }}
                    }},
                    x: {{
                        ticks: {{ maxRotation: 45, minRotation: 25 }}
                    }}
                }}
            }}
        }});
        """
        idx += 1

    return charts_html, chart_configs


def build_trend_charts(runs: list[dict]) -> str:
    """Build line charts showing benchmark trends across runs."""
    if len(runs) < 2:
        return "", ""

    # Collect all (class, benchmark) pairs across all runs
    all_benchmarks: dict[str, dict[str, list]] = {}
    timestamps = []
    for run in runs:
        ts = run["timestamp"][:19].replace("T", " ")
        timestamps.append(ts)
        for cls_name, benchmarks in run["results"].items():
            if cls_name not in all_benchmarks:
                all_benchmarks[cls_name] = {}
            for bench_name, stats in benchmarks.items():
                key = bench_name
                if key not in all_benchmarks[cls_name]:
                    all_benchmarks[cls_name][key] = []
                all_benchmarks[cls_name][key].append(stats["median_ms"])

    charts_html = '<h1 class="section-title">Trends Across Runs</h1>'
    chart_configs = ""
    idx = 100

    for cls_name, benchmarks in all_benchmarks.items():
        canvas_id = f"trend_{idx}"
        charts_html += f"""
        <div class="chart-section">
            <h2>{html.escape(cls_name)} — Median Trend</h2>
            <div class="chart-container">
                <canvas id="{canvas_id}"></canvas>
            </div>
        </div>"""

        datasets = []
        for i, (bench_name, values) in enumerate(benchmarks.items()):
            color = COLORS[i % len(COLORS)]
            border = BORDER_COLORS[i % len(BORDER_COLORS)]
            datasets.append({
                "label": bench_name,
                "data": values,
                "borderColor": border,
                "backgroundColor": color,
                "tension": 0.2,
                "fill": False,
            })

        chart_configs += f"""
        new Chart(document.getElementById('{canvas_id}'), {{
            type: 'line',
            data: {{
                labels: {json.dumps(timestamps)},
                datasets: {json.dumps(datasets)}
            }},
            options: {{
                responsive: true,
                plugins: {{
                    title: {{
                        display: true,
                        text: '{html.escape(cls_name)} — Median (ms) Over Runs',
                        font: {{ size: 16 }}
                    }},
                    legend: {{ position: 'top' }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{ display: true, text: 'Median Time (ms)' }}
                    }},
                    x: {{
                        title: {{ display: true, text: 'Run' }},
                        ticks: {{ maxRotation: 45, minRotation: 25 }}
                    }}
                }}
            }}
        }});
        """
        idx += 1

    return charts_html, chart_configs


def generate_html(data: dict) -> str:
    runs = data.get("runs", [])
    if not runs:
        print("Error: No runs found in results file.", file=sys.stderr)
        sys.exit(1)

    latest = runs[-1]
    ts = latest["timestamp"][:19].replace("T", " ")
    py_ver = latest.get("python_version", "unknown")

    latest_html, latest_configs = build_latest_run_charts(latest)
    trend_html, trend_configs = build_trend_charts(runs)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Performance Report — django-ninja-aio-crud</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            padding: 2rem;
        }}
        h1 {{
            text-align: center;
            margin-bottom: 0.5rem;
            font-size: 1.8rem;
            color: #38bdf8;
        }}
        .meta {{
            text-align: center;
            color: #94a3b8;
            margin-bottom: 2rem;
            font-size: 0.9rem;
        }}
        .section-title {{
            margin-top: 3rem;
            margin-bottom: 1.5rem;
            border-top: 1px solid #334155;
            padding-top: 1.5rem;
        }}
        .chart-section {{
            background: #1e293b;
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }}
        .chart-section h2 {{
            margin-bottom: 1rem;
            font-size: 1.2rem;
            color: #7dd3fc;
        }}
        .chart-container {{
            position: relative;
            height: 350px;
            margin-bottom: 1.5rem;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
        }}
        th, td {{
            padding: 0.5rem 0.75rem;
            text-align: left;
            border-bottom: 1px solid #334155;
        }}
        th {{
            color: #38bdf8;
            font-weight: 600;
            background: #0f172a;
        }}
        tr:hover td {{ background: #334155; }}
        td {{ color: #cbd5e1; }}
    </style>
</head>
<body>
    <h1>Performance Report</h1>
    <p class="meta">
        Latest run: {html.escape(ts)} &middot; Python {html.escape(py_ver)} &middot;
        {len(runs)} run(s) recorded
    </p>

    <h1 class="section-title">Latest Run</h1>
    {latest_html}
    {trend_html}

    <script>
    {latest_configs}
    {trend_configs}
    </script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Generate performance report HTML")
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to performance_results.json",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path for the output HTML report",
    )
    args = parser.parse_args()

    data = load_results(args.input)
    html_content = generate_html(data)
    args.output.write_text(html_content)
    print(f"Report generated: {args.output}")


if __name__ == "__main__":
    main()
