#!/usr/bin/env python3
"""
Display detailed feedback information including candle high/low details
and verification of calculations.
"""
import json
import sys
from pathlib import Path
from typing import Dict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.engulfing_metrics import (
    calculate_body_size,
    calculate_body_ratio,
    calculate_body_position,
    calculate_body_overlap,
    calculate_wick_ratios
)


def verify_calculations(mc1: Dict, mc2: Dict, pattern_type: str, stored_metrics: Dict) -> Dict:
    """Verify all calculations match stored metrics."""
    # Calculate body sizes
    mc1_body_size = calculate_body_size(mc1)
    mc2_body_size = calculate_body_size(mc2)
    
    # Calculate body ratio
    body_size_ratio = calculate_body_ratio(mc1_body_size, mc2_body_size)
    
    # Calculate position
    mc2_body_top = max(float(mc2.get("open", 0)), float(mc2.get("close", 0)))
    mc2_body_bottom = min(float(mc2.get("open", 0)), float(mc2.get("close", 0)))
    mc1_open = float(mc1.get("open", 0))
    
    body_position = calculate_body_position(
        mc1_open,
        mc2_body_top,
        mc2_body_bottom,
        pattern_type
    )
    
    # Calculate overlap
    body_overlap_percentage = calculate_body_overlap(mc1, mc2)
    
    # Calculate wick ratios
    mc1_wick_ratios = calculate_wick_ratios(mc1)
    mc2_wick_ratios = calculate_wick_ratios(mc2)
    
    # Verify engulfing pattern
    mc1_open = float(mc1.get("open", 0))
    mc1_close = float(mc1.get("close", 0))
    mc2_open = float(mc2.get("open", 0))
    mc2_close = float(mc2.get("close", 0))
    
    if pattern_type == "bearish":
        is_valid = mc2_open > mc1_close and mc2_close < mc1_open
    else:  # bullish
        is_valid = mc2_open < mc1_close and mc2_close > mc1_open
    
    return {
        "calculated": {
            "body_size_ratio": body_size_ratio,
            "body_position": body_position,
            "body_overlap_percentage": body_overlap_percentage,
            "mc1_wick_ratios": mc1_wick_ratios,
            "mc2_wick_ratios": mc2_wick_ratios,
            "mc1_body_size": mc1_body_size,
            "mc2_body_size": mc2_body_size
        },
        "stored": stored_metrics,
        "is_valid_engulfing": is_valid,
        "engulfing_check": {
            "mc1_open": mc1_open,
            "mc1_close": mc1_close,
            "mc2_open": mc2_open,
            "mc2_close": mc2_close,
            "pattern_type": pattern_type
        }
    }


