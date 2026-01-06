"""
Metrics calculation for engulfing candle patterns.

Calculates various metrics to characterize engulfing patterns including
body ratios, position analysis, wick ratios, and context metrics.
"""
import logging
from typing import Dict, List, Optional, Literal

logger = logging.getLogger("candle_analysis_api")


def calculate_body_size(candle: Dict) -> float:
    """
    Calculate the body size of a candle.
    
    Args:
        candle: Candle dictionary with 'open' and 'close' keys
        
    Returns:
        Body size as absolute difference between open and close
    """
    open_price = float(candle.get("open", 0))
    close_price = float(candle.get("close", 0))
    return abs(close_price - open_price)


def calculate_body_ratio(mc1_body_size: float, mc2_body_size: float) -> float:
    """
    Calculate the ratio of previous candle body size to new candle body size.
    
    Args:
        mc1_body_size: Previous candle body size
        mc2_body_size: New candle body size
        
    Returns:
        Ratio (mc1_body_size / mc2_body_size), or 0.0 if mc2_body_size is 0
    """
    if mc2_body_size == 0:
        return 0.0
    return mc1_body_size / mc2_body_size


def calculate_body_position(
    mc1_open: float,
    mc2_body_top: float,
    mc2_body_bottom: float,
    pattern_type: Literal["bullish", "bearish"]
) -> str:
    """
    Calculate the position of previous candle's open relative to new candle's body.
    
    For bearish engulfing: position of mc1_open relative to mc2 body
    For bullish engulfing: position of mc1_open relative to mc2 body
    
    Args:
        mc1_open: Previous candle's open price
        mc2_body_top: New candle's body top (max of open/close)
        mc2_body_bottom: New candle's body bottom (min of open/close)
        pattern_type: "bullish" or "bearish"
        
    Returns:
        Position category: "top_25%", "upper_middle", "lower_middle", "bottom_25%", or "outside"
    """
    if mc2_body_top == mc2_body_bottom:
        return "lower_middle"  # No body, treat as lower middle
    
    body_range = mc2_body_top - mc2_body_bottom
    position_from_bottom = mc1_open - mc2_body_bottom
    position_percentage = (position_from_bottom / body_range) * 100
    
    if position_percentage >= 75:
        return "top_25%"
    elif position_percentage >= 50:
        return "upper_middle"
    elif position_percentage >= 25:
        return "lower_middle"
    elif position_percentage >= 0:
        return "bottom_25%"
    else:
        return "outside"


def calculate_body_overlap(mc1: Dict, mc2: Dict) -> float:
    """
    Calculate the percentage of combined body range that overlaps.
    
    The overlap percentage is calculated as the overlap size divided by
    the total combined range of both candle bodies.
    
    Args:
        mc1: Previous candle dictionary
        mc2: New candle dictionary
        
    Returns:
        Overlap percentage (0.0 to 100.0)
    """
    mc1_open = float(mc1.get("open", 0))
    mc1_close = float(mc1.get("close", 0))
    mc2_open = float(mc2.get("open", 0))
    mc2_close = float(mc2.get("close", 0))
    
    mc1_body_top = max(mc1_open, mc1_close)
    mc1_body_bottom = min(mc1_open, mc1_close)
    mc2_body_top = max(mc2_open, mc2_close)
    mc2_body_bottom = min(mc2_open, mc2_close)
    
    # Calculate overlap
    overlap_top = min(mc1_body_top, mc2_body_top)
    overlap_bottom = max(mc1_body_bottom, mc2_body_bottom)
    
    if overlap_top <= overlap_bottom:
        return 0.0
    
    overlap_size = overlap_top - overlap_bottom
    
    # Calculate total combined range of both bodies
    total_combined_top = max(mc1_body_top, mc2_body_top)
    total_combined_bottom = min(mc1_body_bottom, mc2_body_bottom)
    total_combined_range = total_combined_top - total_combined_bottom
    
    if total_combined_range == 0:
        return 0.0
    
    return (overlap_size / total_combined_range) * 100.0


