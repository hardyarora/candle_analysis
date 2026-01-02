"""
Feedback storage and retrieval for engulfing candle patterns.

Handles storing, retrieving, and aggregating feedback data for both
timeframe-specific and merged/general feedback across timeframes.
"""
import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Literal
from collections import defaultdict

from .config import (
    ENGULFING_FEEDBACK_DIR,
    ENGULFING_FEEDBACK_MERGED_DIR,
    SUPPORTED_TIMEFRAMES,
)
from ..utils.timeframe import normalize_timeframe

logger = logging.getLogger("candle_analysis_api")


def ensure_feedback_dirs(timeframe: Optional[str] = None, pattern_type: Optional[str] = None) -> Path:
    """
    Ensure feedback directories exist.
    
    Args:
        timeframe: Optional timeframe (e.g., "1D") for timeframe-specific storage
        pattern_type: Optional pattern type ("bullish" or "bearish")
        
    Returns:
        Path to the feedback directory
    """
    if timeframe:
        normalized_tf = normalize_timeframe(timeframe)
        if pattern_type:
            feedback_dir = ENGULFING_FEEDBACK_DIR / normalized_tf / pattern_type
        else:
            feedback_dir = ENGULFING_FEEDBACK_DIR / normalized_tf
    else:
        if pattern_type:
            feedback_dir = ENGULFING_FEEDBACK_MERGED_DIR / pattern_type
        else:
            feedback_dir = ENGULFING_FEEDBACK_MERGED_DIR
    
    feedback_dir.mkdir(parents=True, exist_ok=True)
    return feedback_dir


def generate_feedback_id() -> str:
    """Generate a unique feedback ID."""
    return str(uuid.uuid4())


