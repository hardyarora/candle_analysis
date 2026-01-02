"""
Core candle analysis functionality.

Extracted from daily_candle_analysis.py for modular use.
"""
import datetime
import calendar
import json
import logging
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from .config import (
    OANDA_API_URL,
    ACCESS_TOKEN,
    INSTRUMENTS,
    DEFAULT_IGNORE_CANDLES,
    DEFAULT_CANDLE_COUNT_DAILY,
    DEFAULT_ENGULFING_THRESHOLD_PERCENT,
    OANDA_SAVED_DATA_DIR,
)
from ..utils.timeframe import parse_timeframe

# Optional imports for feedback integration
try:
    from .engulfing_feedback import get_merged_feedback
    from .engulfing_metrics import calculate_engulfing_metrics
    from .adaptive_learning import calculate_adaptive_similarity, learn_from_feedback
    FEEDBACK_AVAILABLE = True
except ImportError:
    FEEDBACK_AVAILABLE = False

logger = logging.getLogger("candle_analysis_api")


def load_candles_from_saved_data(instrument: str, granularity: str) -> Optional[List[Dict]]:
    """
    Load candles from saved data files for weekly, monthly, or hourly granularities.
    
    Args:
        instrument: Currency pair (e.g., "GBP_USD")
        granularity: Time granularity ("W" for weekly, "M" for monthly, "H1" for hourly)
        
    Returns:
        List of candle dictionaries or None if not found
    """
    # Map granularity to file name
    granularity_to_file = {
        "W": "weekly_candles.json",
        "M": "monthly_candles.json",
        "H1": "hourly_candles.json",
    }
    
    if granularity not in granularity_to_file:
        return None
    
    file_name = granularity_to_file[granularity]
    file_path = OANDA_SAVED_DATA_DIR / file_name
    
    if not file_path.exists():
        logger.debug(f"Cache file not found for {instrument} {granularity}: {file_path}")
        return None
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract candles for the specific instrument
        if "data" in data and instrument in data["data"]:
            candles = data["data"][instrument]
            logger.debug(f"Loaded {len(candles)} candles from CACHE for {instrument} {granularity} (file: {file_path})")
            return candles
        
        logger.debug(f"Instrument {instrument} not found in cache file {file_path}")
        return None
    except Exception as e:
        logger.warning(f"Error loading cache file {file_path} for {instrument} {granularity}: {e}")
        return None


