#!/usr/bin/env python3
"""
Batch runner for daily_candle_analysis.py

Features:
- Configure time frame (TF), ignore candles (IGNORE_CANDLES), and currency list at the top
- Creates per-currency, per-timeframe directories under candle_analysis/
- Runs daily_candle_analysis.py for each currency, saving timestamped logs
- Colored, structured console logging; plain logs are written to files
"""

import os
import sys
import subprocess
import datetime
import argparse
from typing import List


# =====================
# User-configurable vars
# =====================
TF = "3D"  # e.g., "D", "2D", "3W", "W"
IGNORE_CANDLES = 0
CURRENCIES: List[str] = [
    "USD",
    "EUR",
    "GBP",
    "JPY",
    "CHF",
    "CAD",
    "AUD",
    "NZD",
]


# =====================
# Constants
# =====================
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
PYTHON_EXE = sys.executable or "python3"
SCRIPT_TO_RUN = os.path.join(PROJECT_ROOT, "daily_candle_analysis.py")
OUTPUT_ROOT = os.path.join(PROJECT_ROOT, "candle_analysis")


# =====================
# Simple color helpers
# =====================
class Ansi:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"


def colorize(text: str, color: str) -> str:
    return f"{color}{text}{Ansi.RESET}"


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def timestamp_for_filename() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def run_for_currency(currency: str, tf: str, ignore_candles: int, json_output: str = None, batch_timestamp: str = None) -> int:
    currency = currency.upper().strip()
    out_dir = os.path.join(OUTPUT_ROOT, currency, tf)
    ensure_dir(out_dir)

    ts = timestamp_for_filename()
    log_path = os.path.join(out_dir, f"{currency}_{tf}_{ts}.log")

    header = f"[RUN] currency={currency} tf={tf} ignore_candles={ignore_candles}"
    print(colorize(header, Ansi.CYAN))

    cmd = [
        PYTHON_EXE,
        SCRIPT_TO_RUN,
        "--currency",
        currency,
        "--tf",
        tf,
        "--ignore-candles",
        str(ignore_candles),
    ]
    
    if json_output:
        cmd.extend(["--json-output", json_output])
    
    if batch_timestamp:
        cmd.extend(["--timestamp", batch_timestamp])

    with open(log_path, "w", encoding="utf-8") as log_file:
        log_file.write(f"{header}\n")
        log_file.write(f"Command: {' '.join(cmd)}\n")
        log_file.write("=" * 120 + "\n\n")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=PROJECT_ROOT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        assert process.stdout is not None
        for line in process.stdout:
            # Stream colored to console
            line_to_print = line.rstrip("\n")
            # Heuristic coloring: highlight errors/warnings
            if "❌" in line_to_print or "error" in line_to_print.lower():
                print(colorize(line_to_print, Ansi.RED))
            elif "⚠️" in line_to_print or "warn" in line_to_print.lower():
                print(colorize(line_to_print, Ansi.YELLOW))
            elif "✅" in line_to_print or "📈" in line_to_print or "📊" in line_to_print:
                print(colorize(line_to_print, Ansi.GREEN))
            else:
                print(line_to_print)

            # Write plain to file
            log_file.write(line)

        process.wait()
        rc = process.returncode

        footer = f"Exit code: {rc}"
        if rc == 0:
            print(colorize(footer, Ansi.GREEN))
        else:
            print(colorize(footer, Ansi.RED))
        log_file.write("\n" + footer + "\n")

    return rc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch runner for daily_candle_analysis.py across currencies"
    )
    parser.add_argument(
        "--tf", "--timeframe",
        dest="tf",
        default=TF,
        help="Timeframe like D, 2D, W, 3W (default: value in script)",
    )
    parser.add_argument(
        "--ignore-candles",
        dest="ignore_candles",
        type=int,
        default=IGNORE_CANDLES,
        help="Number of most recent candles to ignore (default: value in script)",
    )
    parser.add_argument(
        "--json-output",
        dest="json_output",
        type=str,
        default=None,
        help="Directory path to save JSON output files (optional)",
    )
    args = parser.parse_args()

    selected_tf = args.tf
    selected_ignore = args.ignore_candles
    json_output = args.json_output

    print(colorize("Batch Candle Analysis Runner", Ansi.BOLD))
    print(colorize(f"TF={selected_tf}  IGNORE_CANDLES={selected_ignore}", Ansi.DIM))
    print(colorize(f"Currencies: {', '.join(CURRENCIES)}", Ansi.DIM))
    print()

    ensure_dir(OUTPUT_ROOT)

    # Generate a single timestamp for all JSON files in this batch run
    batch_timestamp = timestamp_for_filename() if json_output else None

    overall_failures = 0
    for cur in CURRENCIES:
        print(colorize("-" * 80, Ansi.MAGENTA))
        rc = run_for_currency(cur, selected_tf, selected_ignore, json_output, batch_timestamp)
        if rc != 0:
            overall_failures += 1

    print()
    summary = f"Completed. Failures: {overall_failures} of {len(CURRENCIES)}"
    if overall_failures == 0:
        print(colorize(summary, Ansi.GREEN))
    else:
        print(colorize(summary, Ansi.YELLOW if overall_failures < len(CURRENCIES) else Ansi.RED))

    print(colorize(f"Logs saved under: {OUTPUT_ROOT}", Ansi.BLUE))
    return 0 if overall_failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())


