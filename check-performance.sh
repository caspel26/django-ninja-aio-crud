#!/bin/bash
# Performance analysis helper script
# Provides quick access to performance analysis tools

set -e

TOOLS_DIR="tests/performance/tools"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

show_help() {
    echo "Performance Analysis Tools"
    echo "=========================="
    echo ""
    echo "Usage: ./check-performance.sh [command]"
    echo ""
    echo "Commands:"
    echo "  quick        - Quick overview of last 5 runs"
    echo "  compare      - Compare performance between days"
    echo "  variance     - Analyze benchmark stability"
    echo "  detect       - Detect regressions (recommended)"
    echo "  all          - Run all analysis tools"
    echo "  help         - Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./check-performance.sh detect"
    echo "  ./check-performance.sh quick"
    echo "  ./check-performance.sh all"
    echo ""
}

run_quick() {
    echo -e "${GREEN}Running quick analysis...${NC}"
    python "$TOOLS_DIR/analyze_perf.py"
}

run_compare() {
    echo -e "${GREEN}Running day comparison...${NC}"
    python "$TOOLS_DIR/compare_days.py"
}

run_variance() {
    echo -e "${GREEN}Running variance analysis...${NC}"
    python "$TOOLS_DIR/analyze_variance.py"
}

run_detect() {
    echo -e "${GREEN}Running regression detection...${NC}"
    python "$TOOLS_DIR/detect_regression.py"
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}✅ No regressions detected!${NC}"
    else
        echo -e "${RED}❌ Regressions detected!${NC}"
        exit 1
    fi
}

run_all() {
    echo "================================================"
    run_quick
    echo ""
    echo "================================================"
    run_variance
    echo ""
    echo "================================================"
    run_detect
}

# Main
case "${1:-help}" in
    quick)
        run_quick
        ;;
    compare)
        run_compare
        ;;
    variance)
        run_variance
        ;;
    detect)
        run_detect
        ;;
    all)
        run_all
        ;;
    help|--help|-h|"")
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac
