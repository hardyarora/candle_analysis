"""
Pullback analysis functionality.

Calculates how much each currency pair has pulled back from the previous week's high,
relative to the previous week's candle range (low to high).
"""
import datetime
import logging
from typing import Dict, List, Optional, Tuple

from .config import (
    OANDA_API_URL,
    ACCESS_TOKEN,
    INSTRUMENTS,
    DEFAULT_CANDLE_COUNT_DAILY,
    DEFAULT_CANDLE_COUNT_WEEKLY,
    DEFAULT_CANDLE_COUNT_MONTHLY,
    CURRENCY_FULL_NAMES,
)
from .candle_analyzer import fetch_candles_raw

logger = logging.getLogger("candle_analysis_api")

# Cache for pullback analysis results
# Format: {cache_key: (cached_data, timestamp)}
# Cache key format: (currency_filter, ignore_candles, period)
_pullback_cache: Dict[Tuple[Optional[str], int, str], Tuple[Dict, datetime.datetime]] = {}

# Cache TTL: 12.5 minutes (middle of 10-15 minute range)
CACHE_TTL_MINUTES = 12.5


def _should_exclude_from_currency_calculation(instrument: str, currency: str) -> bool:
    """
    Check whether an instrument should be excluded from strength/weakness calculations
    for a given currency.

    Currently, for USD calculations we exclude metals pairs (XAU_USD, XAG_USD)
    as per business rules. Also handles reversed instrument names (USD_XAU, USD_XAG).

    Args:
        instrument: Instrument name (e.g., "GBP_USD" or "USD_XAU")
        currency: Currency code (e.g., "USD")

    Returns:
        True if the instrument should be excluded, False otherwise.
    """
    normalized_currency = currency.upper()
    normalized_instrument = instrument.upper()

    if normalized_currency == "USD":
        # Check both original and reversed forms
        if normalized_instrument in {"XAU_USD", "XAG_USD", "USD_XAU", "USD_XAG"}:
            return True

    return False


def calculate_currency_strength_weakness(
    currency: str,
    results: List[Dict],
) -> Optional[Dict[str, object]]:
    """
    Calculate strength and weakness metrics for a given currency based on
    pullback analysis results.

    Strength formula (for currency C):
        (pairs where C is base and tested_high = True
         + pairs where C is quote and tested_low = True) / total_pairs

    Weakness formula (for currency C):
        (pairs where C is base and tested_low = True
         + pairs where C is quote and tested_high = True) / total_pairs

    For USD, XAU_USD and XAG_USD are excluded from the calculations entirely.

    Args:
        currency: Currency code (e.g., "JPY", "USD")
        results: List of pullback results as returned by analyze_all_pullbacks()["results"]

    Returns:
        Dictionary with "strength" and "weakness" ratios in range [0.0, 1.0],
        or None if there are no applicable instruments.
    """
    if not currency:
        return None

    target_currency = currency.upper()

    total_pairs = 0
    total_instruments: List[str] = []

    # Strength components
    strength_count = 0
    strength_tested_high_instruments: List[str] = []
    strength_tested_low_instruments: List[str] = []

    # Weakness components
    weakness_count = 0
    weakness_tested_high_instruments: List[str] = []
    weakness_tested_low_instruments: List[str] = []

    for item in results:
        instrument = item.get("instrument")
        if not instrument:
            continue

        if _should_exclude_from_currency_calculation(instrument, target_currency):
            continue

        try:
            base_currency, quote_currency = instrument.split("_")
        except ValueError:
            # Skip malformed instrument names
            continue

        if target_currency not in (base_currency, quote_currency):
            # Not related to the target currency
            continue

        tested_high = bool(item.get("tested_high"))
        tested_low = bool(item.get("tested_low"))

        # Count this pair towards the total for this currency
        total_pairs += 1
        total_instruments.append(instrument)

        # Strength conditions
        if target_currency == base_currency and tested_high:
            strength_count += 1
            strength_tested_high_instruments.append(instrument)
        if target_currency == quote_currency and tested_low:
            strength_count += 1
            strength_tested_low_instruments.append(instrument)

        # Weakness conditions
        if target_currency == base_currency and tested_low:
            weakness_count += 1
            weakness_tested_low_instruments.append(instrument)
        if target_currency == quote_currency and tested_high:
            weakness_count += 1
            weakness_tested_high_instruments.append(instrument)

    if total_pairs == 0:
        return None

    strength_ratio = strength_count / total_pairs
    weakness_ratio = weakness_count / total_pairs

    return {
        "strength": strength_ratio,
        "weakness": weakness_ratio,
        "strength_details": {
            "total_count": total_pairs,
            "total_instruments": total_instruments,
            "tested_high_count": len(strength_tested_high_instruments),
            "tested_high_instruments": strength_tested_high_instruments,
            "tested_low_count": len(strength_tested_low_instruments),
            "tested_low_instruments": strength_tested_low_instruments,
        },
        "weakness_details": {
            "total_count": total_pairs,
            "total_instruments": total_instruments,
            "tested_high_count": len(weakness_tested_high_instruments),
            "tested_high_instruments": weakness_tested_high_instruments,
            "tested_low_count": len(weakness_tested_low_instruments),
            "tested_low_instruments": weakness_tested_low_instruments,
        },
    }


