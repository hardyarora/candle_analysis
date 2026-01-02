#!/usr/bin/env python3
"""
Interactive script to add feedback for engulfing candle patterns.

Prompts user for currency, timeframe, rating, and optional fields,
then analyzes the pattern and stores the feedback.

Usage:
    python3 scripts/add_feedback.py
    python3 scripts/add_feedback.py GBP_NZD 1D 5
    python3 scripts/add_feedback.py GBP_NZD 1D 5 --date 2025-12-30
    python3 scripts/add_feedback.py GBP_NZD 1D 5 --date 2025-12-30 --pattern-type bearish --notes "Good pattern"
"""
import sys
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.candle_analyzer import fetch_candles_raw, merge_candles, analyze_candle_relation
from src.core.engulfing_metrics import calculate_engulfing_metrics
from src.core.engulfing_feedback import store_feedback
from src.core.config import INSTRUMENTS, DEFAULT_CANDLE_COUNT_DAILY
from src.utils.timeframe import normalize_timeframe, parse_timeframe

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("add_feedback")


def prompt_input(prompt: str, default: Optional[str] = None, validator=None) -> str:
    """
    Prompt user for input with optional default and validation.
    
    Args:
        prompt: Prompt message
        default: Optional default value
        validator: Optional validation function that returns (is_valid, error_message)
        
    Returns:
        User input string
    """
    if default:
        full_prompt = f"{prompt} [{default}]: "
    else:
        full_prompt = f"{prompt}: "
    
    while True:
        value = input(full_prompt).strip()
        if not value and default:
            value = default
        if not value:
            print("This field is required. Please enter a value.")
            continue
        
        if validator:
            is_valid, error_msg = validator(value)
            if not is_valid:
                print(f"Invalid input: {error_msg}")
                continue
        
        return value


def validate_currency(currency: str) -> tuple[bool, str]:
    """Validate currency pair format."""
    if "_" not in currency:
        return False, "Currency must be in format CURR1_CURR2 (e.g., GBP_USD)"
    
    parts = currency.split("_")
    if len(parts) != 2:
        return False, "Currency must be in format CURR1_CURR2 (e.g., GBP_USD)"
    
    if currency not in INSTRUMENTS:
        print(f"Warning: {currency} not in standard instrument list, but continuing...")
    
    return True, ""


def validate_timeframe(timeframe: str) -> tuple[bool, str]:
    """Validate timeframe format."""
    try:
        normalize_timeframe(timeframe)
        return True, ""
    except ValueError as e:
        return False, str(e)


def validate_rating(rating: str) -> tuple[bool, str]:
    """Validate rating (1-10)."""
    try:
        rating_int = int(rating)
        if 1 <= rating_int <= 10:
            return True, ""
        else:
            return False, "Rating must be between 1 and 10"
    except ValueError:
        return False, "Rating must be a number between 1 and 10"