def calculate_whole_body_position(
    mc1_close: float,
    mc2_low: float,
    mc2_high: float,
    pattern_type: Literal["bullish", "bearish"]
) -> str:
    """
    Calculate the position of previous candle's close relative to new candle's full range (high/low).
    
    Args:
        mc1_close: Previous candle's close price
        mc2_low: New candle's low price
        mc2_high: New candle's high price
        pattern_type: "bullish" or "bearish"
        
    Returns:
        Position category: "top_25%", "upper_middle", "lower_middle", "bottom_25%", or "outside"
    """
    if mc2_high == mc2_low:
        return "lower_middle"  # No range, treat as lower middle
    
    candle_range = mc2_high - mc2_low
    position_from_bottom = mc1_close - mc2_low
    position_percentage = (position_from_bottom / candle_range) * 100
    
    # Check if outside the range
    if position_percentage > 100:
        return "outside"  # Above mc2_high
    elif position_percentage < 0:
        return "outside"  # Below mc2_low
    elif position_percentage >= 75:
        return "top_25%"
    elif position_percentage >= 50:
        return "upper_middle"
    elif position_percentage >= 25:
        return "lower_middle"
    else:
        return "bottom_25%"


def calculate_whole_body_overlap_percentage(mc1: Dict, mc2: Dict) -> float:
    """
    Calculate the percentage of previous candle's full range (high/low) that overlaps 
    with new candle's full range (high/low).
    
    Args:
        mc1: Previous candle dictionary
        mc2: New candle dictionary
        
    Returns:
        Overlap percentage (0.0 to 100.0)
    """
    mc1_high = float(mc1.get("high", 0))
    mc1_low = float(mc1.get("low", 0))
    mc2_high = float(mc2.get("high", 0))
    mc2_low = float(mc2.get("low", 0))
    
    # Calculate overlap of full candle ranges
    overlap_top = min(mc1_high, mc2_high)
    overlap_bottom = max(mc1_low, mc2_low)
    
    if overlap_top <= overlap_bottom:
        return 0.0
    
    overlap_size = overlap_top - overlap_bottom
    mc1_range = mc1_high - mc1_low
    
    if mc1_range == 0:
        return 0.0
    
    return (overlap_size / mc1_range) * 100.0


def calculate_wick_ratios(candle: Dict) -> Dict[str, float]:
    """
    Calculate upper and lower wick ratios relative to body size.
    
    Args:
        candle: Candle dictionary with 'open', 'close', 'high', 'low'
        
    Returns:
        Dictionary with 'upper_wick_ratio' and 'lower_wick_ratio'
    """
    open_price = float(candle.get("open", 0))
    close_price = float(candle.get("close", 0))
    high = float(candle.get("high", 0))
    low = float(candle.get("low", 0))
    
    body_size = abs(close_price - open_price)
    body_top = max(open_price, close_price)
    body_bottom = min(open_price, close_price)
    
    upper_wick = high - body_top
    lower_wick = body_bottom - low
    
    if body_size == 0:
        return {
            "upper_wick_ratio": 0.0,
            "lower_wick_ratio": 0.0
        }
    
    return {
        "upper_wick_ratio": upper_wick / body_size,
        "lower_wick_ratio": lower_wick / body_size
    }


