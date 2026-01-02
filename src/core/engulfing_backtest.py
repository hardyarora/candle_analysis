"""
Backtesting functionality for engulfing patterns.

Validates patterns against historical data and compares with feedback.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Literal

from .candle_analyzer import fetch_candles_raw, merge_candles, analyze_candle_relation
from .engulfing_feedback import get_merged_feedback
from .engulfing_metrics import calculate_engulfing_metrics
from ..utils.timeframe import parse_timeframe

logger = logging.getLogger("candle_analysis_api")


def backtest_pattern(
    instrument: str,
    pattern_type: Literal["bullish", "bearish"],
    start_date: str,
    end_date: str,
    timeframe: str
) -> Dict:
    """
    Backtest engulfing patterns against historical data.
    
    Args:
        instrument: Currency pair (e.g., "GBP_USD")
        pattern_type: "bullish" or "bearish"
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        timeframe: Timeframe (e.g., "1D", "2D")
        
    Returns:
        Dictionary with backtest results
    """
    # Parse timeframe
    granularity, n_candles = parse_timeframe(timeframe)
    
    # Parse dates
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    # Fetch historical candles
    # We need enough candles to cover the date range
    days_diff = (end - start).days
    count = max(100, days_diff * 2)  # Fetch enough candles
    
    candles = fetch_candles_raw(instrument, granularity=granularity, count=count, force_oanda=False)
    
    if len(candles) < (n_candles * 2):
        return {
            "error": "Not enough historical candles",
            "total_patterns_found": 0
        }
    
    # Get merged feedback for comparison
    feedback_list = get_merged_feedback(
        instrument=instrument,
        pattern_type=pattern_type
    )
    
    # Find all engulfing patterns in the date range
    patterns_found = []
    detailed_results = []
    
    # Process candles in windows
    for i in range(n_candles * 2, len(candles)):
        # Get candle windows
        mc2_candles = candles[i - n_candles:i]
        mc1_candles = candles[i - (n_candles * 2):i - n_candles]
        
        mc1 = merge_candles(mc1_candles)
        mc2 = merge_candles(mc2_candles)
        
        if not mc1 or not mc2:
            continue
        
        # Check if it's an engulfing pattern
        relation = analyze_candle_relation(mc1, mc2)
        
        is_bullish_engulfing = "bullish engulfing" in relation
        is_bearish_engulfing = "bearish engulfing" in relation
        
        if (pattern_type == "bullish" and is_bullish_engulfing) or \
           (pattern_type == "bearish" and is_bearish_engulfing):
            
            # Get candle date
            candle_time = mc2.get("time", "")
            try:
                candle_date = datetime.fromisoformat(candle_time.replace("Z", "").replace(".000000000", ""))
                candle_date_str = candle_date.strftime("%Y-%m-%d")
            except Exception:
                continue
            
            # Check if within date range
            if start <= candle_date <= end:
                # Calculate metrics
                metrics = calculate_engulfing_metrics(mc1, mc2, pattern_type)
                
                # Check if matches feedback characteristics
                matches_feedback = False
                similarity_score = 0.0
                
                if feedback_list:
                    # Find best matching feedback
                    best_match = None
                    best_similarity = 0.0
                    
                    for feedback in feedback_list:
                        feedback_metrics = feedback.get("metrics", {})
                        # Simple similarity check
                        similarity = _calculate_simple_similarity(metrics, feedback_metrics)
                        if similarity > best_similarity:
                            best_similarity = similarity
                            best_match = feedback
                    
                    if best_match and best_similarity > 0.6:  # 60% similarity threshold
                        matches_feedback = True
                        similarity_score = best_similarity
                
                # Calculate price movement after pattern (if we have future candles)
                price_movement = None
                if i + 1 < len(candles):
                    pattern_close = float(mc2.get("close", 0))
                    # Get next candle's close
                    next_candle = candles[i + 1] if i + 1 < len(candles) else None
                    if next_candle and "mid" in next_candle and "c" in next_candle["mid"]:
                        next_close = float(next_candle["mid"]["c"])
                        price_movement = ((next_close - pattern_close) / pattern_close) * 100
                
                pattern_result = {
                    "date": candle_date_str,
                    "instrument": instrument,
                    "pattern_type": pattern_type,
                    "metrics": metrics,
                    "matches_feedback": matches_feedback,
                    "similarity_score": round(similarity_score, 3),
                    "price_movement_percent": round(price_movement, 2) if price_movement else None,
                    "mc1": {
                        "open": float(mc1.get("open", 0)),
                        "close": float(mc1.get("close", 0)),
                        "high": float(mc1.get("high", 0)),
                        "low": float(mc1.get("low", 0))
                    },
                    "mc2": {
                        "open": float(mc2.get("open", 0)),
                        "close": float(mc2.get("close", 0)),
                        "high": float(mc2.get("high", 0)),
                        "low": float(mc2.get("low", 0))
                    }
                }
                
                patterns_found.append(pattern_result)
                detailed_results.append(pattern_result)
    
    # Calculate statistics
    total_patterns = len(patterns_found)
    matching_patterns = sum(1 for p in patterns_found if p["matches_feedback"])
    
    # Calculate success rate (for patterns matching feedback)
    matching_with_movement = [
        p for p in patterns_found
        if p["matches_feedback"] and p["price_movement_percent"] is not None
    ]
    
    if matching_patterns > 0:
        # Success rate based on positive price movement (for bullish) or negative (for bearish)
        if pattern_type == "bullish":
            successful = sum(1 for p in matching_with_movement if p["price_movement_percent"] > 0)
        else:
            successful = sum(1 for p in matching_with_movement if p["price_movement_percent"] < 0)
        
        success_rate = (successful / len(matching_with_movement)) * 100 if matching_with_movement else 0.0
    else:
        success_rate = 0.0
    
    # Average price movement
    movements = [p["price_movement_percent"] for p in patterns_found if p["price_movement_percent"] is not None]
    avg_movement = sum(movements) / len(movements) if movements else 0.0
    
    return {
        "instrument": instrument,
        "pattern_type": pattern_type,
        "timeframe": timeframe,
        "start_date": start_date,
        "end_date": end_date,
        "total_patterns_found": total_patterns,
        "patterns_matching_feedback": matching_patterns,
        "success_rate": round(success_rate, 2),
        "average_price_movement": round(avg_movement, 2),
        "detailed_results": detailed_results[:50]  # Limit to first 50 for response size
    }


def _calculate_simple_similarity(metrics1: Dict, metrics2: Dict) -> float:
    """Calculate simple similarity between two metrics dictionaries."""
    if not metrics1 or not metrics2:
        return 0.0
    
    similarities = []
    
    # Compare body size ratio
    if "body_size_ratio" in metrics1 and "body_size_ratio" in metrics2:
        val1 = metrics1["body_size_ratio"]
        val2 = metrics2["body_size_ratio"]
        if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            max_val = max(abs(val1), abs(val2), 0.001)
            diff = abs(val1 - val2) / max_val
            similarity = 1.0 - min(1.0, diff)
            similarities.append(similarity)
    
    # Compare body position
    if "body_position" in metrics1 and "body_position" in metrics2:
        if metrics1["body_position"] == metrics2["body_position"]:
            similarities.append(1.0)
        else:
            similarities.append(0.0)
    
    # Compare body overlap
    if "body_overlap_percentage" in metrics1 and "body_overlap_percentage" in metrics2:
        val1 = metrics1["body_overlap_percentage"]
        val2 = metrics2["body_overlap_percentage"]
        if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            max_val = max(abs(val1), abs(val2), 100.0)
            diff = abs(val1 - val2) / max_val
            similarity = 1.0 - min(1.0, diff)
            similarities.append(similarity)
    
    if similarities:
        return sum(similarities) / len(similarities)
    return 0.0


def validate_pattern_against_feedback(pattern_data: Dict, feedback_data: List[Dict]) -> Dict:
    """
    Validate a pattern against feedback data.
    
    Args:
        pattern_data: Pattern data with metrics
        feedback_data: List of feedback entries
        
    Returns:
        Validation result with similarity scores and match information
    """
    if not feedback_data:
        return {
            "matches": False,
            "similarity_score": 0.0,
            "best_match": None
        }
    
    pattern_metrics = pattern_data.get("metrics", {})
    
    best_match = None
    best_similarity = 0.0
    
    for feedback in feedback_data:
        feedback_metrics = feedback.get("metrics", {})
        similarity = _calculate_simple_similarity(pattern_metrics, feedback_metrics)
        
        # Weight by rating
        rating = feedback.get("rating", 5)
        weighted_similarity = similarity * (rating / 10.0)
        
        if weighted_similarity > best_similarity:
            best_similarity = weighted_similarity
            best_match = {
                "id": feedback.get("id"),
                "rating": rating,
                "similarity": round(similarity, 3),
                "weighted_similarity": round(weighted_similarity, 3)
            }
    
    return {
        "matches": best_similarity > 0.6,  # 60% threshold
        "similarity_score": round(best_similarity, 3),
        "best_match": best_match
    }

