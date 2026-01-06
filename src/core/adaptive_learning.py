"""
Adaptive learning from feedback data.

Analyzes feedback patterns to identify successful characteristics and
adjusts detection thresholds and similarity scoring accordingly.
"""
import logging
from typing import Dict, List, Optional, Literal
from collections import defaultdict
from statistics import mean, stdev

from .engulfing_feedback import get_feedback, get_merged_feedback

logger = logging.getLogger("candle_analysis_api")


def learn_from_feedback(
    timeframe: Optional[str] = None,
    pattern_type: Optional[Literal["bullish", "bearish"]] = None,
    use_merged: bool = True
) -> Dict:
    """
    Analyze feedback to learn patterns from high-rated vs low-rated entries.
    
    Args:
        timeframe: Optional timeframe filter (ignored if use_merged=True)
        pattern_type: Optional pattern type filter
        use_merged: If True, use merged feedback (default: True)
        
    Returns:
        Dictionary with learned patterns and characteristics
    """
    # Get all feedback
    if use_merged:
        all_feedback = get_merged_feedback(pattern_type=pattern_type)
    else:
        all_feedback = get_feedback(timeframe=timeframe, pattern_type=pattern_type, merged=False)
    
    if not all_feedback:
        return {
            "high_rated_patterns": {},
            "low_rated_patterns": {},
            "characteristics": {},
            "sample_size": 0
        }
    
    # Separate high-rated (8-10) and low-rated (1-3) feedback
    high_rated = [f for f in all_feedback if 8 <= f.get("rating", 0) <= 10]
    low_rated = [f for f in all_feedback if 1 <= f.get("rating", 0) <= 3]
    
    learned = {
        "high_rated_patterns": {},
        "low_rated_patterns": {},
        "characteristics": {},
        "sample_size": {
            "total": len(all_feedback),
            "high_rated": len(high_rated),
            "low_rated": len(low_rated)
        }
    }
    
    if not high_rated and not low_rated:
        return learned
    
    # Analyze metrics for high-rated patterns
    if high_rated:
        high_metrics = [f.get("metrics", {}) for f in high_rated]
        learned["high_rated_patterns"] = _analyze_metrics_distribution(high_metrics)
    
    # Analyze metrics for low-rated patterns
    if low_rated:
        low_metrics = [f.get("metrics", {}) for f in low_rated]
        learned["low_rated_patterns"] = _analyze_metrics_distribution(low_metrics)
    
    # Compare characteristics
    if high_rated and low_rated:
        learned["characteristics"] = _compare_characteristics(
            learned["high_rated_patterns"],
            learned["low_rated_patterns"]
        )
    
    return learned


def _analyze_metrics_distribution(metrics_list: List[Dict]) -> Dict:
    """Analyze distribution of metrics from a list of feedback entries."""
    if not metrics_list:
        return {}
    
    analysis = {}
    
    # Get all metric keys
    all_keys = set()
    for metrics in metrics_list:
        all_keys.update(metrics.keys())
    
    for key in all_keys:
        values = []
        for metrics in metrics_list:
            value = metrics.get(key)
            if value is not None:
                if isinstance(value, (int, float)):
                    values.append(value)
                elif isinstance(value, dict):
                    # Handle nested dictionaries (wick ratios, context)
                    continue
        
        if values:
            analysis[key] = {
                "mean": mean(values),
                "stdev": stdev(values) if len(values) > 1 else 0.0,
                "min": min(values),
                "max": max(values),
                "count": len(values)
            }
        
        # Handle categorical data (body_position)
        if key == "body_position":
            position_counts = defaultdict(int)
            for metrics in metrics_list:
                pos = metrics.get(key, "unknown")
                position_counts[pos] += 1
            analysis[key] = {
                "distribution": dict(position_counts),
                "most_common": max(position_counts.items(), key=lambda x: x[1])[0] if position_counts else None
            }
    
    return analysis


def _compare_characteristics(high_patterns: Dict, low_patterns: Dict) -> Dict:
    """Compare characteristics between high-rated and low-rated patterns."""
    characteristics = {}
    
    # Compare numeric metrics
    for key in set(high_patterns.keys()) | set(low_patterns.keys()):
        if key == "body_position":
            # Compare position distributions
            high_pos = high_patterns.get(key, {}).get("distribution", {})
            low_pos = low_patterns.get(key, {}).get("distribution", {})
            characteristics[key] = {
                "high_rated_common": high_patterns.get(key, {}).get("most_common"),
                "low_rated_common": low_patterns.get(key, {}).get("most_common"),
                "difference": "High-rated patterns tend to have different position distribution"
            }
        elif isinstance(high_patterns.get(key), dict) and "mean" in high_patterns[key]:
            high_mean = high_patterns[key].get("mean", 0)
            low_mean = low_patterns.get(key, {}).get("mean", 0)
            diff = high_mean - low_mean
            characteristics[key] = {
                "high_rated_mean": high_mean,
                "low_rated_mean": low_mean,
                "difference": diff,
                "significance": "significant" if abs(diff) > (high_patterns[key].get("stdev", 0) or 1.0) else "moderate"
            }
    
    return characteristics