def store_feedback(
    instrument: str,
    timeframe: str,
    date: str,
    pattern_type: Literal["bullish", "bearish"],
    rating: int,
    metrics: Dict,
    candles: Dict,
    notes: Optional[str] = None,
    context: Optional[Dict] = None
) -> Path:
    """
    Store timeframe-specific feedback.
    
    Args:
        instrument: Currency pair (e.g., "GBP_USD")
        timeframe: Timeframe (e.g., "1D", "2D")
        date: Date in YYYY-MM-DD format
        pattern_type: "bullish" or "bearish"
        rating: Rating from 1-10
        metrics: Calculated metrics dictionary
        candles: Dictionary with 'mc1' and 'mc2' candle data
        notes: Optional notes
        context: Optional context information
        
    Returns:
        Path to the stored feedback file
    """
    normalized_tf = normalize_timeframe(timeframe)
    feedback_dir = ensure_feedback_dirs(timeframe=normalized_tf, pattern_type=pattern_type)
    
    feedback_id = generate_feedback_id()
    filename = f"{instrument}_{date}_{feedback_id}.json"
    filepath = feedback_dir / filename
    
    feedback_data = {
        "id": feedback_id,
        "instrument": instrument,
        "timeframe": normalized_tf,
        "date": date,
        "pattern_type": pattern_type,
        "rating": rating,
        "metrics": metrics,
        "candles": candles,
        "context": context or {},
        "notes": notes,
        "timestamp": datetime.now().isoformat(),
        "is_merged": False
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(feedback_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Stored feedback: {filepath}")
    return filepath


def store_general_feedback(
    instrument: str,
    date: str,
    pattern_type: Literal["bullish", "bearish"],
    rating: int,
    metrics: Dict,
    candles: Dict,
    notes: Optional[str] = None,
    context: Optional[Dict] = None
) -> Path:
    """
    Store general/merged feedback (not timeframe-specific).
    
    Args:
        instrument: Currency pair (e.g., "GBP_USD")
        date: Date in YYYY-MM-DD format
        pattern_type: "bullish" or "bearish"
        rating: Rating from 1-10
        metrics: Calculated metrics dictionary
        candles: Dictionary with 'mc1' and 'mc2' candle data
        notes: Optional notes
        context: Optional context information
        
    Returns:
        Path to the stored feedback file
    """
    feedback_dir = ensure_feedback_dirs(pattern_type=pattern_type)
    
    feedback_id = generate_feedback_id()
    filename = f"{instrument}_{date}_{feedback_id}.json"
    filepath = feedback_dir / filename
    
    feedback_data = {
        "id": feedback_id,
        "instrument": instrument,
        "timeframe": None,
        "date": date,
        "pattern_type": pattern_type,
        "rating": rating,
        "metrics": metrics,
        "candles": candles,
        "context": context or {},
        "notes": notes,
        "timestamp": datetime.now().isoformat(),
        "is_merged": True,
        "source_timeframes": []
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(feedback_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Stored general feedback: {filepath}")
    return filepath


def aggregate_feedback_across_timeframes(
    instrument: str,
    pattern_type: Literal["bullish", "bearish"],
    date: str,
    weight_by_rating: bool = True
) -> Optional[Dict]:
    """
    Aggregate feedback from all timeframes for the same instrument/date/pattern.
    
    Args:
        instrument: Currency pair
        pattern_type: "bullish" or "bearish"
        date: Date in YYYY-MM-DD format
        weight_by_rating: If True, weight metrics by rating (default: True)
        
    Returns:
        Aggregated feedback dictionary or None if no feedback found
    """
    # Collect all timeframe-specific feedback
    all_feedback = []
    source_timeframes = []
    
    for timeframe in SUPPORTED_TIMEFRAMES:
        normalized_tf = normalize_timeframe(timeframe)
        feedback_dir = ENGULFING_FEEDBACK_DIR / normalized_tf / pattern_type
        
        if not feedback_dir.exists():
            continue
        
        # Find feedback files for this instrument and date
        pattern = f"{instrument}_{date}_*.json"
        for filepath in feedback_dir.glob(pattern):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    feedback = json.load(f)
                    if feedback.get("instrument") == instrument and feedback.get("date") == date:
                        all_feedback.append(feedback)
                        if normalized_tf not in source_timeframes:
                            source_timeframes.append(normalized_tf)
            except Exception as e:
                logger.warning(f"Error reading feedback file {filepath}: {e}")
                continue
    
    if not all_feedback:
        return None
    
    # Calculate weighted averages
    if weight_by_rating:
        total_weight = sum(f.get("rating", 1) for f in all_feedback)
        if total_weight == 0:
            total_weight = len(all_feedback)
        
        # Weighted average rating
        weighted_rating = sum(f.get("rating", 1) ** 2 for f in all_feedback) / total_weight
        
        # Weighted average metrics
        metrics_keys = all_feedback[0].get("metrics", {}).keys()
        weighted_metrics = {}
        
        for key in metrics_keys:
            if key in ["mc1_wick_ratios", "mc2_wick_ratios", "context"]:
                # Handle nested dictionaries
                weighted_metrics[key] = {}
                if isinstance(all_feedback[0]["metrics"].get(key), dict):
                    for subkey in all_feedback[0]["metrics"][key].keys():
                        weighted_value = sum(
                            f["metrics"][key].get(subkey, 0) * f.get("rating", 1)
                            for f in all_feedback
                            if isinstance(f.get("metrics", {}).get(key), dict)
                        ) / total_weight
                        weighted_metrics[key][subkey] = weighted_value
            elif key in ["body_position", "whole_body_position"]:
                # For categorical data, use most common weighted by rating
                position_counts = defaultdict(float)
                for f in all_feedback:
                    pos = f["metrics"].get(key, "unknown")
                    position_counts[pos] += f.get("rating", 1)
                weighted_metrics[key] = max(position_counts.items(), key=lambda x: x[1])[0]
            else:
                # Numeric metrics
                weighted_value = sum(
                    f["metrics"].get(key, 0) * f.get("rating", 1)
                    for f in all_feedback
                ) / total_weight
                weighted_metrics[key] = weighted_value
    else:
        # Simple average
        weighted_rating = sum(f.get("rating", 1) for f in all_feedback) / len(all_feedback)
        
        metrics_keys = all_feedback[0].get("metrics", {}).keys()
        weighted_metrics = {}
        
        for key in metrics_keys:
            if key in ["mc1_wick_ratios", "mc2_wick_ratios", "context"]:
                weighted_metrics[key] = {}
                if isinstance(all_feedback[0]["metrics"].get(key), dict):
                    for subkey in all_feedback[0]["metrics"][key].keys():
                        avg_value = sum(
                            f["metrics"][key].get(subkey, 0)
                            for f in all_feedback
                            if isinstance(f.get("metrics", {}).get(key), dict)
                        ) / len(all_feedback)
                        weighted_metrics[key][subkey] = avg_value
            elif key in ["body_position", "whole_body_position"]:
                position_counts = defaultdict(int)
                for f in all_feedback:
                    pos = f["metrics"].get(key, "unknown")
                    position_counts[pos] += 1
                weighted_metrics[key] = max(position_counts.items(), key=lambda x: x[1])[0]
            else:
                avg_value = sum(f["metrics"].get(key, 0) for f in all_feedback) / len(all_feedback)
                weighted_metrics[key] = avg_value
    
    # Calculate confidence score
    rating_variance = sum((f.get("rating", 1) - weighted_rating) ** 2 for f in all_feedback) / len(all_feedback)
    rating_consistency = 1.0 / (1.0 + rating_variance)  # Higher consistency = lower variance
    timeframe_count_factor = min(len(source_timeframes) / len(SUPPORTED_TIMEFRAMES), 1.0)
    feedback_count_factor = min(len(all_feedback) / 4.0, 1.0)  # Normalize to max 4 timeframes
    
    confidence_score = (rating_consistency * 0.4 + timeframe_count_factor * 0.3 + feedback_count_factor * 0.3)
    
    # Use the most recent candles data
    latest_feedback = max(all_feedback, key=lambda x: x.get("timestamp", ""))
    
    aggregated = {
        "id": generate_feedback_id(),
        "instrument": instrument,
        "timeframe": None,
        "date": date,
        "pattern_type": pattern_type,
        "rating": round(weighted_rating, 2),
        "metrics": weighted_metrics,
        "candles": latest_feedback.get("candles", {}),
        "context": latest_feedback.get("context", {}),
        "notes": "; ".join(f.get("notes", "") for f in all_feedback if f.get("notes")),
        "timestamp": datetime.now().isoformat(),
        "is_merged": True,
        "source_timeframes": sorted(source_timeframes),
        "confidence_score": round(confidence_score, 3),
        "feedback_count": len(all_feedback)
    }
    
    # Store the aggregated feedback
    store_general_feedback(
        instrument=instrument,
        date=date,
        pattern_type=pattern_type,
        rating=int(round(weighted_rating)),
        metrics=weighted_metrics,
        candles=aggregated["candles"],
        notes=aggregated["notes"],
        context=aggregated["context"]
    )
    
    return aggregated


def get_feedback(
    instrument: Optional[str] = None,
    timeframe: Optional[str] = None,
    pattern_type: Optional[Literal["bullish", "bearish"]] = None,
    date_range: Optional[tuple] = None,
    merged: bool = False
) -> List[Dict]:
    """
    Query feedback entries.
    
    Args:
        instrument: Optional instrument filter
        timeframe: Optional timeframe filter (ignored if merged=True)
        pattern_type: Optional pattern type filter
        date_range: Optional tuple of (start_date, end_date) in YYYY-MM-DD format
        merged: If True, return merged feedback (ignores timeframe)
        
    Returns:
        List of feedback dictionaries matching criteria
    """
    feedback_list = []
    
    if merged:
        # Search in merged directory
        if pattern_type:
            search_dirs = [ENGULFING_FEEDBACK_MERGED_DIR / pattern_type]
        else:
            search_dirs = [
                ENGULFING_FEEDBACK_MERGED_DIR / "bullish",
                ENGULFING_FEEDBACK_MERGED_DIR / "bearish"
            ]
    else:
        # Search in timeframe-specific directories
        if timeframe:
            normalized_tf = normalize_timeframe(timeframe)
            timeframes = [normalized_tf]
        else:
            timeframes = [normalize_timeframe(tf) for tf in SUPPORTED_TIMEFRAMES]
        
        search_dirs = []
        for tf in timeframes:
            if pattern_type:
                search_dirs.append(ENGULFING_FEEDBACK_DIR / tf / pattern_type)
            else:
                search_dirs.append(ENGULFING_FEEDBACK_DIR / tf / "bullish")
                search_dirs.append(ENGULFING_FEEDBACK_DIR / tf / "bearish")
    
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        
        for filepath in search_dir.glob("*.json"):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    feedback = json.load(f)
                    
                    # Apply filters
                    if instrument and feedback.get("instrument") != instrument:
                        continue
                    if timeframe and not merged and feedback.get("timeframe") != normalize_timeframe(timeframe):
                        continue
                    if pattern_type and feedback.get("pattern_type") != pattern_type:
                        continue
                    if date_range:
                        feedback_date = datetime.strptime(feedback.get("date", ""), "%Y-%m-%d")
                        start_date = datetime.strptime(date_range[0], "%Y-%m-%d")
                        end_date = datetime.strptime(date_range[1], "%Y-%m-%d")
                        if not (start_date <= feedback_date <= end_date):
                            continue
                    
                    feedback_list.append(feedback)
            except Exception as e:
                logger.warning(f"Error reading feedback file {filepath}: {e}")
                continue
    
    # Sort by timestamp (newest first)
    feedback_list.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return feedback_list


def get_feedback_statistics(
    timeframe: Optional[str] = None,
    pattern_type: Optional[Literal["bullish", "bearish"]] = None,
    instrument: Optional[str] = None,
    use_merged: bool = True
) -> Dict:
    """
    Get statistics about feedback patterns.
    
    Args:
        timeframe: Optional timeframe filter (ignored if use_merged=True)
        pattern_type: Optional pattern type filter
        instrument: Optional instrument filter
        use_merged: If True, use merged feedback (default: True)
        
    Returns:
        Dictionary with feedback statistics
    """
    if use_merged:
        feedback_list = get_merged_feedback(instrument=instrument, pattern_type=pattern_type)
    else:
        feedback_list = get_feedback(instrument=instrument, timeframe=timeframe, pattern_type=pattern_type, merged=False)
    
    if not feedback_list:
        return {
            "total_count": 0,
            "average_rating": 0.0,
            "position_distribution": {},
            "metric_statistics": {}
        }
    
    total_count = len(feedback_list)
    average_rating = sum(f.get("rating", 0) for f in feedback_list) / total_count
    
    # Position distribution
    position_counts = defaultdict(int)
    for f in feedback_list:
        pos = f.get("metrics", {}).get("body_position", "unknown")
        position_counts[pos] += 1
    
    # Metric statistics
    metric_stats = {}
    numeric_metrics = ["body_size_ratio", "body_overlap_percentage", "whole_body_overlap_percentage", "mc1_body_size", "mc2_body_size"]
    for key in numeric_metrics:
        values = [
            f.get("metrics", {}).get(key, 0)
            for f in feedback_list
            if isinstance(f.get("metrics", {}).get(key), (int, float))
        ]
        if values:
            metric_stats[key] = {
                "mean": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "count": len(values)
            }
    
    return {
        "total_count": total_count,
        "average_rating": round(average_rating, 2),
        "position_distribution": dict(position_counts),
        "metric_statistics": metric_stats
    }


def get_merged_feedback(
    instrument: Optional[str] = None,
    pattern_type: Optional[Literal["bullish", "bearish"]] = None,
    date_range: Optional[tuple] = None
) -> List[Dict]:
    """
    Get merged feedback (convenience wrapper).
    
    Args:
        instrument: Optional instrument filter
        pattern_type: Optional pattern type filter
        date_range: Optional tuple of (start_date, end_date)
        
    Returns:
        List of merged feedback dictionaries
    """
    return get_feedback(
        instrument=instrument,
        pattern_type=pattern_type,
        date_range=date_range,
        merged=True
    )