def display_feedback_details(feedback_file: Path):
    """Display detailed feedback information."""
    with open(feedback_file, 'r', encoding='utf-8') as f:
        feedback = json.load(f)
    
    instrument = feedback.get("instrument", "N/A")
    timeframe = feedback.get("timeframe", "N/A")
    date = feedback.get("date", "N/A")
    pattern_type = feedback.get("pattern_type", "N/A")
    rating = feedback.get("rating", "N/A")
    notes = feedback.get("notes", "")
    timestamp = feedback.get("timestamp", "N/A")
    
    mc1 = feedback.get("candles", {}).get("mc1", {})
    mc2 = feedback.get("candles", {}).get("mc2", {})
    metrics = feedback.get("metrics", {})
    
    print("=" * 80)
    print(f"Feedback data for {instrument} ({timeframe}, {pattern_type.capitalize()} Engulfing)")
    print("=" * 80)
    print(f"File location: {feedback_file}")
    print()
    print("Feedback details:")
    print(f"  Instrument: {instrument}")
    print(f"  Timeframe: {timeframe}")
    print(f"  Date: {date}")
    print(f"  Pattern Type: {pattern_type.capitalize()}")
    print(f"  Rating: {rating}/10")
    if notes:
        print(f"  Notes: {notes}")
    print(f"  Timestamp: {timestamp}")
    print()
    
    # Display candle details with high/low
    print("Candle Details:")
    print("-" * 80)
    
    print("\nMC1 (Previous Candle):")
    mc1_open = float(mc1.get("open", 0))
    mc1_high = float(mc1.get("high", 0))
    mc1_low = float(mc1.get("low", 0))
    mc1_close = float(mc1.get("close", 0))
    mc1_time = mc1.get("time", "N/A")
    
    print(f"  Time: {mc1_time}")
    print(f"  Open:  {mc1_open:.5f}")
    print(f"  High:  {mc1_high:.5f}")
    print(f"  Low:   {mc1_low:.5f}")
    print(f"  Close: {mc1_close:.5f}")
    
    mc1_body_top = max(mc1_open, mc1_close)
    mc1_body_bottom = min(mc1_open, mc1_close)
    mc1_body_size = abs(mc1_close - mc1_open)
    mc1_upper_wick = mc1_high - mc1_body_top
    mc1_lower_wick = mc1_body_bottom - mc1_low
    mc1_total_range = mc1_high - mc1_low
    
    print(f"  Body Range: {mc1_body_bottom:.5f} to {mc1_body_top:.5f} (size: {mc1_body_size:.5f})")
    print(f"  Upper Wick: {mc1_upper_wick:.5f}")
    print(f"  Lower Wick: {mc1_lower_wick:.5f}")
    print(f"  Total Range: {mc1_total_range:.5f}")
    print(f"  Candle Type: {'Bullish' if mc1_close > mc1_open else 'Bearish' if mc1_close < mc1_open else 'Doji'}")
    
    print("\nMC2 (New Candle):")
    mc2_open = float(mc2.get("open", 0))
    mc2_high = float(mc2.get("high", 0))
    mc2_low = float(mc2.get("low", 0))
    mc2_close = float(mc2.get("close", 0))
    mc2_time = mc2.get("time", "N/A")
    
    print(f"  Time: {mc2_time}")
    print(f"  Open:  {mc2_open:.5f}")
    print(f"  High:  {mc2_high:.5f}")
    print(f"  Low:   {mc2_low:.5f}")
    print(f"  Close: {mc2_close:.5f}")
    
    mc2_body_top = max(mc2_open, mc2_close)
    mc2_body_bottom = min(mc2_open, mc2_close)
    mc2_body_size = abs(mc2_close - mc2_open)
    mc2_upper_wick = mc2_high - mc2_body_top
    mc2_lower_wick = mc2_body_bottom - mc2_low
    mc2_total_range = mc2_high - mc2_low
    
    print(f"  Body Range: {mc2_body_bottom:.5f} to {mc2_body_top:.5f} (size: {mc2_body_size:.5f})")
    print(f"  Upper Wick: {mc2_upper_wick:.5f}")
    print(f"  Lower Wick: {mc2_lower_wick:.5f}")
    print(f"  Total Range: {mc2_total_range:.5f}")
    print(f"  Candle Type: {'Bullish' if mc2_close > mc2_open else 'Bearish' if mc2_close < mc2_open else 'Doji'}")
    
    # Engulfing pattern validation
    print("\n" + "-" * 80)
    print("Engulfing Pattern Validation:")
    if pattern_type == "bearish":
        condition1 = mc2_open > mc1_close
        condition2 = mc2_close < mc1_open
        print(f"  For bearish engulfing:")
        print(f"    MC2 open ({mc2_open:.5f}) > MC1 close ({mc1_close:.5f}): {condition1} {'✓' if condition1 else '✗'}")
        print(f"    MC2 close ({mc2_close:.5f}) < MC1 open ({mc1_open:.5f}): {condition2} {'✓' if condition2 else '✗'}")
        is_valid = condition1 and condition2
    else:  # bullish
        condition1 = mc2_open < mc1_close
        condition2 = mc2_close > mc1_open
        print(f"  For bullish engulfing:")
        print(f"    MC2 open ({mc2_open:.5f}) < MC1 close ({mc1_close:.5f}): {condition1} {'✓' if condition1 else '✗'}")
        print(f"    MC2 close ({mc2_close:.5f}) > MC1 open ({mc1_open:.5f}): {condition2} {'✓' if condition2 else '✗'}")
        is_valid = condition1 and condition2
    
    print(f"  Valid Engulfing Pattern: {is_valid} {'✓' if is_valid else '✗ WARNING: This may not be a valid engulfing pattern!'}")
    
    # Verify calculations
    print("\n" + "-" * 80)
    print("Calculated metrics:")
    verification = verify_calculations(mc1, mc2, pattern_type, metrics)
    
    print("\nBody metrics:")
    stored_ratio = metrics.get("body_size_ratio", 0)
    calc_ratio = verification["calculated"]["body_size_ratio"]
    print(f"  Body Size Ratio: {calc_ratio:.3f} (previous candle body is {calc_ratio*100:.1f}% of new candle body)")
    if abs(stored_ratio - calc_ratio) > 0.0001:
        print(f"    ⚠️  Stored value: {stored_ratio:.3f} (mismatch!)")
    
    stored_position = metrics.get("body_position", "")
    calc_position = verification["calculated"]["body_position"]
    print(f"  Body Position: {calc_position} (previous candle open is in the {calc_position} of new candle body)")
    if stored_position != calc_position:
        print(f"    ⚠️  Stored value: {stored_position} (mismatch!)")
    
    # Show position details
    position_from_bottom = mc1_open - mc2_body_bottom
    body_range = mc2_body_top - mc2_body_bottom
    position_percentage = (position_from_bottom / body_range) * 100 if body_range > 0 else 0
    print(f"    Position Details: MC1 open ({mc1_open:.5f}) is {position_percentage:.2f}% from bottom of MC2 body")
    print(f"    MC2 Body Range: {mc2_body_bottom:.5f} to {mc2_body_top:.5f}")
    
    stored_overlap = metrics.get("body_overlap_percentage", 0)
    calc_overlap = verification["calculated"]["body_overlap_percentage"]
    print(f"  Body Overlap: {calc_overlap:.2f}% ({calc_overlap:.2f}% of previous candle body overlaps with new candle body)")
    if abs(stored_overlap - calc_overlap) > 0.01:
        print(f"    ⚠️  Stored value: {stored_overlap:.2f}% (mismatch!)")
    
    # Show overlap details
    overlap_top = min(mc1_body_top, mc2_body_top)
    overlap_bottom = max(mc1_body_bottom, mc2_body_bottom)
    overlap_size = overlap_top - overlap_bottom if overlap_top > overlap_bottom else 0
    print(f"    Overlap Details: Range {overlap_bottom:.5f} to {overlap_top:.5f} (size: {overlap_size:.5f})")
    print(f"    MC1 Body Range: {mc1_body_bottom:.5f} to {mc1_body_top:.5f}")
    print(f"    MC2 Body Range: {mc2_body_bottom:.5f} to {mc2_body_top:.5f}")
    
    print("\nWick ratios:")
    mc1_wick = verification["calculated"]["mc1_wick_ratios"]
    print(f"  MC1 (Previous Candle):")
    print(f"    Upper wick ratio: {mc1_wick['upper_wick_ratio']:.3f}")
    print(f"    Lower wick ratio: {mc1_wick['lower_wick_ratio']:.3f}")
    
    mc2_wick = verification["calculated"]["mc2_wick_ratios"]
    print(f"  MC2 (New Candle):")
    print(f"    Upper wick ratio: {mc2_wick['upper_wick_ratio']:.3f}")
    print(f"    Lower wick ratio: {mc2_wick['lower_wick_ratio']:.3f}")
    
    print("\nBody sizes:")
    calc_mc1_body = verification["calculated"]["mc1_body_size"]
    calc_mc2_body = verification["calculated"]["mc2_body_size"]
    print(f"  MC1 Body Size: {calc_mc1_body:.5f}")
    print(f"  MC2 Body Size: {calc_mc2_body:.5f} (new candle body is ~{calc_mc2_body/calc_mc1_body:.1f}x larger)")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python display_feedback_details.py <feedback_file_path>")
        sys.exit(1)
    
    feedback_file = Path(sys.argv[1])
    if not feedback_file.exists():
        print(f"Error: File not found: {feedback_file}")
        sys.exit(1)
    
    display_feedback_details(feedback_file)




