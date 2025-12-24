"""
File management for candle analysis data.

Handles saving, loading, and backing up analysis results.
"""
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .config import LATEST_DIR, BACKUPS_DIR
from ..utils.timeframe import normalize_timeframe


def backup_current_analysis(timeframe: str, backup_date: Optional[str] = None) -> Path:
    """
    Move current analysis data from latest/{timeframe} to backups/{date}/{timeframe}/.
    
    Args:
        timeframe: Normalized timeframe (e.g., "1D", "2D")
        backup_date: Date string in YYYY-MM-DD format. If None, uses today's date.
        
    Returns:
        Path to the backup directory
        
    Raises:
        ValueError: If timeframe is invalid
    """
    normalized_tf = normalize_timeframe(timeframe)
    
    if backup_date is None:
        backup_date = datetime.now().strftime("%Y-%m-%d")
    
    # Source: data/latest/{timeframe}/
    source_dir = LATEST_DIR / normalized_tf
    
    # Destination: data/backups/{date}/{timeframe}/
    backup_dir = BACKUPS_DIR / backup_date / normalized_tf
    
    # Create backup directory
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # If source exists and has files, move them
    if source_dir.exists() and any(source_dir.iterdir()):
        # Move all files from source to backup
        for item in source_dir.iterdir():
            if item.is_file():
                shutil.move(str(item), str(backup_dir / item.name))
        
        # Remove empty source directory
        try:
            source_dir.rmdir()
        except OSError:
            # Directory not empty or doesn't exist, that's fine
            pass
    
    return backup_dir


def save_analysis(analysis_data: Dict, timeframe: str) -> Path:
    """
    Save analysis data to latest/{timeframe}/ directory.
    
    Creates a JSON file with timestamp in the filename.
    
    Args:
        analysis_data: Dictionary containing analysis results
        timeframe: Normalized timeframe (e.g., "1D", "2D")
        
    Returns:
        Path to the saved JSON file
        
    Raises:
        ValueError: If timeframe is invalid
    """
    normalized_tf = normalize_timeframe(timeframe)
    
    # Ensure latest directory exists
    output_dir = LATEST_DIR / normalized_tf
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"analysis_{normalized_tf}_{timestamp}.json"
    filepath = output_dir / filename
    
    # Save JSON file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(analysis_data, f, indent=2, ensure_ascii=False)
    
    return filepath


def list_backup_dates(timeframe: str) -> List[str]:
    """
    List all available backup dates for a given timeframe.
    
    Args:
        timeframe: Normalized timeframe (e.g., "1D", "2D")
        
    Returns:
        Sorted list of date strings (YYYY-MM-DD format) that have backups
        
    Raises:
        ValueError: If timeframe is invalid
    """
    normalized_tf = normalize_timeframe(timeframe)
    
    backup_dates = []
    
    # Check each date directory in backups/
    if BACKUPS_DIR.exists():
        for date_dir in BACKUPS_DIR.iterdir():
            if date_dir.is_dir():
                # Check if this date has data for the timeframe
                tf_dir = date_dir / normalized_tf
                if tf_dir.exists() and any(tf_dir.glob("*.json")):
                    backup_dates.append(date_dir.name)
    
    # Sort dates (newest first)
    backup_dates.sort(reverse=True)
    
    return backup_dates


def load_analysis(timeframe: str, date: Optional[str] = None) -> Optional[Dict]:
    """
    Load analysis data from latest or backup directory.
    
    Args:
        timeframe: Normalized timeframe (e.g., "1D", "2D")
        date: Date string in YYYY-MM-DD format. If None, loads from latest.
        
    Returns:
        Analysis data dictionary or None if not found
        
    Raises:
        ValueError: If timeframe is invalid
    """
    normalized_tf = normalize_timeframe(timeframe)
    
    if date is None:
        # Load from latest
        source_dir = LATEST_DIR / normalized_tf
    else:
        # Load from backup
        source_dir = BACKUPS_DIR / date / normalized_tf
    
    if not source_dir.exists():
        return None
    
    # Find the most recent JSON file
    json_files = sorted(source_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    if not json_files:
        return None
    
    # Load the most recent file
    with open(json_files[0], 'r', encoding='utf-8') as f:
        return json.load(f)


def get_current_analysis_date(timeframe: str) -> Optional[str]:
    """
    Get the date of the current analysis in latest directory.
    
    Args:
        timeframe: Normalized timeframe (e.g., "1D", "2D")
        
    Returns:
        Date string (YYYY-MM-DD) if analysis exists, None otherwise
    """
    normalized_tf = normalize_timeframe(timeframe)
    source_dir = LATEST_DIR / normalized_tf
    
    if not source_dir.exists():
        return None
    
    json_files = sorted(source_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    if not json_files:
        return None
    
    # Extract date from filename or use file modification time
    # Filename format: analysis_{tf}_{timestamp}.json
    # We'll use the file's modification time
    mtime = json_files[0].stat().st_mtime
    file_date = datetime.fromtimestamp(mtime)
    return file_date.strftime("%Y-%m-%d")


def list_available_dates(timeframe: str) -> Dict[str, List[str]]:
    """
    List all available dates (current + backups) for a timeframe.
    
    Args:
        timeframe: Normalized timeframe (e.g., "1D", "2D")
        
    Returns:
        Dictionary with:
        - "current": List with current date if exists, empty otherwise
        - "backups": List of backup dates
    """
    normalized_tf = normalize_timeframe(timeframe)
    
    result = {
        "current": [],
        "backups": []
    }
    
    # Check current
    current_date = get_current_analysis_date(normalized_tf)
    if current_date:
        result["current"] = [current_date]
    
    # Get backups
    result["backups"] = list_backup_dates(normalized_tf)
    
    return result