def calculate_context_metrics(
    candles: Optional[List[Dict]] = None,
    trend_data: Optional[Dict] = None
) -> Dict:
    """
    Calculate context metrics such as trend direction and volatility.
    
    Args:
        candles: Optional list of recent candles for trend calculation
        trend_data: Optional pre-calculated trend data
        
    Returns:
        Dictionary with context metrics (trend, volatility, etc.)
    """
    context = {
        "trend": "unknown",
        "volatility": None,
        "volume": None
    }
    
    # Simple trend calculation from recent candles if provided
    if candles and len(candles) >= 2:
        recent_closes = [float(c.get("close", 0)) for c in candles[-5:]]
        if len(recent_closes) >= 2:
            if recent_closes[-1] > recent_closes[0]:
                context["trend"] = "uptrend"
            elif recent_closes[-1] < recent_closes[0]:
                context["trend"] = "downtrend"
            else:
                context["trend"] = "sideways"
    
    # Use provided trend data if available
    if trend_data:
        if "trend" in trend_data:
            context["trend"] = trend_data["trend"]
        if "volatility" in trend_data:
            context["volatility"] = trend_data["volatility"]
        if "volume" in trend_data:
            context["volume"] = trend_data["volume"]
    
    return context


def calculate_engulfing_metrics(
    mc1: Dict,
    mc2: Dict,
    pattern_type: Literal["bullish", "bearish"],
    context: Optional[Dict] = None
) -> Dict:
    """
    Calculate comprehensive metrics for an engulfing pattern.
    
    Args:
        mc1: Previous candle dictionary
        mc2: New candle dictionary (engulfing candle)
        pattern_type: "bullish" or "bearish"
        context: Optional context dictionary with trend/volatility info
        
    Returns:
        Dictionary with all calculated metrics:
        - body_size_ratio: Ratio of mc1 body to mc2 body
        - body_position: Position category of mc1_open relative to mc2 body
        - body_overlap_percentage: Overlap percentage of bodies
        - whole_body_position: Position category of mc1_close relative to mc2 full range
        - whole_body_overlap_percentage: Overlap percentage of full candle ranges
        - mc1_wick_ratios: Wick ratios for previous candle
        - mc2_wick_ratios: Wick ratios for new candle
        - context: Context metrics (trend, volatility, etc.)
    """
    # Calculate body sizes
    mc1_body_size = calculate_body_size(mc1)
    mc2_body_size = calculate_body_size(mc2)
    
    # Calculate body ratio
    body_size_ratio = calculate_body_ratio(mc1_body_size, mc2_body_size)
    
    # Calculate position (body-based)
    mc2_body_top = max(float(mc2.get("open", 0)), float(mc2.get("close", 0)))
    mc2_body_bottom = min(float(mc2.get("open", 0)), float(mc2.get("close", 0)))
    mc1_open = float(mc1.get("open", 0))
    
    body_position = calculate_body_position(
        mc1_open,
        mc2_body_top,
        mc2_body_bottom,
        pattern_type
    )
    
    # Calculate whole body position (from mc2 low)
    mc1_close = float(mc1.get("close", 0))
    mc2_low = float(mc2.get("low", 0))
    mc2_high = float(mc2.get("high", 0))
    
    whole_body_position = calculate_whole_body_position(
        mc1_close,
        mc2_low,
        mc2_high,
        pattern_type
    )
    
    # Calculate overlap (body-based)
    body_overlap_percentage = calculate_body_overlap(mc1, mc2)
    
    # Calculate whole body overlap (full candle ranges)
    whole_body_overlap_percentage = calculate_whole_body_overlap_percentage(mc1, mc2)
    
    # Calculate wick ratios
    mc1_wick_ratios = calculate_wick_ratios(mc1)
    mc2_wick_ratios = calculate_wick_ratios(mc2)
    
    # Calculate context metrics
    context_metrics = calculate_context_metrics(trend_data=context)
    
    return {
        "body_size_ratio": body_size_ratio,
        "body_position": body_position,
        "body_overlap_percentage": body_overlap_percentage,
        "whole_body_position": whole_body_position,
        "whole_body_overlap_percentage": whole_body_overlap_percentage,
        "mc1_wick_ratios": mc1_wick_ratios,
        "mc2_wick_ratios": mc2_wick_ratios,
        "context": context_metrics,
        "mc1_body_size": mc1_body_size,
        "mc2_body_size": mc2_body_size
    }

