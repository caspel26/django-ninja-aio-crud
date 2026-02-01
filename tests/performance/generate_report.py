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
    "rgba(103, 58, 183, 0.75)",   # deep purple (primary)
    "rgba(171, 71, 188, 0.75)",   # purple accent
    "rgba(126, 87, 194, 0.75)",   # lighter purple
    "rgba(186, 104, 200, 0.75)",  # pink-purple
    "rgba(94, 53, 177, 0.75)",    # darker purple
    "rgba(149, 117, 205, 0.75)",  # soft violet
    "rgba(206, 147, 216, 0.75)",  # lavender
    "rgba(69, 39, 160, 0.75)",    # indigo-purple
]

BORDER_COLORS = [c.replace("0.75", "1") for c in COLORS]


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
    <title>Performance Benchmarks — django-ninja-aio-crud</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&family=Roboto+Mono:wght@400;500&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <style>
        :root {{
            --md-primary: #673ab7;
            --md-primary-light: #7e57c2;
            --md-primary-dark: #5e35b1;
            --md-accent: #7c4dff;
            --md-bg: #fff;
            --md-bg-alt: #f5f5f6;
            --md-fg: #1a1a2e;
            --md-fg-light: #555;
            --md-fg-lighter: #999;
            --md-border: rgba(0, 0, 0, 0.07);
            --md-code-bg: #f5f5f5;
            --md-shadow: rgba(0, 0, 0, 0.08);
            --md-shadow-heavy: rgba(0, 0, 0, 0.12);
            --chart-grid: rgba(0, 0, 0, 0.06);
            --chart-text: #555;
        }}
        @media (prefers-color-scheme: dark) {{
            :root {{
                --md-bg: #1e1e2e;
                --md-bg-alt: #2a2a3e;
                --md-fg: #e2e2f0;
                --md-fg-light: #a0a0b8;
                --md-fg-lighter: #707088;
                --md-border: rgba(255, 255, 255, 0.08);
                --md-code-bg: #252538;
                --md-shadow: rgba(0, 0, 0, 0.25);
                --md-shadow-heavy: rgba(0, 0, 0, 0.4);
                --chart-grid: rgba(255, 255, 255, 0.08);
                --chart-text: #a0a0b8;
            }}
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Roboto', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--md-bg);
            color: var(--md-fg);
            line-height: 1.6;
        }}
        .header {{
            background: var(--md-primary);
            color: #fff;
            padding: 0.6rem 2rem;
            font-size: 0.82rem;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        .header a {{
            color: #fff;
            text-decoration: none;
            opacity: 0.9;
        }}
        .header a:hover {{ opacity: 1; }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem 1.5rem;
        }}
        .hero {{
            text-align: center;
            padding: 2rem 0 1rem;
            border-bottom: 1px solid var(--md-border);
            margin-bottom: 2rem;
        }}
        .hero h1 {{
            font-size: 2rem;
            font-weight: 700;
            color: var(--md-fg);
            margin-bottom: 0.4rem;
        }}
        .hero .subtitle {{
            font-size: 1rem;
            color: var(--md-fg-light);
            margin-bottom: 1rem;
        }}
        .meta-pills {{
            display: flex;
            justify-content: center;
            gap: 0.5rem;
            flex-wrap: wrap;
        }}
        .meta-pill {{
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            background: var(--md-code-bg);
            border: 1px solid var(--md-border);
            border-radius: 2rem;
            padding: 0.3rem 0.9rem;
            font-size: 0.8rem;
            font-family: 'Roboto Mono', monospace;
            color: var(--md-fg-light);
        }}
        .meta-pill strong {{
            color: var(--md-primary-light);
            font-weight: 500;
        }}
        .section-title {{
            font-size: 1.4rem;
            font-weight: 700;
            color: var(--md-fg);
            margin: 2.5rem 0 1.5rem;
            padding-top: 1.5rem;
            border-top: 1px solid var(--md-border);
        }}
        .chart-section {{
            background: var(--md-bg-alt);
            border: 1px solid var(--md-border);
            border-radius: 10px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            transition: box-shadow 0.25s ease, transform 0.25s ease;
        }}
        .chart-section:hover {{
            box-shadow: 0 6px 20px var(--md-shadow);
            transform: translateY(-2px);
        }}
        .chart-section h2 {{
            margin-bottom: 1rem;
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--md-primary);
        }}
        .chart-container {{
            position: relative;
            height: 350px;
            margin-bottom: 1.5rem;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.82rem;
        }}
        th, td {{
            padding: 0.55rem 0.75rem;
            text-align: left;
            border-bottom: 1px solid var(--md-border);
        }}
        th {{
            color: var(--md-primary);
            font-weight: 600;
            background: var(--md-code-bg);
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}
        tr:hover td {{
            background: var(--md-code-bg);
        }}
        td {{
            color: var(--md-fg-light);
            font-family: 'Roboto Mono', monospace;
            font-size: 0.8rem;
        }}
        td:first-child {{
            font-family: 'Roboto', sans-serif;
            font-weight: 500;
            color: var(--md-fg);
        }}
        .footer {{
            text-align: center;
            margin-top: 3rem;
            padding: 1.5rem 0;
            border-top: 1px solid var(--md-border);
            font-size: 0.78rem;
            color: var(--md-fg-lighter);
        }}
        .footer a {{
            color: var(--md-primary-light);
            text-decoration: none;
        }}
        .footer a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="header">
        <a href="https://django-ninja-aio.com/">django-ninja-aio-crud</a>
        <span>&middot;</span>
        <span>Performance Benchmarks</span>
    </div>
    <div class="container">
        <div class="hero">
            <h1>Performance Benchmarks</h1>
            <p class="subtitle">Automated benchmark results for django-ninja-aio-crud</p>
            <div class="meta-pills">
                <span class="meta-pill"><strong>Run</strong> {html.escape(ts)}</span>
                <span class="meta-pill"><strong>Python</strong> {html.escape(py_ver)}</span>
                <span class="meta-pill"><strong>Runs</strong> {len(runs)}</span>
            </div>
        </div>

        <h1 class="section-title">Latest Run</h1>
        {latest_html}
        {trend_html}

        <div class="footer">
            Generated by <a href="https://github.com/caspel26/django-ninja-aio-crud">django-ninja-aio-crud</a> performance suite
        </div>
    </div>

    <script>
    // Configure Chart.js defaults to match theme
    const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    Chart.defaults.color = isDark ? '#a0a0b8' : '#555';
    Chart.defaults.borderColor = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)';
    Chart.defaults.font.family = "'Roboto', sans-serif";

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

    input_path = args.input.resolve()
    output_path = args.output.resolve()

    if not str(input_path).startswith(str(PROJECT_ROOT)):
        print(f"Error: input path must be within project root ({PROJECT_ROOT})", file=sys.stderr)
        sys.exit(1)
    if not str(output_path).startswith(str(PROJECT_ROOT)):
        print(f"Error: output path must be within project root ({PROJECT_ROOT})", file=sys.stderr)
        sys.exit(1)

    data = load_results(input_path)
    html_content = generate_html(data)
    output_path.write_text(html_content)
    print(f"Report generated: {output_path}")


if __name__ == "__main__":
    main()