def calculate_all_currencies_strength_weakness(
    results: List[Dict],
) -> Dict[str, Dict[str, object]]:
    """
    Calculate strength/weakness metrics for all currencies present in the
    pullback results.

    This allows the API and CLI to expose strength/weakness information even
    when no specific currency filter is provided.

    Args:
        results: List of pullback results as returned by analyze_all_pullbacks()["results"]

    Returns:
        Dictionary mapping currency code -> stats dictionary with the same
        structure as calculate_currency_strength_weakness.
    """
    # Derive currency universe from config to keep it stable and predictable
    available_currencies = set(CURRENCY_FULL_NAMES.keys())

    all_stats: Dict[str, Dict[str, object]] = {}

    for currency in sorted(available_currencies):
        stats = calculate_currency_strength_weakness(currency, results)
        if stats is not None:
            all_stats[currency] = stats

    return all_stats


def categorize_currencies_strength_weakness(
    all_currencies_strength_weakness: Dict[str, Dict[str, object]],
) -> Dict[str, Dict[str, object]]:
    """
    Categorize currencies based on strength/weakness data from pullback analysis.
    
    This function processes the all_currencies_strength_weakness data and reorganizes
    it to show which instruments tested high/low for each currency, normalized to
    show the currency's perspective (as base currency).
    
    Args:
        all_currencies_strength_weakness: Dictionary from analyze_all_pullbacks()
            containing strength/weakness data for all currencies
    
    Returns:
        Dictionary mapping currency code -> categorized data with:
        - tested_high: List[str] - instruments where currency tested high
        - tested_high_count: int
        - tested_low: List[str] - instruments where currency tested low
        - tested_low_count: int
        - strength: float - strength percentage (0.0-1.0)
        - weakness: float - weakness percentage (0.0-1.0)
    """
    result: Dict[str, Dict[str, object]] = {}
    
    for currency, details in all_currencies_strength_weakness.items():
        # Collect all tested_high and tested_low instruments
        all_tested_high = set()
        all_tested_low = set()
        
        if "strength_details" in details:
            strength_details = details["strength_details"]
            if isinstance(strength_details, dict):
                all_tested_high.update(strength_details.get("tested_high_instruments", []))
                all_tested_low.update(strength_details.get("tested_low_instruments", []))
        
        if "weakness_details" in details:
            weakness_details = details["weakness_details"]
            if isinstance(weakness_details, dict):
                all_tested_high.update(weakness_details.get("tested_high_instruments", []))
                all_tested_low.update(weakness_details.get("tested_low_instruments", []))
        
        # Categorize based on position in pair
        currency_tested_high = []
        currency_tested_low = []
        
        for instrument in all_tested_high:
            try:
                base, quote = instrument.split("_")
                if base == currency:
                    currency_tested_high.append(instrument)
                elif quote == currency:
                    # Reverse the name when quote currency goes to tested_low
                    currency_tested_low.append(f"{quote}_{base}")
            except ValueError:
                # Skip malformed instrument names
                continue
        
        for instrument in all_tested_low:
            try:
                base, quote = instrument.split("_")
                if base == currency:
                    currency_tested_low.append(instrument)
                elif quote == currency:
                    # Reverse the name when quote currency goes to tested_high
                    currency_tested_high.append(f"{quote}_{base}")
            except ValueError:
                # Skip malformed instrument names
                continue
        
        tested_high_list = sorted(set(currency_tested_high))
        tested_low_list = sorted(set(currency_tested_low))
        tested_high_count = len(tested_high_list)
        tested_low_count = len(tested_low_list)
        total = tested_high_count + tested_low_count
        
        result[currency] = {
            "tested_high": tested_high_list,
            "tested_high_count": tested_high_count,
            "tested_low": tested_low_list,
            "tested_low_count": tested_low_count,
            "strength": tested_high_count / total if total > 0 else 0.0,
            "weakness": tested_low_count / total if total > 0 else 0.0,
        }
    
    return result


