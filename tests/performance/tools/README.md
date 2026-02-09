# Performance Analysis Tools

This directory contains analysis tools for performance benchmarking and regression detection.

## 📊 Available Tools

### 1. **analyze_perf.py** - Quick Performance Overview

Displays the last 5 performance test runs with side-by-side comparison.

```bash
python tests/performance/tools/analyze_perf.py
```

**Output:**
- Last 5 runs with timestamps and Python versions
- Per-benchmark metrics (median/avg in ms)
- Delta between latest and previous run
- Color-coded indicators (🔴 slower, 🟢 faster, ⚪ unchanged)

**Use when:** You want a quick overview of recent performance trends.

---

### 2. **compare_days.py** - Day-over-Day Comparison

Compares average performance between two different days.

```bash
python tests/performance/tools/compare_days.py
```

**Output:**
- Average metrics for all runs on Day 1 vs Day 2
- Percentage change for each benchmark
- Top 10 biggest regressions
- Summary statistics (N slower, N faster, N unchanged)

**Use when:** You want to compare performance between different days or code versions.

---

### 3. **analyze_variance.py** - Stability Analysis

Analyzes performance variance and stability of benchmarks across multiple runs.

```bash
python tests/performance/tools/analyze_variance.py
```

**Output:**
- Coefficient of Variation (CV%) for each benchmark
- Stability classification (🟢 stable <10%, 🟡 moderate 10-15%, 🔴 unstable >15%)
- Mean, StdDev, Min, Max values
- Early vs Late runs comparison
- Identification of unstable benchmarks

**Use when:** You suspect noise or want to verify benchmark reliability.

---

### 4. **detect_regression.py** - Statistical Regression Detection ⭐

**Primary tool for CI/CD integration.** Uses statistical analysis to detect real regressions vs noise.

```bash
# Default: compare last 5 runs vs previous 5 runs
python tests/performance/tools/detect_regression.py

# Custom configuration
python tests/performance/tools/detect_regression.py \
  --baseline-size 10 \
  --current-size 10 \
  --threshold 10.0 \
  --significance 2.5
```

**Parameters:**
- `--baseline-size N`: Number of older runs to use as baseline (default: 5)
- `--current-size N`: Number of recent runs to compare (default: 5)
- `--threshold PCT`: Minimum % change to consider (default: 15.0)
- `--significance SIGMA`: Statistical significance threshold in σ (default: 2.0)

**Output:**
- Regressions detected (sorted by % change)
- Improvements detected
- Stable benchmarks count
- Statistical significance markers (Nσ)

**Exit codes:**
- `0` - No regressions detected ✅
- `1` - Regressions detected ❌

**Use when:**
- Running automated regression checks in CI/CD
- Verifying if performance changes are statistically significant
- Need to filter out noise from real regressions

---

## 🔧 Existing Tools (tests/performance/)

### **generate_report.py** - HTML Report Generator

Generates interactive Chart.js HTML report from `performance_results.json`.

```bash
python tests/performance/generate_report.py

# Custom paths
python tests/performance/generate_report.py \
  --input path/to/results.json \
  --output path/to/report.html
```

**Output:** Interactive `performance_report.html` with bar/line charts.

---

### **check_regression.py** - Simple Regression Check

Legacy regression checker with fixed threshold.

```bash
python tests/performance/check_regression.py \
  --baseline path/to/baseline.json \
  --current path/to/current.json \
  --threshold 20
```

**Note:** Prefer `detect_regression.py` for more robust statistical analysis.

---

## 📈 Workflow Recommendations

### For Development

```bash
# 1. Run performance tests
./run-performance.sh

# 2. Quick check of latest results
python tests/performance/tools/analyze_perf.py

# 3. Check stability if suspicious
python tests/performance/tools/analyze_variance.py

# 4. Statistical regression detection
python tests/performance/tools/detect_regression.py
```

### For CI/CD

```bash
# Run tests multiple times for statistical reliability
for i in 1 2 3 4 5; do
  python -m django test tests.performance --settings=tests.test_settings --tag=performance -v0
done

# Detect regressions with strict threshold
python tests/performance/tools/detect_regression.py --threshold 10.0 --significance 2.0
```

### For Analysis

```bash
# Compare yesterday vs today
python tests/performance/tools/compare_days.py

# Check variance over last N runs
python tests/performance/tools/analyze_variance.py

# Generate visual report
python tests/performance/generate_report.py
```

---

## 🎯 Understanding Results

### Coefficient of Variation (CV%)

Measures relative variability:
- **CV < 10%**: Benchmark is stable ✅
- **CV 10-15%**: Moderate variance, acceptable 🟡
- **CV > 15%**: High variance, investigate 🔴

### Statistical Significance (σ)

Number of standard deviations from baseline:
- **< 2σ**: Likely noise, not significant
- **2-3σ**: Possibly significant (95-99% confidence)
- **> 3σ**: Highly significant (99.7%+ confidence)

### When to Worry

**Real regression indicators:**
- High % change (>15%) **AND** high σ (>2.0)
- Consistent degradation across multiple runs
- Affects benchmarks that should be impacted by code changes

**Likely noise:**
- Low absolute time change (<0.1ms)
- High variance in both baseline and current
- Affects unrelated benchmarks
- Not reproducible across runs

---

## 📝 Output Files

All tools read from:
- `performance_results.json` - Accumulated benchmark results (gitignored)

Report output:
- `performance_report.html` - Interactive visual report (gitignored)

---

## 🚀 Tips

1. **Run tests 5+ times** before comparing for statistical reliability
2. **Close background apps** before benchmarking to reduce noise
3. **Use same machine** for comparing different code versions
4. **Filter microsecond tests** - benchmarks <0.001ms have high noise
5. **Check system load** - CPU throttling affects results
6. **Warm up first** - first run is often slower (JIT, cache)

---

For more details, see `CLAUDE.md` in the project root.
