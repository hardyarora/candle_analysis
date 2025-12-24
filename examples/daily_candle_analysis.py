#!/usr/bin/env python3
"""
Candle Analysis Tool (Daily, Weekly, Monthly)

Analyzes candles for a specific currency across multiple timeframes based on
daily, weekly, or monthly granularity. Supports merged periods (e.g., 4D, 3D, 2D, D, 2W, 3W, W, 2M, 3M, M).

Merges consecutive candles to create custom timeframes and analyzes the relationship
between merged candle pairs (downclose, upclose, engulfing patterns).
"""

import requests
import datetime
import calendar
import argparse
import json
import os
from typing import Dict, List, Tuple, Optional
from tabulate import tabulate
from collections import defaultdict

# OANDA API Configuration
OANDA_API_URL = "https://api-fxpractice.oanda.com/v3/instruments/{instrument}/candles"
ACCESS_TOKEN = "3e243a07175dad2e3b13b43f7b0c3db2-e158044d41883ede91b90cb98b577e0f"

# Full instrument list from oanda_weekly.py
INSTRUMENTS = [
    "GBP_AUD",
    "GBP_NZD",
    "GBP_USD",
    "GBP_CAD",
    "GBP_JPY",
    "GBP_CHF",
    "EUR_AUD",
    "EUR_NZD",
    "EUR_JPY",
    "EUR_CAD",
    "EUR_CHF",
    "EUR_USD",
    "USD_JPY",
    "USD_CHF",
    "CAD_CHF",
    "CAD_JPY",
    "AUD_USD",
    "AUD_JPY",
    "AUD_CAD",
    "AUD_CHF",
    "NZD_USD",
    "NZD_JPY",
    "NZD_CAD",
    "NZD_CHF",
    "EUR_GBP",
    "USD_CAD",
    "AUD_NZD",
    "CHF_JPY",
    "XAG_USD",
    "XAU_USD"
]

INSTRUMENTS = list(set(INSTRUMENTS))

# Full currency names for display in summaries
CURRENCY_FULL_NAMES = {
    "USD": "United States Dollar",
    "EUR": "Euro",
    "GBP": "British Pound",
    "JPY": "Japanese Yen",
    "CHF": "Swiss Franc",
    "CAD": "Canadian Dollar",
    "AUD": "Australian Dollar",
    "NZD": "New Zealand Dollar",
}

def fetch_candles_raw(instrument: str, granularity: str = "D", count: int = 30) -> List[Dict]:
    """Fetch raw candles list from OANDA for given instrument and granularity."""
    params = {
        "granularity": granularity,
        "price": "M",
        "count": count,
    }
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    url = OANDA_API_URL.format(instrument=instrument)
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data.get("candles", [])
        return []
    except Exception:
        return []

def parse_timeframe(timeframe: str) -> Tuple[str, int]:
    """
    Parse timeframe strings like "D", "2D", "W", "3W" into (granularity, n_candles).
    Returns ("D"|"W", count:int)
    """
    tf = timeframe.upper().strip()
    if tf == "D":
        return ("D", 1)
    if tf == "W":
        return ("W", 1)
    if tf == "M":
        return ("M", 1)
    if tf.endswith("D") and tf[:-1].isdigit():
        return ("D", int(tf[:-1]))
    if tf.endswith("W") and tf[:-1].isdigit():
        return ("W", int(tf[:-1]))
    if tf.endswith("M") and tf[:-1].isdigit():
        return ("M", int(tf[:-1]))
    raise ValueError(f"Invalid timeframe: {timeframe}")

def merge_candles(candles: List[Dict]) -> Optional[Dict]:
    """
    Merge multiple candles into one.
    
    Rules:
    - high = max(all highs)
    - low = min(all lows)
    - open = first candle's open
    - close = last candle's close
    - time = first candle's time
    """
    if not candles:
        return None
    
    highs = [float(c["mid"]["h"]) for c in candles]
    lows = [float(c["mid"]["l"]) for c in candles]
    
    merged = {
        "high": max(highs),
        "low": min(lows),
        "open": candles[0]["mid"]["o"],
        "close": candles[-1]["mid"]["c"],
        "time": candles[0]["time"],
        "candle_count": len(candles)
    }
    return merged