def reverse_pullback_result(result: Dict, target_currency: str) -> Dict:
    """
    Reverse a pullback result when the target currency is in the quote position.
    
    When reversing a currency pair (e.g., EUR_USD -> USD_EUR), we need to:
    1. Reverse the instrument name
    2. Invert all prices (high becomes low, low becomes high, etc.)
    3. Recalculate pullback percentage with inverted prices
    4. Swap tested_high and tested_low
    
    Args:
        result: Pullback result dictionary from analyze_pullback_for_instrument
        target_currency: Currency code that should be in base position after reversal
        
    Returns:
        Reversed pullback result dictionary
    """
    instrument = result.get("instrument", "")
    try:
        base, quote = instrument.split("_")
    except ValueError:
        # Can't reverse if instrument name is malformed
        return result
    
    # Only reverse if target_currency is in quote position
    if quote.upper() != target_currency.upper():
        return result
    
    # Reverse instrument name
    reversed_instrument = f"{quote}_{base}"
    
    # Invert all prices (when reversing pair, prices are inverted)
    def invert_price(price: float) -> float:
        """Invert a price: 1/price"""
        if price == 0:
            return 0.0
        return 1.0 / price
    
    # Invert previous week candle data
    prev_week = result.get("prev_week", {})
    prev_week_high_orig = prev_week.get("high", 0)
    prev_week_low_orig = prev_week.get("low", 0)
    prev_week_open_orig = prev_week.get("open", 0)
    prev_week_close_orig = prev_week.get("close", 0)
    
    # When reversing: new_high = 1/old_low, new_low = 1/old_high
    prev_week_high_new = invert_price(prev_week_low_orig)
    prev_week_low_new = invert_price(prev_week_high_orig)
    prev_week_open_new = invert_price(prev_week_open_orig)
    prev_week_close_new = invert_price(prev_week_close_orig)
    
    # Invert current price
    current_price_orig = result.get("current_price", 0)
    current_price_new = invert_price(current_price_orig)
    
    # Recalculate pullback percentage with inverted prices
    pullback_pct_new = calculate_pullback_percentage(
        current_price_new, 
        prev_week_high_new, 
        prev_week_low_new
    )
    
    # Swap tested_high and tested_low (perspective is reversed)
    tested_high_orig = result.get("tested_high", False)
    tested_low_orig = result.get("tested_low", False)
    tested_high_new = tested_low_orig
    tested_low_new = tested_high_orig
    
    # Build reversed result
    reversed_result = {
        "instrument": reversed_instrument,
        "current_price": round(current_price_new, 6),
        "prev_week": {
            "time": prev_week.get("time"),
            "open": round(prev_week_open_new, 6),
            "high": round(prev_week_high_new, 6),
            "low": round(prev_week_low_new, 6),
            "close": round(prev_week_close_new, 6),
        },
        "pullback_percentage": pullback_pct_new,
        "tested_high": tested_high_new,
        "tested_low": tested_low_new,
    }
    
    # Handle current week data if available
    current_week = result.get("current_week")
    if current_week:
        current_week_high_orig = current_week.get("high")
        current_week_low_orig = current_week.get("low")
        
        if current_week_high_orig is not None and current_week_low_orig is not None:
            # Invert: new_high = 1/old_low, new_low = 1/old_high
            current_week_high_new = invert_price(current_week_low_orig)
            current_week_low_new = invert_price(current_week_high_orig)
            
            reversed_result["current_week"] = {
                "time": current_week.get("time"),
                "high": round(current_week_high_new, 6),
                "low": round(current_week_low_new, 6),
            }
            
            # Recalculate max pullback and max extension with inverted prices
            # max_pullback_percentage: lowest point in current week relative to previous week range
            # (using current_week_low_new which is 1/original_current_week_high)
            max_pullback_pct_new = calculate_pullback_percentage(
                current_week_low_new, 
                prev_week_high_new, 
                prev_week_low_new
            )
            # max_extension_percentage: how much the highest point extended beyond previous week's high
            # (using current_week_high_new which is 1/original_current_week_low)
            max_extension_pct_new = calculate_extension_percentage(
                current_week_high_new, 
                prev_week_high_new, 
                prev_week_low_new
            )
            
            if max_pullback_pct_new is not None:
                reversed_result["max_pullback_percentage"] = max_pullback_pct_new
            if max_extension_pct_new is not None:
                reversed_result["max_extension_percentage"] = max_extension_pct_new
    
    return reversed_result


