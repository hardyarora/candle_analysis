"""
Timeframe normalization utilities.

Handles various timeframe formats and normalizes them to a standard format.
Supports: D/1D/1d -> 1D, 2D/2d -> 2D, etc.
"""
from typing import Tuple


def normalize_timeframe(timeframe: str) -> str:
    """
    Normalize timeframe string to standard format (e.g., 1D, 2D, 3D, 4D).
    
    Supports:
    - D, 1D, 1d -> 1D
    - 2D, 2d -> 2D
    - 3D, 3d -> 3D
    - 4D, 4d -> 4D
    
    Args:
        timeframe: Timeframe string in various formats
        
    Returns:
        Normalized timeframe string (e.g., "1D", "2D", "3D", "4D")
        
    Raises:
        ValueError: If timeframe format is invalid or not supported
    """
    if not timeframe:
        raise ValueError("Timeframe cannot be empty")
    
    tf = timeframe.strip().upper()
    
    # Handle single 'D' as '1D'
    if tf == "D":
        return "1D"
    
    # Handle numeric prefix with D (e.g., 1D, 2D, 3D, 4D)
    if tf.endswith("D"):
        prefix = tf[:-1]
        if prefix.isdigit():
            num = int(prefix)
            if 1 <= num <= 4:
                return f"{num}D"
            else:
                raise ValueError(f"Timeframe must be between 1D and 4D, got {tf}")
        else:
            raise ValueError(f"Invalid timeframe format: {timeframe}")
    
    # If we get here, it's an unsupported format
    raise ValueError(f"Unsupported timeframe format: {timeframe}. Expected D, 1D-4D (case insensitive)")


def parse_timeframe(timeframe: str) -> Tuple[str, int]:
    """
    Parse timeframe string into granularity and candle count.
    
    For daily timeframes (1D-4D), returns ("D", count).
    
    Args:
        timeframe: Normalized timeframe string (e.g., "1D", "2D")
        
    Returns:
        Tuple of (granularity, n_candles) where:
        - granularity: "D" for daily
        - n_candles: Number of candles to merge (1-4)
        
    Raises:
        ValueError: If timeframe is invalid
    """
    normalized = normalize_timeframe(timeframe)
    
    # Extract number from normalized timeframe (e.g., "1D" -> 1)
    if normalized.endswith("D"):
        count_str = normalized[:-1]
        if count_str.isdigit():
            count = int(count_str)
            return ("D", count)
    
    raise ValueError(f"Failed to parse timeframe: {timeframe}")


def is_valid_timeframe(timeframe: str) -> bool:
    """
    Check if a timeframe string is valid.
    
    Args:
        timeframe: Timeframe string to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        normalize_timeframe(timeframe)
        return True
    except ValueError:
        return False
