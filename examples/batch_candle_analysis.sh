#!/bin/sh

# =====================
# Configuration (defaults)
# =====================
TIMEFRAME=1W
IGNORE_CANDLES=1
JSON_OUTPUT=./candle_analysis/json_output/

# =====================
# Parse Command Line Arguments
# =====================
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  -t, --tf TIMEFRAME          Set timeframe (default: 1W)"
    echo "  -i, --ignore-candles NUM    Set ignore candles count (default: 0)"
    echo "  -j, --json-output PATH      Set JSON output directory (default: ./candle_analysis/json_output/)"
    echo "  -h, --help                  Show this help message"
    exit 1
}

while [ $# -gt 0 ]; do
    case $1 in
        -t|--tf)
            TIMEFRAME="$2"
            shift 2
            ;;
        -i|--ignore-candles)
            IGNORE_CANDLES="$2"
            shift 2
            ;;
        -j|--json-output)
            JSON_OUTPUT="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

# =====================
# ANSI Color Codes
# =====================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

# =====================
# Helper Functions
# =====================
print_header() {
    printf "%b\n" "${BOLD}${CYAN}════════════════════════════════════════════════════════════════${NC}"
    printf "%b\n" "${BOLD}${CYAN}  $1${NC}"
    printf "%b\n" "${BOLD}${CYAN}════════════════════════════════════════════════════════════════${NC}"
}

print_section() {
    printf "\n%b\n" "${BOLD}${MAGENTA}▶ $1${NC}"
    printf "%b\n" "${DIM}────────────────────────────────────────────────────────────${NC}"
}

print_success() {
    printf "%b\n" "${GREEN}✓${NC} $1"
}

print_error() {
    printf "%b\n" "${RED}✗${NC} $1"
}

print_info() {
    printf "%b\n" "${BLUE}ℹ${NC} $1"
}

print_warning() {
    printf "%b\n" "${YELLOW}⚠${NC} $1"
}

# =====================
# Main Execution
# =====================
print_header "Batch Candle Analysis Runner"
printf "%b\n" "${DIM}Timeframe: ${BOLD}${TIMEFRAME}${NC}${DIM} | Ignore Candles: ${BOLD}${IGNORE_CANDLES}${NC}${DIM} | JSON Output: ${BOLD}${JSON_OUTPUT}${NC}"
echo ""

# Run the batch analysis
print_section "Running Batch Analysis"
if python3 run_candle_batch.py --tf "$TIMEFRAME" --ignore-candles "$IGNORE_CANDLES" --json-output "$JSON_OUTPUT"; then
    print_success "Batch analysis completed successfully"
else
    print_error "Batch analysis failed with exit code $?"
    exit 1
fi

# Check if output directory exists
ANALYSIS_DIR="candle_analysis"
if [ ! -d "$ANALYSIS_DIR" ]; then
    print_error "Analysis directory '$ANALYSIS_DIR' not found"
    exit 1
fi

# Search for summaries
print_section "Summary Analysis"
echo ""

# Bullish Summary
print_info "Searching for bullish patterns..."
GREP_CMD_BULL="grep -rin \"summary.*bul\" \"$JSON_OUTPUT\""
printf "%b\n" "${DIM}Command: ${GREP_CMD_BULL}${NC}"
eval "$GREP_CMD_BULL"

print_info "Searching for bearish patterns..."
GREP_CMD_BEAR="grep -rin \"summary.*bear\" \"$JSON_OUTPUT\""
printf "%b\n" "${DIM}Command: ${GREP_CMD_BEAR}${NC}"
eval "$GREP_CMD_BEAR" 

echo "cp -r ./candle_analysis/json_output/*$TIMEFRAME_*20251110* <DEST>"