def get_current_price(instrument: str, force_oanda: bool = False) -> Optional[float]:
    """
    Get current price for an instrument using the latest daily candle close.
    
    Args:
        instrument: Currency pair (e.g., "GBP_USD")
        force_oanda: If True, force loading from OANDA API instead of saved data
        
    Returns:
        Current price as float, or None if unavailable
    """
    logger.debug(f"Getting current price for {instrument}, force_oanda={force_oanda}")
    # Fetch enough candles to ensure we get at least one complete one
    candles = fetch_candles_raw(instrument, granularity="D", count=5, force_oanda=force_oanda)
    if not candles:
        return None
    
    # Prefer the latest candle's close price (even if incomplete, it's the most current)
    latest_candle = candles[-1]
    if "mid" in latest_candle and "c" in latest_candle["mid"]:
        return float(latest_candle["mid"]["c"])
    
    # Fallback: find the last complete candle
    for candle in reversed(candles):
        if candle.get("complete", False) and "mid" in candle and "c" in candle["mid"]:
            return float(candle["mid"]["c"])
    
    return None


def calculate_pullback_percentage(
    current_price: float,
    prev_week_high: float,
    prev_week_low: float
) -> Optional[float]:
    """
    Calculate pullback percentage from previous week's range.
    
    Formula: (current_price - prev_week_low) / (prev_week_high - prev_week_low) * 100
    
    Where:
    - 0% = at previous week's low
    - 100% = at previous week's high
    - < 0% = below previous week's low
    - > 100% = above previous week's high
    
    Args:
        current_price: Current price of the instrument
        prev_week_high: Previous week's high
        prev_week_low: Previous week's low
        
    Returns:
        Pullback percentage as float, or None if range is zero
    """
    if prev_week_high == prev_week_low:
        return None
    
    pullback = ((current_price - prev_week_low) / (prev_week_high - prev_week_low)) * 100
    return round(pullback, 2)


def calculate_extension_percentage(
    current_price: float,
    prev_week_high: float,
    prev_week_low: float
) -> Optional[float]:
    """
    Calculate extension percentage beyond previous week's high.
    
    Formula: (current_price - prev_week_high) / (prev_week_high - prev_week_low) * 100
    
    Where:
    - 0% = at previous week's high (no extension)
    - < 0% = below previous week's high (didn't reach it)
    - > 0% = above previous week's high (extended beyond)
    
    Args:
        current_price: Current price of the instrument
        prev_week_high: Previous week's high
        prev_week_low: Previous week's low
        
    Returns:
        Extension percentage as float, or None if range is zero
    """
    if prev_week_high == prev_week_low:
        return None
    
    extension = ((current_price - prev_week_high) / (prev_week_high - prev_week_low)) * 100
    return round(extension, 2)


def has_tested_high(current_price: float, prev_week_high: float, tolerance: float = 0.001) -> bool:
    """
    Check if current price has tested (touched or exceeded) previous week's high.
    
    Args:
        current_price: Current price
        prev_week_high: Previous week's high
        tolerance: Tolerance percentage (default: 0.1%)
        
    Returns:
        True if price has tested the high
    """
    tolerance_amount = prev_week_high * (tolerance / 100.0)
    return current_price >= (prev_week_high - tolerance_amount)