def fetch_candles_raw(instrument: str, granularity: str = "D", count: int = 30, force_oanda: bool = False) -> List[Dict]:
    """
    Fetch raw candles list from OANDA for given instrument and granularity.
    
    For weekly (W), monthly (M), and hourly (H1) granularities, this function will
    attempt to load from saved data files first, unless force_oanda is True.
    
    Args:
        instrument: Currency pair (e.g., "GBP_USD")
        granularity: Time granularity ("D" for daily, "W" for weekly, "M" for monthly, "H1" for hourly)
        count: Number of candles to fetch (used when loading from OANDA API)
        force_oanda: If True, force loading from OANDA API instead of saved data
        
    Returns:
        List of candle dictionaries from OANDA API or saved data
    """
    # For weekly, monthly, and hourly, try loading from saved data first
    if not force_oanda and granularity in ("W", "M", "H1"):
        logger.debug(f"Attempting to load {instrument} {granularity} from cache (force_oanda=False)")
        saved_candles = load_candles_from_saved_data(instrument, granularity)
        if saved_candles is not None:
            # Limit to requested count if specified
            result = saved_candles[-count:] if count > 0 and len(saved_candles) > count else saved_candles
            logger.debug(f"Using CACHE for {instrument} {granularity}: {len(result)} candles")
            return result
        logger.debug(f"Cache miss for {instrument} {granularity}, falling back to OANDA API")
    elif force_oanda:
        logger.debug(f"force_oanda=True: Loading {instrument} {granularity} from OANDA API (skipping cache)")
    else:
        logger.debug(f"Loading {instrument} {granularity} from OANDA API (daily granularity, no cache)")
    
    # Fall back to OANDA API
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
        logger.debug(f"Fetching from OANDA API: {instrument} {granularity} (count={count})")
        response = requests.get(url, headers=headers, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            candles = data.get("candles", [])
            logger.debug(f"Loaded {len(candles)} candles from OANDA API for {instrument} {granularity}")
            return candles
        else:
            logger.warning(f"OANDA API returned status {response.status_code} for {instrument} {granularity}")
        return []
    except Exception as e:
        logger.error(f"Error fetching from OANDA API for {instrument} {granularity}: {e}")
        return []


def merge_candles(candles: List[Dict]) -> Optional[Dict]:
    """
    Merge multiple candles into one.
    
    Rules:
    - high = max(all highs)
    - low = min(all lows)
    - open = first candle's open
    - close = last candle's close
    - time = first candle's time
    
    Args:
        candles: List of candle dictionaries from OANDA
        
    Returns:
        Merged candle dictionary or None if empty
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
        Combined pattern string like "downclose ⬇️ + bearish" or "upclose ⬆️ + bullish engulfing"
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
        # Bullish engulfing: mc2 is bullish (green) AND mc1 is bearish (red)
        if mc2_close > mc2_open and mc1_close < mc1_open:
            patterns.append("bullish engulfing")
        # Bearish engulfing: mc2 is bearish (red) AND mc1 is bullish (green)
        elif mc2_close < mc2_open and mc1_close > mc1_open:
            patterns.append("bearish engulfing")
    
    if not patterns:
        return "neutral"
    
    # Combine patterns with " + "
    return " + ".join(patterns)


def analyze_all_currencies(timeframe: str, ignore_candles: int = DEFAULT_IGNORE_CANDLES, force_oanda: bool = False) -> Dict:
    """
    Analyze all currencies across all instruments for the given timeframe.
    Returns pattern-based groupings of currency pairs (instruments).
    
    This is the main analysis function that processes all instruments and returns
    merged results suitable for API responses.
    
    Args:
        timeframe: Timeframe like "1D", "2D", "3D", "4D"
        ignore_candles: Number of candles to ignore at the end (default: 1)
        force_oanda: If True, force loading from OANDA API instead of saved data
    
    Returns:
        Dictionary with:
        - "timeframe": The normalized timeframe
        - "timestamp": ISO timestamp of analysis
        - "ignore_candles": Number of candles ignored
        - "patterns": Dictionary with pattern keys and lists of instruments
        - "instruments": List of all instrument analysis results
    """
    logger.info(f"Starting analysis for timeframe={timeframe}, ignore_candles={ignore_candles}, force_oanda={force_oanda}")
    
    # Parse timeframe
    granularity, n_candles = parse_timeframe(timeframe)
    
    if granularity != "D":
        raise ValueError(f"Only daily timeframes (1D-4D) are supported, got {timeframe}")
    
    if n_candles < 1 or n_candles > 4:
        raise ValueError(f"Timeframe must be between 1D and 4D, got {timeframe}")
    
    # Track instruments (pairs) by pattern
    pattern_instruments = defaultdict(set)
    
    # Store detailed results for each instrument
    instrument_results = []
    
    for instrument in INSTRUMENTS:
        # Fetch candles
        candles = fetch_candles_raw(instrument, granularity=granularity, count=DEFAULT_CANDLE_COUNT_DAILY, force_oanda=force_oanda)
        
        if len(candles) < (n_candles * 2) + ignore_candles:
            instrument_results.append({
                "instrument": instrument,
                "error": f"Not enough candles (need {n_candles * 2 + ignore_candles}, got {len(candles)})"
            })
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
            instrument_results.append({
                "instrument": instrument,
                "error": "Failed to merge candles"
            })
            continue
        
        # Analyze relationship
        relation = analyze_candle_relation(mc1, mc2)
        
        # Determine color
        mc2_close = float(mc2["close"])
        mc2_open = float(mc2["open"])
        is_bullish = mc2_close > mc2_open
        is_bearish = mc2_close < mc2_open
        
        # Format dates
        try:
            mc1_time = datetime.datetime.fromisoformat(mc1["time"].replace("Z", "").replace(".000000000", ""))
            mc2_time = datetime.datetime.fromisoformat(mc2["time"].replace("Z", "").replace(".000000000", ""))
            mc1_last_time = mc1_candles[-1]["time"] if mc1_candles else mc1["time"]
            mc2_last_time = mc2_candles[-1]["time"] if mc2_candles else mc2["time"]
            mc1_last = datetime.datetime.fromisoformat(mc1_last_time.replace("Z", "").replace(".000000000", ""))
            mc2_last = datetime.datetime.fromisoformat(mc2_last_time.replace("Z", "").replace(".000000000", ""))
            
            mc1_time_str = f"{mc1_time.strftime('%Y-%m-%d')} to {mc1_last.strftime('%Y-%m-%d')}"
            mc2_time_str = f"{mc2_time.strftime('%Y-%m-%d')} to {mc2_last.strftime('%Y-%m-%d')}"
        except Exception:
            mc1_time_str = mc1["time"]
            mc2_time_str = mc2["time"]
        
        # Store detailed instrument result
        instrument_result = {
            "instrument": instrument,
            "mc1": {
                "time": mc1_time_str,
                "open": float(mc1["open"]),
                "high": mc1["high"],
                "low": mc1["low"],
                "close": float(mc1["close"]),
            },
            "mc2": {
                "time": mc2_time_str,
                "open": float(mc2["open"]),
                "high": mc2["high"],
                "low": mc2["low"],
                "close": float(mc2["close"]),
            },
            "relation": relation,
            "color": "GREEN" if is_bullish else ("RED" if is_bearish else "NEUTRAL"),
        }
        instrument_results.append(instrument_result)
        
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
    patterns = {}
    for pattern, instruments in pattern_instruments.items():
        patterns[pattern] = sorted(instruments)
    
    return {
        "timeframe": timeframe,
        "timestamp": datetime.datetime.now().isoformat(),
        "ignore_candles": ignore_candles,
        "patterns": patterns,
        "instruments": instrument_results,
    }


def enhance_analysis_with_feedback(
    analysis_data: Dict,
    timeframe: str,
    use_merged: bool = True,
    use_adaptive: bool = True
) -> Dict:
    """
    Enhance analysis results with feedback-based scoring and statistics.
    
    Args:
        analysis_data: Analysis data dictionary from analyze_all_currencies()
        timeframe: Timeframe string (e.g., "1D", "2D")
        use_merged: If True, use merged feedback (default: True)
        use_adaptive: If True, use adaptive learning (default: True)
        
    Returns:
        Enhanced analysis dictionary with feedback scores and statistics
    """
    if not FEEDBACK_AVAILABLE:
        logger.warning("Feedback modules not available, returning original analysis")
        return analysis_data
    
    enhanced = analysis_data.copy()
    enhanced["feedback_enhanced"] = True
    enhanced["feedback_statistics"] = {}
    
    # Get learned patterns
    learned_patterns = None
    if use_adaptive:
        try:
            learned_patterns = learn_from_feedback(use_merged=use_merged)
        except Exception as e:
            logger.warning(f"Failed to learn patterns: {e}")
    
    # Enhance each instrument result
    enhanced_instruments = []
    for instrument_result in analysis_data.get("instruments", []):
        enhanced_instr = instrument_result.copy()
        
        relation = instrument_result.get("relation", "")
        has_bullish_engulfing = "bullish engulfing" in relation
        has_bearish_engulfing = "bearish engulfing" in relation
        
        if has_bullish_engulfing or has_bearish_engulfing:
            pattern_type = "bullish" if has_bullish_engulfing else "bearish"
            instrument = instrument_result.get("instrument", "")
            mc1 = instrument_result.get("mc1", {})
            mc2 = instrument_result.get("mc2", {})
            
            if mc1 and mc2:
                try:
                    # Calculate metrics for current pattern
                    current_metrics = calculate_engulfing_metrics(mc1, mc2, pattern_type)
                    
                    # Get historical feedback
                    feedback_list = get_merged_feedback(
                        instrument=instrument,
                        pattern_type=pattern_type
                    ) if use_merged else []
                    
                    # Calculate similarity score
                    similarity_score = 0.0
                    if feedback_list:
                        similarity_score = calculate_adaptive_similarity(
                            current_metrics=current_metrics,
                            historical_feedback=feedback_list,
                            learned_patterns=learned_patterns
                        )
                    
                    # Add feedback information
                    enhanced_instr["feedback"] = {
                        "similarity_score": round(similarity_score, 3),
                        "metrics": current_metrics,
                        "pattern_type": pattern_type,
                        "has_feedback_data": len(feedback_list) > 0
                    }
                    
                    # Add confidence indicator
                    if similarity_score > 0.7:
                        enhanced_instr["feedback"]["confidence"] = "high"
                    elif similarity_score > 0.4:
                        enhanced_instr["feedback"]["confidence"] = "medium"
                    else:
                        enhanced_instr["feedback"]["confidence"] = "low"
                    
                except Exception as e:
                    logger.warning(f"Failed to enhance instrument {instrument} with feedback: {e}")
                    enhanced_instr["feedback"] = {"error": str(e)}
        
        enhanced_instruments.append(enhanced_instr)
    
    enhanced["instruments"] = enhanced_instruments
    
    # Add overall statistics
    try:
        from .engulfing_feedback import get_merged_feedback
        
        # Count engulfing patterns
        bullish_count = sum(1 for instr in enhanced_instruments if "bullish engulfing" in instr.get("relation", ""))
        bearish_count = sum(1 for instr in enhanced_instruments if "bearish engulfing" in instr.get("relation", ""))
        
        if bullish_count > 0 or bearish_count > 0:
            # Get feedback for both pattern types
            bullish_feedback = get_merged_feedback(pattern_type="bullish") if use_merged else []
            bearish_feedback = get_merged_feedback(pattern_type="bearish") if use_merged else []
            
            total_feedback = len(bullish_feedback) + len(bearish_feedback)
            
            if total_feedback > 0:
                avg_rating = (
                    sum(f.get("rating", 0) for f in bullish_feedback) +
                    sum(f.get("rating", 0) for f in bearish_feedback)
                ) / total_feedback
                
                enhanced["feedback_statistics"] = {
                    "total_feedback_entries": total_feedback,
                    "bullish_feedback_entries": len(bullish_feedback),
                    "bearish_feedback_entries": len(bearish_feedback),
                    "average_rating": round(avg_rating, 2),
                    "learned_patterns_available": learned_patterns is not None,
                    "engulfing_patterns_found": {
                        "bullish": bullish_count,
                        "bearish": bearish_count
                    }
                }
    except Exception as e:
        logger.warning(f"Failed to add feedback statistics: {e}")
    
    return enhanced