# Default engulfing threshold (percentage)
DEFAULT_ENGULFING_THRESHOLD_PERCENT = 0.05  # 0.05% threshold

def analyze_candle_relation(mc1: Dict, mc2: Dict, engulfing_threshold_percent: float = DEFAULT_ENGULFING_THRESHOLD_PERCENT) -> str:
    """
    Analyze the relation between two merged candles (mc1 and mc2).
    
    mc1 is older (previous period), mc2 is newer (current period)
    
    Args:
        mc1: Previous period merged candle
        mc2: Current period merged candle
        engulfing_threshold_percent: Percentage threshold for engulfing detection (default: 0.05%)
                                     Allows slight tolerance when mc2's body is very close to engulfing mc1's body.
                                     Value is a percentage (e.g., 0.05 means 0.05%).
    
    Returns:
    - Combined pattern string like "downclose ⬇️ + bearish" or "upclose ⬆️ + bullish engulfing"
    """
    if not mc1 or not mc2:
        return "error"
    
    mc1_high = float(mc1["high"])
    mc1_low = float(mc1["low"])
    mc1_open = float(mc1["open"])
    mc1_close = float(mc1["close"])
    
    mc2_high = float(mc2["high"])
    mc2_low = float(mc2["low"])
    mc2_open = float(mc2["open"])
    mc2_close = float(mc2["close"])
    
    patterns = []
    
    # Define body ranges (using min/max of open/close for each candle)
    mc1_body_top = max(mc1_open, mc1_close)
    mc1_body_bottom = min(mc1_open, mc1_close)
    mc2_body_top = max(mc2_open, mc2_close)
    mc2_body_bottom = min(mc2_open, mc2_close)
    
    # Calculate body size for threshold calculation
    mc1_body_size = mc1_body_top - mc1_body_bottom
    
    # Calculate threshold as absolute value based on percentage of mc1's body size
    # Use a minimum threshold to handle very small bodies
    threshold_absolute = max(mc1_body_size * (engulfing_threshold_percent / 100.0), mc1_body_top * (engulfing_threshold_percent / 100.0))
    
    # Check for downclose (highest priority signal)
    if mc2_close < mc1_low:
        patterns.append("downclose ⬇️")
    
    # Check for upclose
    if mc2_close > mc1_high:
        patterns.append("upclose ⬆️")
    
    # Check for bullish/bearish engulfing: mc2's body engulfs mc1's body
    # mc2 body must extend above AND below mc1's body (with threshold tolerance)
    # Bottom check: mc2_body_bottom should be <= mc1_body_bottom + threshold (with tolerance)
    # Top check: mc2_body_top should be >= mc1_body_top - threshold (with tolerance)
    bottom_engulfs = mc2_body_bottom <= (mc1_body_bottom + threshold_absolute)
    top_engulfs = mc2_body_top >= (mc1_body_top - threshold_absolute)
    
    if bottom_engulfs and top_engulfs:
        if mc2_close > mc2_open:  # mc2 is bullish
            patterns.append("bullish engulfing")
        elif mc2_close < mc2_open:  # mc2 is bearish
            patterns.append("bearish engulfing")
    
    # # Check if mc2 is bullish (close > open)
    # if mc2_close > mc2_open:
    #     patterns.append("bullish")
    
    # # Check if mc2 is bearish (close < open)
    # if mc2_close < mc2_open:
    #     patterns.append("bearish")
    
    if not patterns:
        return "neutral"
    
    # Combine patterns with " + "
    return " + ".join(patterns)