def has_tested_low(current_price: float, prev_week_low: float, tolerance: float = 0.001) -> bool:
    """
    Check if current price has tested (touched or exceeded) previous week's low.
    
    Args:
        current_price: Current price
        prev_week_low: Previous week's low
        tolerance: Tolerance percentage (default: 0.1%)
        
    Returns:
        True if price has tested the low
    """
    tolerance_amount = prev_week_low * (tolerance / 100.0)
    return current_price <= (prev_week_low + tolerance_amount)


def analyze_pullback_for_instrument(
    instrument: str,
    ignore_candles: int = 0,
    period: str = "weekly",
    force_oanda: bool = False,
) -> Optional[Dict]:
    """
    Analyze pullback for a single instrument.
    
    Args:
        instrument: Currency pair (e.g., "GBP_USD")
        ignore_candles: Number of candles to ignore at the end (default: 0)
        period: Aggregation period for the pullback range. Supported values:
            - "daily": use daily candles
            - "weekly": use weekly candles
            - "monthly": use monthly candles
        
    Returns:
        Dictionary with pullback analysis data, or None if analysis fails
    """
    normalized_period = period.lower()
    if normalized_period not in {"daily", "weekly", "monthly"}:
        raise ValueError(f"Unsupported period: {period}. Expected 'daily', 'weekly' or 'monthly'.")

    # Select granularity and candle count based on period
    if normalized_period == "daily":
        granularity = "D"
        candle_count = DEFAULT_CANDLE_COUNT_DAILY
    elif normalized_period == "weekly":
        granularity = "W"
        candle_count = DEFAULT_CANDLE_COUNT_WEEKLY
    else:
        granularity = "M"
        candle_count = DEFAULT_CANDLE_COUNT_MONTHLY

    # Fetch candles for the selected period
    period_candles = fetch_candles_raw(
        instrument,
        granularity=granularity,
        count=candle_count,
        force_oanda=force_oanda,
    )
    
    if len(period_candles) < 2:
        return None
    
    # Get previous period candle (ignore last N candles)
    candles_to_process = period_candles[:-ignore_candles] if ignore_candles > 0 else period_candles
    
    # Find the last complete candle - this is the "previous" period
    # (the current period is likely incomplete)
    prev_period_candle = None
    prev_period_idx = None
    for i in range(len(candles_to_process) - 1, -1, -1):
        if candles_to_process[i].get("complete", False):
            prev_period_candle = candles_to_process[i]
            prev_period_idx = i
            break
    
    if prev_period_candle is None:
        return None
    
    prev_week_high = float(prev_period_candle["mid"]["h"])
    prev_week_low = float(prev_period_candle["mid"]["l"])
    prev_week_open = float(prev_period_candle["mid"]["o"])
    prev_week_close = float(prev_period_candle["mid"]["c"])
    prev_week_time = prev_period_candle["time"]
    
    # Get current period candle (the incomplete one after the last complete period)
    current_week_high = None
    current_week_low = None
    current_week_time = None
    if prev_period_idx is not None and prev_period_idx + 1 < len(period_candles):
        current_week_candle = period_candles[prev_period_idx + 1]
        if "mid" in current_week_candle:
            current_week_high = float(current_week_candle["mid"]["h"])
            current_week_low = float(current_week_candle["mid"]["l"])
            current_week_time = current_week_candle.get("time")
    
    # Get current price
    current_price = get_current_price(instrument, force_oanda=force_oanda)
    if current_price is None:
        return None
    
    # Calculate pullback percentage
    pullback_pct = calculate_pullback_percentage(current_price, prev_week_high, prev_week_low)
    
    if pullback_pct is None:
        return None
    
    # Check if current week has tested high/low
    # Use current week's high/low if available (more accurate), otherwise fall back to current price
    price_to_check_high = current_week_high if current_week_high is not None else current_price
    price_to_check_low = current_week_low if current_week_low is not None else current_price
    
    tested_high = has_tested_high(price_to_check_high, prev_week_high)
    tested_low = has_tested_low(price_to_check_low, prev_week_low)
    
    # Calculate max pullback using current week's low/high
    max_pullback_pct = None
    max_extension_pct = None
    if current_week_low is not None and current_week_high is not None:
        # Max pullback = lowest point reached this week relative to previous week range
        max_pullback_pct = calculate_pullback_percentage(current_week_low, prev_week_high, prev_week_low)
        # Max extension = how much the highest point extended beyond previous week's high
        max_extension_pct = calculate_extension_percentage(current_week_high, prev_week_high, prev_week_low)
    
    # Format previous week time
    try:
        prev_week_datetime = datetime.datetime.fromisoformat(
            prev_week_time.replace("Z", "").replace(".000000000", "")
        )
        prev_week_time_str = prev_week_datetime.strftime("%Y-%m-%d")
    except Exception:
        prev_week_time_str = prev_week_time
    
    # Format current week time
    current_week_time_str = None
    if current_week_time:
        try:
            current_week_datetime = datetime.datetime.fromisoformat(
                current_week_time.replace("Z", "").replace(".000000000", "")
            )
            current_week_time_str = current_week_datetime.strftime("%Y-%m-%d")
        except Exception:
            current_week_time_str = current_week_time
    
    result = {
        "instrument": instrument,
        "current_price": current_price,
        "prev_week": {
            "time": prev_week_time_str,
            "open": prev_week_open,
            "high": prev_week_high,
            "low": prev_week_low,
            "close": prev_week_close,
        },
        "pullback_percentage": pullback_pct,
        "tested_high": tested_high,
        "tested_low": tested_low,
    }
    
    # Add current week data if available
    if current_week_high is not None and current_week_low is not None:
        result["current_week"] = {
            "time": current_week_time_str,
            "high": current_week_high,
            "low": current_week_low,
        }
        if max_pullback_pct is not None:
            result["max_pullback_percentage"] = max_pullback_pct
        if max_extension_pct is not None:
            result["max_extension_percentage"] = max_extension_pct
    
    return result


