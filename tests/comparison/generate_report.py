#!/usr/bin/env python3
"""Generate interactive HTML comparison report from framework benchmark results.

This script reads comparison_results.json and generates an interactive HTML
report with Chart.js visualizations comparing django-ninja-aio-crud against
other popular Python REST frameworks.
"""

import argparse
import html
import json
import sys
from pathlib import Path


def generate_html_report(results_file: Path, output_file: Path) -> None:
    """Generate HTML comparison report from JSON results."""
    if not results_file.exists():
        print(f"Error: Results file not found: {results_file}", file=sys.stderr)
        sys.exit(1)

    with open(results_file) as f:
        data = json.load(f)

    if "runs" not in data or not data["runs"]:
        print("Error: No comparison runs found in results file", file=sys.stderr)
        sys.exit(1)

    latest_run = data["runs"][-1]
    ts = latest_run.get("timestamp", "Unknown")[:19].replace("T", " ")
    py_ver = latest_run.get("python_version", "Unknown")
    results = latest_run.get("results", {})

    # Extract framework names and operations
    frameworks = list(results.keys())
    if not frameworks:
        print("Error: No framework results found", file=sys.stderr)
        sys.exit(1)

    # Get all operations from the first framework
    operations = list(results[frameworks[0]].keys())

    # Build chart sections and configs
    chart_html = ""
    chart_configs = ""

    # Color palette matching performance report style
    colors = [
        "rgba(76, 175, 80, 0.75)",    # Green - django-ninja-aio-crud
        "rgba(33, 150, 243, 0.75)",   # Blue - Django Ninja
        "rgba(255, 152, 0, 0.75)",    # Orange - ADRF
        "rgba(156, 39, 176, 0.75)",   # Purple - FastAPI
    ]
    border_colors = [c.replace("0.75", "1") for c in colors]

    for idx, operation in enumerate(operations):
        canvas_id = f"chart_{idx}"
        operation_title = operation.replace("_", " ").title()

        # Collect data for this operation
        op_frameworks = []
        median_values = []
        avg_values = []
        min_values = []
        max_values = []

        for framework in frameworks:
            if operation in results[framework]:
                stats = results[framework][operation]
                op_frameworks.append(framework)
                median_values.append(stats["median_ms"])
                avg_values.append(stats["avg_ms"])
                min_values.append(stats["min_ms"])
                max_values.append(stats["max_ms"])

        # Build data table
        table_rows = ""
        for i, framework in enumerate(op_frameworks):
            table_rows += f"""
            <tr>
                <td>{html.escape(framework)}</td>
                <td>{median_values[i]:.4f}</td>
                <td>{avg_values[i]:.4f}</td>
                <td>{min_values[i]:.4f}</td>
                <td>{max_values[i]:.4f}</td>
            </tr>"""

        chart_html += f"""
        <div class="chart-section">
            <h2>{html.escape(operation_title)}</h2>
            <div class="chart-container">
                <canvas id="{canvas_id}"></canvas>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Framework</th>
                        <th>Median (ms)</th>
                        <th>Avg (ms)</th>
                        <th>Min (ms)</th>
                        <th>Max (ms)</th>
                    </tr>
                </thead>
                <tbody>{table_rows}
                </tbody>
            </table>
        </div>"""

        # Generate chart config
        chart_configs += f"""
        new Chart(document.getElementById('{canvas_id}'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(op_frameworks)},
                datasets: [
                    {{
                        label: 'Median (ms)',
                        data: {json.dumps(median_values)},
                        backgroundColor: {json.dumps(colors[:len(op_frameworks)])},
                        borderColor: {json.dumps(border_colors[:len(op_frameworks)])},
                        borderWidth: 1
                    }}
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    title: {{
                        display: true,
                        text: '{html.escape(operation_title)}',
                        font: {{ size: 16 }}
                    }},
                    legend: {{ display: false }},
                    tooltip: {{
                        callbacks: {{
                            afterLabel: function(context) {{
                                const idx = context.dataIndex;
                                return [
                                    `Avg: {json.dumps(avg_values)}[idx].toFixed(4) + ' ms'`,
                                    `Min: {json.dumps(min_values)}[idx].toFixed(4) + ' ms'`,
                                    `Max: {json.dumps(max_values)}[idx].toFixed(4) + ' ms'`
                                ];
                            }}
                        }}
                    }}
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

    # Generate HTML matching performance report style
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Framework Comparison — django-ninja-aio-crud</title>
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
        <span>Framework Comparison</span>
    </div>
    <div class="container">
        <div class="hero">
            <h1>Framework Comparison</h1>
            <p class="subtitle">Comparing django-ninja-aio-crud against other Python REST frameworks</p>
            <div class="meta-pills">
                <span class="meta-pill"><strong>Run</strong> {html.escape(ts)}</span>
                <span class="meta-pill"><strong>Python</strong> {html.escape(py_ver)}</span>
                <span class="meta-pill"><strong>Frameworks</strong> {len(frameworks)}</span>
                <span class="meta-pill"><strong>Operations</strong> {len(operations)}</span>
            </div>
        </div>

        <h1 class="section-title">Results</h1>
        {chart_html}

        <div class="footer">
            Generated by <a href="https://github.com/caspel26/django-ninja-aio-crud">django-ninja-aio-crud</a> comparison suite
        </div>
    </div>

    <script>
    // Configure Chart.js defaults to match theme
    const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    Chart.defaults.color = isDark ? '#a0a0b8' : '#555';
    Chart.defaults.borderColor = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)';
    Chart.defaults.font.family = "'Roboto', sans-serif";

    {chart_configs}
    </script>
</body>
</html>"""

    output_file.write_text(html_content)
    print(f"Comparison report generated: {output_file}")


def main():
    """Parse arguments and generate report."""
    parser = argparse.ArgumentParser(
        description="Generate framework comparison HTML report from benchmark results"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).parent.parent.parent / "comparison_results.json",
        help="Path to comparison results JSON file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent.parent.parent / "comparison_report.html",
        help="Path to output HTML report file",
    )

    args = parser.parse_args()
    generate_html_report(args.input, args.output)


if __name__ == "__main__":
    main()
