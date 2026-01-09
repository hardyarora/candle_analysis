"""
Historical data storage for API endpoint responses.

Handles storing and retrieving historical snapshots of API endpoint responses.
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from .config import DATA_DIR

logger = logging.getLogger("candle_analysis_api.history")

# History storage directory
HISTORY_DIR = DATA_DIR / "history"


def ensure_history_dir() -> Path:
    """
    Ensure the history directory exists.
    
    Returns:
        Path to the history directory
    """
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return HISTORY_DIR


def store_snapshot(endpoint: str, data: Dict, date: Optional[str] = None) -> Path:
    """
    Store a snapshot of endpoint data.
    
    Args:
        endpoint: Endpoint identifier (e.g., "strength_weakness_weekly")
        data: Response data dictionary to store
        date: Date string in YYYY-MM-DD format. If None, uses today's date.
        
    Returns:
        Path to the stored JSON file
        
    Raises:
        ValueError: If date format is invalid
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid date format: {date}. Expected YYYY-MM-DD")
    
    # Ensure history directory exists
    ensure_history_dir()
    
    # Create endpoint directory
    endpoint_dir = HISTORY_DIR / endpoint
    endpoint_dir.mkdir(parents=True, exist_ok=True)
    
    # Store with date as filename (overwrites if exists for same date)
    filepath = endpoint_dir / f"{date}.json"
    
    # Prepare snapshot data with timestamp
    snapshot = {
        "endpoint": endpoint,
        "date": date,
        "timestamp": datetime.now().isoformat(),
        "data": data
    }
    
    # Save JSON file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
    
    logger.debug(f"Stored snapshot for endpoint '{endpoint}' on date {date}")
    return filepath


def get_snapshot(endpoint: str, date: str) -> Optional[Dict]:
    """
    Retrieve a snapshot for a specific date.
    
    Args:
        endpoint: Endpoint identifier
        date: Date string in YYYY-MM-DD format
        
    Returns:
        Snapshot dictionary with keys: endpoint, date, timestamp, data
        Returns None if not found
        
    Raises:
        ValueError: If date format is invalid
    """
    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid date format: {date}. Expected YYYY-MM-DD")
    
    filepath = HISTORY_DIR / endpoint / f"{date}.json"
    
    if not filepath.exists():
        return None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_snapshots_range(endpoint: str, start_date: str, end_date: str) -> List[Dict]:
    """
    Retrieve all snapshots within a date range (inclusive).
    
    Args:
        endpoint: Endpoint identifier
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        List of snapshot dictionaries, sorted by date (oldest first)
        Each snapshot has keys: endpoint, date, timestamp, data
        
    Raises:
        ValueError: If date format is invalid or start_date > end_date
    """
    # Validate date formats
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(f"Invalid date format. Expected YYYY-MM-DD: {e}")
    
    if start > end:
        raise ValueError(f"start_date ({start_date}) must be <= end_date ({end_date})")
    
    endpoint_dir = HISTORY_DIR / endpoint
    
    if not endpoint_dir.exists():
        return []
    
    snapshots = []
    current_date = start
    
    # Iterate through date range
    while current_date <= end:
        date_str = current_date.strftime("%Y-%m-%d")
        snapshot = get_snapshot(endpoint, date_str)
        if snapshot:
            snapshots.append(snapshot)
        current_date += timedelta(days=1)
    
    # Sort by date
    snapshots.sort(key=lambda x: x["date"])
    
    return snapshots


def get_last_n_days(endpoint: str, days: int = 10) -> List[Dict]:
    """
    Get last N days of snapshots.
    
    Args:
        endpoint: Endpoint identifier
        days: Number of days to retrieve (default: 10)
        
    Returns:
        List of snapshot dictionaries, sorted by date (oldest first)
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days - 1)
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    return get_snapshots_range(endpoint, start_str, end_str)


def list_dates(endpoint: str) -> List[str]:
    """
    List all available dates for an endpoint.
    
    Args:
        endpoint: Endpoint identifier
        
    Returns:
        Sorted list of date strings (YYYY-MM-DD format)
    """
    endpoint_dir = HISTORY_DIR / endpoint
    
    if not endpoint_dir.exists():
        return []
    
    dates = []
    for filepath in endpoint_dir.glob("*.json"):
        # Extract date from filename (format: YYYY-MM-DD.json)
        date_str = filepath.stem
        try:
            # Validate it's a valid date
            datetime.strptime(date_str, "%Y-%m-%d")
            dates.append(date_str)
        except ValueError:
            # Skip invalid filenames
            continue
    
    # Sort dates (oldest first)
    dates.sort()
    
    return dates


def get_latest_snapshot(endpoint: str) -> Optional[Dict]:
    """
    Get the most recent snapshot.
    
    Args:
        endpoint: Endpoint identifier
        
    Returns:
        Snapshot dictionary with keys: endpoint, date, timestamp, data
        Returns None if no snapshots exist
    """
    dates = list_dates(endpoint)
    
    if not dates:
        return None
    
    # Get the latest date (last in sorted list)
    latest_date = dates[-1]
    return get_snapshot(endpoint, latest_date)