def adjust_detection_thresholds(learned_patterns: Dict) -> Dict:
    """
    Adjust detection thresholds based on learned patterns.
    
    Args:
        learned_patterns: Learned patterns from learn_from_feedback()
        
    Returns:
        Dictionary with adjusted thresholds
    """
    thresholds = {
        "body_size_ratio_min": None,
        "body_size_ratio_max": None,
        "body_overlap_min": None,
        "preferred_positions": []
    }
    
    characteristics = learned_patterns.get("characteristics", {})
    high_patterns = learned_patterns.get("high_rated_patterns", {})
    
    # Adjust body size ratio threshold
    if "body_size_ratio" in high_patterns:
        high_mean = high_patterns["body_size_ratio"].get("mean", 0)
        high_stdev = high_patterns["body_size_ratio"].get("stdev", 0)
        thresholds["body_size_ratio_min"] = max(0, high_mean - high_stdev)
        thresholds["body_size_ratio_max"] = high_mean + high_stdev
    
    # Adjust body overlap threshold
    if "body_overlap_percentage" in high_patterns:
        high_mean = high_patterns["body_overlap_percentage"].get("mean", 0)
        thresholds["body_overlap_min"] = max(0, high_mean - high_patterns["body_overlap_percentage"].get("stdev", 0))
    
    # Preferred positions
    if "body_position" in high_patterns:
        distribution = high_patterns["body_position"].get("distribution", {})
        if distribution:
            # Get positions that appear in at least 20% of high-rated patterns
            total = sum(distribution.values())
            for position, count in distribution.items():
                if count / total >= 0.2:
                    thresholds["preferred_positions"].append(position)
    
    return thresholds


def calculate_adaptive_similarity(
    current_metrics: Dict,
    historical_feedback: List[Dict],
    learned_patterns: Optional[Dict] = None
) -> float:
    """
    Calculate similarity score using adaptive learning.
    
    Args:
        current_metrics: Metrics for the current pattern
        historical_feedback: List of historical feedback entries
        learned_patterns: Optional learned patterns (if None, will learn from feedback)
        
    Returns:
        Similarity score between 0.0 and 1.0
    """
    if not historical_feedback:
        return 0.0
    
    if learned_patterns is None:
        learned_patterns = learn_from_feedback()
    
    # Calculate base similarity scores
    similarities = []
    for feedback in historical_feedback:
        feedback_metrics = feedback.get("metrics", {})
        similarity = _calculate_metrics_similarity(current_metrics, feedback_metrics)
        
        # Weight by rating
        rating = feedback.get("rating", 5)
        weighted_similarity = similarity * (rating / 10.0)
        
        # Boost if matches learned high-rated characteristics
        if learned_patterns:
            boost = _calculate_characteristics_boost(current_metrics, learned_patterns)
            weighted_similarity *= (1.0 + boost * 0.2)  # Up to 20% boost
        
        similarities.append(weighted_similarity)
    
    # Return average similarity
    if similarities:
        return min(1.0, sum(similarities) / len(similarities))
    return 0.0


def _calculate_metrics_similarity(metrics1: Dict, metrics2: Dict) -> float:
    """Calculate similarity between two metrics dictionaries."""
    if not metrics1 or not metrics2:
        return 0.0
    
    similarities = []
    
    # Compare numeric metrics
    numeric_keys = ["body_size_ratio", "body_overlap_percentage", "mc1_body_size", "mc2_body_size"]
    for key in numeric_keys:
        if key in metrics1 and key in metrics2:
            val1 = metrics1[key]
            val2 = metrics2[key]
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                if val1 == 0 and val2 == 0:
                    similarity = 1.0
                elif val1 == 0 or val2 == 0:
                    similarity = 0.0
                else:
                    # Normalized difference
                    max_val = max(abs(val1), abs(val2))
                    diff = abs(val1 - val2) / max_val
                    similarity = 1.0 - min(1.0, diff)
                    similarities.append(similarity)
    
    # Compare categorical metrics
    if "body_position" in metrics1 and "body_position" in metrics2:
        if metrics1["body_position"] == metrics2["body_position"]:
            similarities.append(1.0)
        else:
            similarities.append(0.0)
    
    # Compare wick ratios
    for wick_key in ["mc1_wick_ratios", "mc2_wick_ratios"]:
        if wick_key in metrics1 and wick_key in metrics2:
            wick1 = metrics1[wick_key]
            wick2 = metrics2[wick_key]
            if isinstance(wick1, dict) and isinstance(wick2, dict):
                for subkey in ["upper_wick_ratio", "lower_wick_ratio"]:
                    if subkey in wick1 and subkey in wick2:
                        val1 = wick1[subkey]
                        val2 = wick2[subkey]
                        if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                            max_val = max(abs(val1), abs(val2), 0.001)
                            diff = abs(val1 - val2) / max_val
                            similarity = 1.0 - min(1.0, diff)
                            similarities.append(similarity)
    
    if similarities:
        return sum(similarities) / len(similarities)
    return 0.0


def _calculate_characteristics_boost(current_metrics: Dict, learned_patterns: Dict) -> float:
    """Calculate boost factor if current metrics match learned high-rated characteristics."""
    boost = 0.0
    characteristics = learned_patterns.get("characteristics", {})
    high_patterns = learned_patterns.get("high_rated_patterns", {})
    
    # Check body position
    if "body_position" in characteristics:
        preferred = characteristics["body_position"].get("high_rated_common")
        if preferred and current_metrics.get("body_position") == preferred:
            boost += 0.5
    
    # Check body size ratio
    if "body_size_ratio" in high_patterns:
        high_mean = high_patterns["body_size_ratio"].get("mean", 0)
        high_stdev = high_patterns["body_size_ratio"].get("stdev", 1.0)
        current_ratio = current_metrics.get("body_size_ratio", 0)
        if abs(current_ratio - high_mean) <= high_stdev:
            boost += 0.3
    
    # Check body overlap
    if "body_overlap_percentage" in high_patterns:
        high_mean = high_patterns["body_overlap_percentage"].get("mean", 0)
        current_overlap = current_metrics.get("body_overlap_percentage", 0)
        if current_overlap >= high_mean * 0.8:  # Within 80% of high-rated mean
            boost += 0.2
    
    return min(1.0, boost)




