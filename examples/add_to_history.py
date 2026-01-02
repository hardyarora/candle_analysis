"""
Script to add currency categorization data into historical storage.

Reads currency_by_date.json and stores each date's data as a historical snapshot
for the strength_weakness_weekly endpoint.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

# Add src to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.history_storage import store_snapshot

def transform_date_data(date: str, date_data: dict) -> dict:
    """
    Transform date-specific data to match API response format.
    
    Args:
        date: Date string in YYYY-MM-DD format
        date_data: Dictionary with 'currencies' and 'summary' keys
        
    Returns:
        Dictionary matching StrengthWeaknessCategorizationResponse format
    """
    # Create timestamp for the date (end of day)
    date_obj = datetime.strptime(date, "%Y-%m-%d")
    timestamp = date_obj.replace(hour=23, minute=59, second=59).isoformat()
    
    # Transform summary to match API format
    summary = {
        "by_strength": date_data["summary"]["by_strength"],
        "by_weakness": date_data["summary"]["by_weakness"]
    }
    
    # Build response matching API format
    response_data = {
        "timestamp": timestamp,
        "currency_filter": None,
        "ignore_candles": 0,
        "period": "weekly",
        "currencies": date_data["currencies"],
        "summary": summary
    }
    
    return response_data

def add_to_history(input_file: str = "currency_by_date.json", endpoint: str = "strength_weakness_weekly"):
    """
    Read currency data by date and store as historical snapshots.
    
    Args:
        input_file: Path to JSON file with date-keyed currency data
        endpoint: Endpoint identifier for historical storage
    """
    input_path = Path(input_file)
    
    if not input_path.exists():
        print(f"Error: File not found: {input_file}")
        return
    
    # Read the data
    with open(input_path, 'r') as f:
        all_data = json.load(f)
    
    print(f"Found {len(all_data)} dates in {input_file}")
    print(f"Storing as historical snapshots for endpoint: {endpoint}\n")
    
    stored_count = 0
    skipped_count = 0
    
    for date, date_data in sorted(all_data.items()):
        # Validate date format
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            print(f"Warning: Skipping invalid date format: {date}")
            skipped_count += 1
            continue
        
        # Check if data has required structure
        if "currencies" not in date_data or "summary" not in date_data:
            print(f"Warning: Skipping {date} - missing required fields")
            skipped_count += 1
            continue
        
        # Transform to API response format
        response_data = transform_date_data(date, date_data)
        
        # Store snapshot
        try:
            filepath = store_snapshot(endpoint, response_data, date=date)
            print(f"✓ Stored snapshot for {date} -> {filepath}")
            stored_count += 1
        except Exception as e:
            print(f"✗ Error storing {date}: {e}")
            skipped_count += 1
    
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Stored: {stored_count} snapshots")
    print(f"  Skipped: {skipped_count} dates")
    print(f"{'='*60}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Add currency categorization data to historical storage")
    parser.add_argument(
        "--input",
        default="currency_by_date.json",
        help="Input JSON file with date-keyed currency data (default: currency_by_date.json)"
    )
    parser.add_argument(
        "--endpoint",
        default="strength_weakness_weekly",
        help="Endpoint identifier for storage (default: strength_weakness_weekly)"
    )
    
    args = parser.parse_args()
    
    add_to_history(args.input, args.endpoint)