def analyze_candles_for_currency(currency: str, timeframe: str, ignore_candles: int = 1) -> List[Dict]:
    """
    Analyze candles (daily, weekly, or monthly) for all instruments containing the given currency.
    
    Args:
        currency: Currency code (e.g., "GBP")
        timeframe: Timeframe like "4D", "3D", "2D", "D", "2W", "W", "2M", or "M"
        ignore_candles: Number of candles to ignore at the end (default: 1)
    
    Returns:
        List of analysis results for each instrument
    """
    # Parse timeframe
    granularity, n_candles = parse_timeframe(timeframe)
    
    if n_candles < 1 or n_candles > 10:
        unit = granularity
        raise ValueError(f"Timeframe must be between 1{unit} and 10{unit}, got {timeframe}")
    
    # Filter instruments containing the currency
    relevant_instruments = [
        inst for inst in INSTRUMENTS
        if currency in inst.split("_")
    ]
    
    if not relevant_instruments:
        print(f"❌ No instruments found for currency: {currency}")
        return []
    
    print(f"🔍 Analyzing {len(relevant_instruments)} instruments containing {currency}")
    print(f"📊 Timeframe: {timeframe} (merging {n_candles} {'daily' if granularity=='D' else ('weekly' if granularity=='W' else 'monthly')} candles)")
    print(f"⏭️  Ignoring last {ignore_candles} candle(s)")
    print()
    
    results = []
    
    for instrument in relevant_instruments:
        # Fetch candles based on granularity
        request_count = 30 if granularity == "D" else (120 if granularity == "W" else 240)
        candles = fetch_candles_raw(instrument, granularity=granularity, count=request_count)
        
        if len(candles) < (n_candles * 2) + ignore_candles:
            results.append({
                "Instrument": instrument,
                "Error": f"Not enough candles (need {n_candles * 2 + ignore_candles}, got {len(candles)})"
            })
            continue
        
        # Ignore the last N candles
        candles_to_process = candles[:-ignore_candles] if ignore_candles > 0 else candles
        
        # Get the last n_candles candles (most recent period)
        # Index -n_candles to end (but excluding last one)
        mc2_candles = candles_to_process[-n_candles:]
        
        # Get the n_candles before that (previous period)
        mc1_candles = candles_to_process[-(n_candles * 2):-n_candles]
        
        # Merge the candles
        mc1 = merge_candles(mc1_candles)
        mc2 = merge_candles(mc2_candles)
        
        # Get the time of the last candle in each merged period
        mc1_last_time = mc1_candles[-1]["time"] if mc1_candles else ""
        mc2_last_time = mc2_candles[-1]["time"] if mc2_candles else ""
        
        if not mc1 or not mc2:
            results.append({
                "Instrument": instrument,
                "Error": "Failed to merge candles"
            })
            continue
        
        # Analyze the relationship
        relation = analyze_candle_relation(mc1, mc2)
        
        # Determine color
        mc2_open = float(mc2["open"])
        mc2_close = float(mc2["close"])
        if mc2_close > mc2_open:
            color = "🟢 GREEN"
        elif mc2_close < mc2_open:
            color = "🔴 RED"
        else:
            color = "⚪ NEUTRAL"
        
        # Format dates
        try:
            mc1_time = datetime.datetime.fromisoformat(mc1["time"].replace("Z", "").replace(".000000000", ""))
            mc2_time = datetime.datetime.fromisoformat(mc2["time"].replace("Z", "").replace(".000000000", ""))
            mc1_last = datetime.datetime.fromisoformat(mc1_last_time.replace("Z", "").replace(".000000000", ""))
            mc2_last = datetime.datetime.fromisoformat(mc2_last_time.replace("Z", "").replace(".000000000", ""))

            if granularity == "M":
                # Use full month span for display
                mc1_start = mc1_time.replace(day=1)
                mc1_end = mc1_last.replace(day=calendar.monthrange(mc1_last.year, mc1_last.month)[1])
                mc2_start = mc2_time.replace(day=1)
                mc2_end = mc2_last.replace(day=calendar.monthrange(mc2_last.year, mc2_last.month)[1])
                mc1_time_str = f"{mc1_start.strftime('%Y-%m-%d')} to {mc1_end.strftime('%Y-%m-%d')}"
                mc2_time_str = f"{mc2_start.strftime('%Y-%m-%d')} to {mc2_end.strftime('%Y-%m-%d')}"
            else:
                mc1_time_str = f"{mc1_time.strftime('%Y-%m-%d')} to {mc1_last.strftime('%Y-%m-%d')}"
                mc2_time_str = f"{mc2_time.strftime('%Y-%m-%d')} to {mc2_last.strftime('%Y-%m-%d')}"
        except Exception:
            mc1_time_str = mc1["time"]
            mc2_time_str = mc2["time"]
        
        results.append({
            "Instrument": instrument,
            "MC1_Time": mc1_time_str,
            "MC1_O": f"{float(mc1['open']):.5f}",
            "MC1_H": f"{mc1['high']:.5f}",
            "MC1_L": f"{mc1['low']:.5f}",
            "MC1_C": f"{float(mc1['close']):.5f}",
            "MC2_Time": mc2_time_str,
            "MC2_O": f"{float(mc2['open']):.5f}",
            "MC2_H": f"{mc2['high']:.5f}",
            "MC2_L": f"{mc2['low']:.5f}",
            "MC2_C": f"{float(mc2['close']):.5f}",
            "Relation": relation,
            "Color": color
        })
    
    return results