def validate_date(date_str: str) -> tuple[bool, str]:
    """Validate date format YYYY-MM-DD."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True, ""
    except ValueError:
        return False, "Date must be in YYYY-MM-DD format"


def validate_pattern_type(pattern_type: str) -> tuple[bool, str]:
    """Validate pattern type."""
    if pattern_type.lower() in ["bullish", "bearish"]:
        return True, ""
    return False, "Pattern type must be 'bullish' or 'bearish'"


def find_candles_for_date(
    candles: list[dict],
    target_date: str,
    n_candles: int
) -> Optional[tuple[dict, dict]]:
    """
    Find mc1 and mc2 candles for a specific date.
    
    Args:
        candles: List of candle dictionaries
        target_date: Target date in YYYY-MM-DD format
        n_candles: Number of candles to merge
        
    Returns:
        Tuple of (mc1, mc2) dictionaries or None if not found
    """
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    
    # Find the candle that contains or is closest to the target date
    best_match_idx = None
    min_diff = None
    
    for i in range(n_candles * 2, len(candles)):
        # Get candle windows
        mc2_candles = candles[i - n_candles:i]
        mc2 = merge_candles(mc2_candles)
        
        if not mc2:
            continue
        
        # Parse mc2 time
        try:
            mc2_time = mc2.get("time", "")
            mc2_dt = datetime.fromisoformat(mc2_time.replace("Z", "").replace(".000000000", ""))
            mc2_date_str = mc2_dt.strftime("%Y-%m-%d")
            
            # Check if this candle's date matches
            if mc2_date_str == target_date:
                mc1_candles = candles[i - (n_candles * 2):i - n_candles]
                mc1 = merge_candles(mc1_candles)
                if mc1:
                    return (mc1, mc2)
            
            # Track closest match
            diff = abs((mc2_dt - target_dt).days)
            if min_diff is None or diff < min_diff:
                min_diff = diff
                best_match_idx = i
        except Exception:
            continue
    
    # If exact match not found, use closest match
    if best_match_idx is not None:
        mc2_candles = candles[best_match_idx - n_candles:best_match_idx]
        mc1_candles = candles[best_match_idx - (n_candles * 2):best_match_idx - n_candles]
        mc1 = merge_candles(mc1_candles)
        mc2 = merge_candles(mc2_candles)
        if mc1 and mc2:
            print(f"Note: Using closest match to {target_date} (difference: {min_diff} days)")
            return (mc1, mc2)
    
    return None


def get_latest_pattern(
    candles: list[dict],
    n_candles: int,
    ignore_candles: int = 1
) -> Optional[tuple[dict, dict]]:
    """
    Get the latest engulfing pattern from candles.
    
    Args:
        candles: List of candle dictionaries
        n_candles: Number of candles to merge
        ignore_candles: Number of candles to ignore at the end
        
    Returns:
        Tuple of (mc1, mc2) dictionaries or None if not found
    """
    if len(candles) < (n_candles * 2) + ignore_candles:
        return None
    
    candles_to_process = candles[:-ignore_candles] if ignore_candles > 0 else candles
    
    # Get latest merged candles
    mc2_candles = candles_to_process[-n_candles:]
    mc1_candles = candles_to_process[-(n_candles * 2):-n_candles]
    
    mc1 = merge_candles(mc1_candles)
    mc2 = merge_candles(mc2_candles)
    
    if not mc1 or not mc2:
        return None
    
    return (mc1, mc2)


def format_candle_for_storage(candle: dict) -> dict:
    """
    Format candle dictionary for storage in feedback.
    
    Args:
        candle: Candle dictionary from merge_candles
        
    Returns:
        Formatted candle dictionary
    """
    # Parse time to get date range
    try:
        candle_time = candle.get("time", "")
        candle_dt = datetime.fromisoformat(candle_time.replace("Z", "").replace(".000000000", ""))
        time_str = candle_dt.strftime("%Y-%m-%d")
    except Exception:
        time_str = candle.get("time", "")
    
    return {
        "time": time_str,
        "open": float(candle.get("open", 0)),
        "high": float(candle.get("high", 0)),
        "low": float(candle.get("low", 0)),
        "close": float(candle.get("close", 0))
    }


def main():
    """Main interactive feedback entry function."""
    parser = argparse.ArgumentParser(
        description="Add feedback for engulfing candle patterns",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Interactive mode
  %(prog)s GBP_NZD 1D 5                       # Quick entry with currency, timeframe, rating
  %(prog)s GBP_NZD 1D 5 --date 2025-12-30     # With specific date
  %(prog)s GBP_NZD 1D 5 --pattern-type bearish --notes "Good pattern"
        """
    )
    
    parser.add_argument(
        "currency",
        nargs="?",
        help="Currency pair (e.g., GBP_NZD, NZD_CHF)"
    )
    parser.add_argument(
        "timeframe",
        nargs="?",
        help="Timeframe (1D, 2D, 3D, or 4D)"
    )
    parser.add_argument(
        "rating",
        nargs="?",
        type=int,
        help="Rating (1-10)"
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Date in YYYY-MM-DD format (default: latest pattern)"
    )
    parser.add_argument(
        "--pattern-type",
        choices=["bullish", "bearish"],
        help="Pattern type (default: auto-detect)"
    )
    parser.add_argument(
        "--notes",
        type=str,
        help="Optional notes"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Engulfing Pattern Feedback Entry")
    print("=" * 60)
    print()
    
    # Get required fields from args or prompt
    if args.currency:
        currency = args.currency
        is_valid, error_msg = validate_currency(currency)
        if not is_valid:
            print(f"Error: {error_msg}")
            return 1
    else:
        currency = prompt_input(
            "Currency pair (e.g., GBP_USD, NZD_CHF)",
            validator=validate_currency
        )
    
    if args.timeframe:
        timeframe = args.timeframe
        is_valid, error_msg = validate_timeframe(timeframe)
        if not is_valid:
            print(f"Error: {error_msg}")
            return 1
    else:
        timeframe = prompt_input(
            "Timeframe (1D, 2D, 3D, or 4D)",
            validator=validate_timeframe
        )
    
    if args.rating is not None:
        rating_int = args.rating
        if not (1 <= rating_int <= 10):
            print("Error: Rating must be between 1 and 10")
            return 1
    else:
        rating = prompt_input(
            "Rating (1-10)",
            validator=validate_rating
        )
        rating_int = int(rating)
    
    # Optional fields
    if args.date or args.pattern_type or args.notes:
        # Non-interactive mode - use provided args or defaults
        date_input = args.date or ""
        pattern_type_input = args.pattern_type or ""
        notes = args.notes or ""
    else:
        # Interactive mode - prompt for optional fields
        print()
        print("Optional fields (press Enter to skip):")
        
        def validate_date_optional(value: str) -> tuple[bool, str]:
            """Validate date, allowing empty string."""
            if not value:
                return True, ""
            return validate_date(value)
        
        date_input = prompt_input(
            "Date (YYYY-MM-DD) - leave empty for latest pattern",
            default="",
            validator=validate_date_optional
        )
        
        def validate_pattern_type_optional(value: str) -> tuple[bool, str]:
            """Validate pattern type, allowing empty string."""
            if not value:
                return True, ""
            return validate_pattern_type(value)
        
        pattern_type_input = prompt_input(
            "Pattern type (bullish/bearish) - leave empty to auto-detect",
            default="",
            validator=validate_pattern_type_optional
        )
        
        notes = prompt_input("Notes (optional)", default="")
    
    # Normalize timeframe
    normalized_tf = normalize_timeframe(timeframe)
    granularity, n_candles = parse_timeframe(normalized_tf)
    
    print()
    print("Fetching candles and analyzing pattern...")
    
    # Fetch candles
    candles = fetch_candles_raw(
        currency,
        granularity=granularity,
        count=DEFAULT_CANDLE_COUNT_DAILY,
        force_oanda=False
    )
    
    if len(candles) < (n_candles * 2):
        print(f"Error: Not enough candles. Need at least {n_candles * 2}, got {len(candles)}")
        return 1
    
    # Get mc1 and mc2
    if date_input:
        mc1, mc2 = find_candles_for_date(candles, date_input, n_candles)
        if not mc1 or not mc2:
            print(f"Error: Could not find candles for date {date_input}")
            return 1
        target_date = date_input
    else:
        result = get_latest_pattern(candles, n_candles, ignore_candles=1)
        if not result:
            print("Error: Could not find latest pattern")
            return 1
        mc1, mc2 = result
        
        # Get date from mc2
        try:
            mc2_time = mc2.get("time", "")
            mc2_dt = datetime.fromisoformat(mc2_time.replace("Z", "").replace(".000000000", ""))
            target_date = mc2_dt.strftime("%Y-%m-%d")
        except Exception:
            print("Error: Could not extract date from candle")
            return 1
    
    # Analyze pattern
    relation = analyze_candle_relation(mc1, mc2)
    has_bullish_engulfing = "bullish engulfing" in relation
    has_bearish_engulfing = "bearish engulfing" in relation
    
    # Determine pattern type
    if pattern_type_input:
        pattern_type: Literal["bullish", "bearish"] = pattern_type_input.lower()  # type: ignore
    elif has_bullish_engulfing:
        pattern_type = "bullish"
    elif has_bearish_engulfing:
        pattern_type = "bearish"
    else:
        # Determine from candle colors
        mc2_close = float(mc2.get("close", 0))
        mc2_open = float(mc2.get("open", 0))
        if mc2_close > mc2_open:
            pattern_type = "bullish"
        else:
            pattern_type = "bearish"
        print(f"Auto-detected pattern type: {pattern_type}")
    
    # Verify it's an engulfing pattern
    if not has_bullish_engulfing and not has_bearish_engulfing:
        print(f"Warning: No engulfing pattern detected. Relation: {relation}")
        confirm = input("Continue anyway? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Cancelled.")
            return 0
    
    # Calculate metrics
    print("Calculating metrics...")
    metrics = calculate_engulfing_metrics(mc1, mc2, pattern_type)
    
    # Format candles for storage
    candles_data = {
        "mc1": format_candle_for_storage(mc1),
        "mc2": format_candle_for_storage(mc2)
    }
    
    # Display summary
    print()
    print("=" * 60)
    print("Feedback Summary")
    print("=" * 60)
    print(f"Instrument: {currency}")
    print(f"Timeframe: {normalized_tf}")
    print(f"Date: {target_date}")
    print(f"Pattern Type: {pattern_type}")
    print(f"Rating: {rating_int}/10")
    print(f"Relation: {relation}")
    print(f"Body Size Ratio: {metrics['body_size_ratio']:.4f}")
    print(f"Body Position: {metrics['body_position']}")
    print(f"Body Overlap: {metrics['body_overlap_percentage']:.2f}%")
    if notes:
        print(f"Notes: {notes}")
    print()
    
    # Confirm
    confirm = input("Store this feedback? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return 0
    
    # Store feedback
    try:
        filepath = store_feedback(
            instrument=currency,
            timeframe=normalized_tf,
            date=target_date,
            pattern_type=pattern_type,
            rating=rating_int,
            metrics=metrics,
            candles=candles_data,
            notes=notes if notes else None,
            context={}
        )
        print()
        print(f"✓ Feedback stored successfully: {filepath}")
        return 0
    except Exception as e:
        print(f"Error storing feedback: {e}")
        logger.exception("Failed to store feedback")
        return 1


if __name__ == "__main__":
    sys.exit(main())