def analyze_all_pullbacks(
    currency_filter: Optional[str] = None,
    ignore_candles: int = 0,
    period: str = "weekly",
    force_oanda: bool = False,
) -> Dict:
    """
    Analyze pullback for all instruments, optionally filtered by currency.
    
    Results are cached for 12.5 minutes (middle of 10-15 minute range).
    If a request was made within the cache TTL, cached data is returned.
    
    Args:
        currency_filter: Optional currency code to filter by (e.g., "JPY")
        ignore_candles: Number of candles to ignore at the end for the selected period (default: 1)
        period: Aggregation period for the pullback range. Supported values:
            - "daily": use daily candles
            - "weekly": use weekly candles
            - "monthly": use monthly candles
        
    Returns:
        Dictionary with:
        - "timestamp": ISO timestamp
        - "currency_filter": Currency filter applied (if any)
        - "ignore_candles": Number of candles ignored
        - "results": List of pullback analysis results
    """
    # Normalize inputs for cache key
    cache_currency_filter = currency_filter.upper() if currency_filter else None
    normalized_period = period.lower() if period else "weekly"
    if normalized_period not in {"daily", "weekly", "monthly"}:
        raise ValueError(f"Unsupported period: {period}. Expected 'daily', 'weekly' or 'monthly'.")
    
    # Create cache key
    cache_key = (cache_currency_filter, ignore_candles, normalized_period)
    
    logger.info(f"Analyzing pullbacks: currency_filter={currency_filter}, ignore_candles={ignore_candles}, period={normalized_period}, force_oanda={force_oanda}")
    
    # Check cache (only if not forcing OANDA)
    now = datetime.datetime.now()
    if not force_oanda and cache_key in _pullback_cache:
        cached_data, cache_timestamp = _pullback_cache[cache_key]
        time_diff = now - cache_timestamp
        if time_diff.total_seconds() < (CACHE_TTL_MINUTES * 60):
            # Return cached data with updated timestamp
            logger.debug(f"CACHE HIT for pullback analysis: key={cache_key}, age={time_diff.total_seconds():.1f}s")
            result = cached_data.copy()
            result["timestamp"] = now.isoformat()
            return result
        else:
            logger.debug(f"CACHE EXPIRED for pullback analysis: key={cache_key}, age={time_diff.total_seconds():.1f}s (TTL={CACHE_TTL_MINUTES*60}s)")
    elif force_oanda:
        logger.debug(f"force_oanda=True: Skipping cache for pullback analysis")
    else:
        logger.debug(f"CACHE MISS for pullback analysis: key={cache_key}")
    
    # Cache miss or expired - fetch fresh data
    # Filter instruments if currency_filter is provided
    if currency_filter:
        currency_filter = currency_filter.upper()
        filtered_instruments = [
            inst for inst in INSTRUMENTS
            if currency_filter in inst.split("_")
        ]
    else:
        filtered_instruments = INSTRUMENTS
    
    results = []
    # Track which instruments we've already added (to avoid duplicates)
    added_instruments = set()
    
    for instrument in filtered_instruments:
        analysis = analyze_pullback_for_instrument(
            instrument=instrument,
            ignore_candles=ignore_candles,
            period=normalized_period,
            force_oanda=force_oanda,
        )
        if analysis:
            try:
                base, quote = instrument.split("_")
                
                # If currency filter is provided, reverse results where currency is in quote position
                if cache_currency_filter:
                    # If target currency is in quote position, reverse the result
                    if quote.upper() == cache_currency_filter.upper():
                        reversed_analysis = reverse_pullback_result(analysis, cache_currency_filter)
                        # Only use reversed result if pullback_percentage is valid
                        if reversed_analysis.get("pullback_percentage") is not None:
                            analysis = reversed_analysis
                            instrument = reversed_analysis.get("instrument", instrument)
                else:
                    # No currency filter: add both original and reversed versions
                    # Add original result
                    if instrument not in added_instruments:
                        if analysis.get("pullback_percentage") is not None:
                            results.append(analysis)
                            added_instruments.add(instrument)
                    
                    # Add reversed version if quote currency is in our currency list
                    # and the reversed pair doesn't already exist in the original instruments list
                    if quote.upper() in CURRENCY_FULL_NAMES:
                        reversed_instrument = f"{quote}_{base}"
                        # Only add reversed if it's not in the original instruments list
                        if reversed_instrument not in INSTRUMENTS:
                            reversed_analysis = reverse_pullback_result(analysis, quote)
                            # Only add reversed if it doesn't already exist and pullback is valid
                            if (reversed_instrument not in added_instruments and 
                                reversed_analysis.get("pullback_percentage") is not None):
                                results.append(reversed_analysis)
                                added_instruments.add(reversed_instrument)
                    continue  # Skip the normal append below since we handled it
                    
            except ValueError:
                # Skip reversal if instrument name is malformed
                pass
            
            # Only add if pullback_percentage is valid (should always be true, but safety check)
            if analysis.get("pullback_percentage") is not None and instrument not in added_instruments:
                results.append(analysis)
                added_instruments.add(instrument)
    
    # Sort by pullback percentage (descending)
    results.sort(key=lambda x: x["pullback_percentage"], reverse=True)

    # Calculate strength/weakness if a specific currency is requested
    strength: Optional[float] = None
    weakness: Optional[float] = None
    strength_details: Optional[Dict[str, object]] = None
    weakness_details: Optional[Dict[str, object]] = None
    all_currencies_strength_weakness: Optional[Dict[str, Dict[str, object]]] = None

    if cache_currency_filter and results:
        currency_stats = calculate_currency_strength_weakness(cache_currency_filter, results)
        if currency_stats is not None:
            strength = currency_stats["strength"]  # type: ignore[index]
            weakness = currency_stats["weakness"]  # type: ignore[index]
            strength_details = currency_stats["strength_details"]  # type: ignore[index]
            weakness_details = currency_stats["weakness_details"]  # type: ignore[index]
    elif results:
        # No specific currency filter: compute stats for all currencies
        all_currencies_strength_weakness = calculate_all_currencies_strength_weakness(results)

    result = {
        "timestamp": now.isoformat(),
        "currency_filter": cache_currency_filter,
        "ignore_candles": ignore_candles,
        "period": normalized_period,
        "results": results,
        "strength": strength,
        "weakness": weakness,
        "strength_details": strength_details,
        "weakness_details": weakness_details,
        "all_currencies_strength_weakness": all_currencies_strength_weakness,
    }
    
    # Store in cache
    _pullback_cache[cache_key] = (result, now)
    logger.debug(f"Cached pullback analysis result: key={cache_key}, TTL={CACHE_TTL_MINUTES} minutes")

    return result