def analyze_all_currencies(timeframe: str, ignore_candles: int = 1) -> Dict:
    """
    Analyze all currencies across all instruments for the given timeframe.
    Returns pattern-based groupings of currency pairs (instruments).
    
    Args:
        timeframe: Timeframe like "4D", "3D", "2D", "D", "2W", "W", "2M", or "M"
        ignore_candles: Number of candles to ignore at the end (default: 1)
    
    Returns:
        Dictionary with pattern keys and lists of instruments showing those patterns
    """
    # Parse timeframe
    granularity, n_candles = parse_timeframe(timeframe)
    
    print(f"🔍 Analyzing ALL currencies ({len(INSTRUMENTS)} instruments)")
    print(f"📊 Timeframe: {timeframe} (merging {n_candles} {'daily' if granularity=='D' else ('weekly' if granularity=='W' else 'monthly')} candles)")
    print(f"⏭️  Ignoring last {ignore_candles} candle(s)")
    print()
    
    # Track instruments (pairs) by pattern
    pattern_instruments = defaultdict(set)
    
    for instrument in INSTRUMENTS:
        # Fetch candles based on granularity
        request_count = 30 if granularity == "D" else (120 if granularity == "W" else 240)
        candles = fetch_candles_raw(instrument, granularity=granularity, count=request_count)
        
        if len(candles) < (n_candles * 2) + ignore_candles:
            continue
        
        # Parse currency pairs
        if "_" not in instrument:
            continue
        
        # Ignore the last N candles
        candles_to_process = candles[:-ignore_candles] if ignore_candles > 0 else candles
        
        # Get merged candles
        mc2_candles = candles_to_process[-n_candles:]
        mc1_candles = candles_to_process[-(n_candles * 2):-n_candles]
        
        mc1 = merge_candles(mc1_candles)
        mc2 = merge_candles(mc2_candles)
        
        if not mc1 or not mc2:
            continue
        
        # Analyze relationship
        relation = analyze_candle_relation(mc1, mc2)
        
        # Determine color
        mc2_close = float(mc2["close"])
        mc2_open = float(mc2["open"])
        is_bullish = mc2_close > mc2_open
        is_bearish = mc2_close < mc2_open
        
        # Build pattern strings
        has_upclose = "upclose ⬆️" in relation
        has_downclose = "downclose ⬇️" in relation
        has_bullish_engulfing = "bullish engulfing" in relation
        has_bearish_engulfing = "bearish engulfing" in relation
        
        # Convert instrument name from GBP_AUD to GBPAUD format
        instrument_name = instrument.replace("_", "")
        
        # Track patterns for the instrument
        if has_bullish_engulfing:
            if has_upclose:
                pattern_instruments["Bullish engulfing + upclose"].add(instrument_name)
            else:
                pattern_instruments["Bullish engulfing"].add(instrument_name)
        
        if has_bearish_engulfing:
            if has_downclose:
                pattern_instruments["Bearish engulfing + downclose"].add(instrument_name)
            else:
                pattern_instruments["Bearish engulfing"].add(instrument_name)
        
        # Standalone bullish/bearish with upclose/downclose (without engulfing)
        if has_upclose and not has_bullish_engulfing and not has_bearish_engulfing:
            if is_bullish:
                pattern_instruments["Bullish + upclose"].add(instrument_name)
            else:
                pattern_instruments["Upclose"].add(instrument_name)
        
        if has_downclose and not has_bullish_engulfing and not has_bearish_engulfing:
            if is_bearish:
                pattern_instruments["Bearish + downclose"].add(instrument_name)
            else:
                pattern_instruments["Downclose"].add(instrument_name)
    
    # Convert sets to sorted lists
    result = {}
    for pattern, instruments in pattern_instruments.items():
        result[pattern] = sorted(instruments)
    
    return result

def save_json_output(data: Dict, output_dir: str, filename: str) -> None:
    """
    Save data to a JSON file in the specified directory.
    
    Args:
        data: Dictionary to save as JSON
        output_dir: Directory path where JSON file should be saved
        filename: Name of the JSON file (without .json extension)
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Construct full file path
        filepath = os.path.join(output_dir, f"{filename}.json")
        
        # Write JSON file with pretty formatting
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 JSON output saved to: {filepath}")
    except Exception as e:
        print(f"\n⚠️  Warning: Failed to save JSON output: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Candle Analysis Tool - Analyze merged daily, weekly, or monthly candles for specific or all currencies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --currency GBP --tf 4D                        # Analyze GBP pairs using 4-day merged daily candles
  %(prog)s --currency EUR --tf 2D                        # Analyze EUR pairs using 2-day merged daily candles
  %(prog)s --currency USD --tf D                         # Analyze USD pairs using single daily candle
  %(prog)s --currency USD --tf W                         # Analyze USD pairs using single weekly candle
  %(prog)s --currency GBP --tf 3W                        # Analyze GBP pairs using 3-week merged weekly candles
  %(prog)s --currency EUR --tf M                         # Analyze EUR pairs using single monthly candle
  %(prog)s --currency JPY --tf 2M                        # Analyze JPY pairs using 2-month merged monthly candles
  %(prog)s --all --tf 4D                                # Show all currencies strength summary (daily)
  %(prog)s --all --tf 2W                                # Show all currencies strength summary (weekly)
  %(prog)s --all --tf M                                 # Show all currencies strength summary (monthly)
  %(prog)s --currency GBP --tf 4D --ignore-candles 2     # Ignore last 2 candles (default is 1)
  %(prog)s --currency GBP --tf 4D --json-output ./output # Save JSON output to ./output directory
  %(prog)s --all --tf 4D --json-output ./results        # Save JSON output for all currencies analysis
        """
    )
    
    parser.add_argument(
        "--currency", "-c",
        required=False,
        help="Currency code (e.g., GBP, EUR, USD)"
    )
    
    parser.add_argument(
        "--tf", "--timeframe",
        required=True,
        help="Timeframe: D/W/M for single, or ND/NW/NM for merged (e.g., 2D, 3W, 2M)."
    )
    
    parser.add_argument(
        "--all-currencies", "--all",
        action="store_true",
        help="Show analysis for all currencies in a summary table (ignores --currency)"
    )
    
    parser.add_argument(
        "--ignore-candles",
        type=int,
        default=1,
        help="Number of candles to ignore at the end (default: 1)"
    )
    
    parser.add_argument(
        "--json-output", "--json-dir",
        type=str,
        default=None,
        help="Directory path to save JSON output files (optional). JSON output is in addition to console output."
    )
    
    parser.add_argument(
        "--timestamp",
        type=str,
        default=None,
        help="Timestamp string to use for JSON filename (format: YYYYMMDD_HHMMSS). If not provided, current time will be used."
    )
    
    args = parser.parse_args()
    
    timeframe = args.tf
    ignore_candles = args.ignore_candles
    
    print("🚀 Candle Analysis Tool")
    print("=" * 100)
    
    # Handle all-currencies case
    if args.all_currencies:
        pattern_results = analyze_all_currencies(timeframe, ignore_candles)
        
        # Display results in list format
        print(f"\n📊 Currency Patterns Summary ({timeframe} timeframe):")
        print("=" * 100)
        
        # Define pattern order for display
        pattern_order = [
            "Bullish engulfing + upclose",
            "Bullish engulfing",
            "Bullish + upclose",
            "Bearish engulfing + downclose",
            "Bearish engulfing",
            "Bearish + downclose",
            "Upclose",
            "Downclose"
        ]
        
        # Display patterns in order
        for pattern in pattern_order:
            if pattern in pattern_results and pattern_results[pattern]:
                currencies_str = ", ".join(pattern_results[pattern])
                print(f"{pattern}: {currencies_str}")
        
        # Display any other patterns not in the standard list
        for pattern, currencies in sorted(pattern_results.items()):
            if pattern not in pattern_order and currencies:
                currencies_str = ", ".join(currencies)
                print(f"{pattern}: {currencies_str}")
        
        # Save JSON output if requested
        if args.json_output:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"all_currencies_{timeframe}_{timestamp}"
            json_data = {
                "timeframe": timeframe,
                "ignore_candles": ignore_candles,
                "timestamp": datetime.datetime.now().isoformat(),
                "patterns": pattern_results
            }
            save_json_output(json_data, args.json_output, filename)
        
        return
    
    # Handle single currency case
    if not args.currency:
        parser.error("--currency is required (or use --all-currencies)")
    
    currency = args.currency.upper()
    
    # Analyze candles
    results = analyze_candles_for_currency(currency, timeframe, ignore_candles)
    
    if not results:
        print("❌ No results to display")
        return
    
    # Filter out errors for summary
    valid_results = [r for r in results if "Error" not in r]
    error_results = [r for r in results if "Error" in r]
    
    if error_results:
        print(f"\n⚠️  {len(error_results)} instrument(s) had errors:")
        for r in error_results:
            print(f"   {r['Instrument']}: {r['Error']}")
        print()
    
    if not valid_results:
        print("❌ No valid results to display")
        return
    
    # Display results table
    print(f"\n📊 Analysis Results for {currency} ({timeframe} timeframe):")
    print("=" * 100)
    
    # Prepare table data
    table_headers = [
        "Instrument", "MC1_Time", "MC1_O", "MC1_H", "MC1_L", "MC1_C",
        "MC2_Time", "MC2_O", "MC2_H", "MC2_L", "MC2_C", "Relation", "Color"
    ]
    
    table_data = []
    for r in sorted(valid_results, key=lambda x: x["Instrument"]):
        table_data.append([r.get(h, "-") for h in table_headers])
    
    print(tabulate(table_data, headers=table_headers, tablefmt="grid"))
    
    # Summary statistics
    print(f"\n📈 Summary Statistics:")
    print(f"   Total Instruments: {len(valid_results)}")
    
    relation_counts = {}
    relation_to_instruments = defaultdict(list)
    for r in valid_results:
        relation = r.get("Relation", "unknown")
        instrument = r.get("Instrument", "-")
        relation_counts[relation] = relation_counts.get(relation, 0) + 1
        relation_to_instruments[relation].append(instrument)

    for relation, count in sorted(relation_counts.items(), key=lambda x: -x[1]):
        instruments_str = ", ".join(sorted(relation_to_instruments.get(relation, [])))
        print(f"summary:   {relation}: {count}  [{instruments_str}]")

    # Highlight conditions: if there are 3 or more engulfing cases, surface an alert line
    be_count = relation_counts.get("bearish engulfing", 0)
    bu_count = relation_counts.get("bullish engulfing", 0)
    if be_count >= 3:
        be_list = ", ".join(sorted(relation_to_instruments.get("bearish engulfing", [])))
        print(f"\n🔥 HIGHLIGHT: {be_count} bearish engulfing detected → [{be_list}]")
    if bu_count >= 3:
        bu_list = ", ".join(sorted(relation_to_instruments.get("bullish engulfing", [])))
        print(f"\n🔥 HIGHLIGHT: {bu_count} bullish engulfing detected → [{bu_list}]")
    
    # Save JSON output if requested
    if args.json_output:
        # Use provided timestamp or generate a new one
        if args.timestamp:
            timestamp = args.timestamp
        else:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{currency}_{timeframe}_{timestamp}"
        json_data = {
            "currency": currency,
            "timeframe": timeframe,
            "ignore_candles": ignore_candles,
            "timestamp": datetime.datetime.now().isoformat(),
            "total_instruments": len(valid_results),
            "results": valid_results,
            "errors": error_results,
            "summary": {
                "relation_counts": relation_counts,
                "relation_to_instruments": dict(relation_to_instruments)
            },
            "highlights": {
                "bearish_engulfing_count": be_count,
                "bullish_engulfing_count": bu_count,
                "bearish_engulfing_instruments": sorted(relation_to_instruments.get("bearish engulfing", [])),
                "bullish_engulfing_instruments": sorted(relation_to_instruments.get("bullish engulfing", []))
            }
        }
        save_json_output(json_data, args.json_output, filename)

if __name__ == "__main__":
    main()

