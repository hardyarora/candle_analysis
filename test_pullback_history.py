#!/usr/bin/env python3
"""
Test script for pullback history endpoints.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.history_storage import list_dates, get_snapshot
from src.api.routes import get_pullback_history, get_historical_pullback
from fastapi.testclient import TestClient
from src.api.main import app

def test_history_storage():
    """Test that historical data exists and can be loaded."""
    print("Testing history storage functions...")
    
    # Test weekly pullback
    endpoint_weekly = "pullback_weekly"
    dates_weekly = list_dates(endpoint_weekly)
    print(f"  Weekly pullback dates: {len(dates_weekly)} dates found")
    if dates_weekly:
        print(f"    Latest: {dates_weekly[-1]}")
        print(f"    First: {dates_weekly[0]}")
        
        # Try loading a snapshot
        latest_date = dates_weekly[-1]
        snapshot = get_snapshot(endpoint_weekly, latest_date)
        if snapshot:
            print(f"    ✓ Successfully loaded snapshot for {latest_date}")
            data = snapshot.get("data", {})
            results_count = len(data.get("results", []))
            print(f"    ✓ Snapshot contains {results_count} results")
        else:
            print(f"    ✗ Failed to load snapshot for {latest_date}")
    
    # Test monthly pullback
    endpoint_monthly = "pullback_monthly"
    dates_monthly = list_dates(endpoint_monthly)
    print(f"  Monthly pullback dates: {len(dates_monthly)} dates found")
    if dates_monthly:
        print(f"    Latest: {dates_monthly[-1]}")
        print(f"    First: {dates_monthly[0]}")
    
    print()

def test_api_endpoints():
    """Test the API endpoints using TestClient."""
    print("Testing API endpoints...")
    client = TestClient(app)
    
    # Test /pullback/history endpoint
    print("  Testing GET /api/v1/pullback/history?period=weekly")
    response = client.get("/api/v1/pullback/history?period=weekly")
    if response.status_code == 200:
        data = response.json()
        print(f"    ✓ Success: {len(data.get('dates', []))} dates available")
        print(f"    ✓ Latest date: {data.get('latest')}")
    else:
        print(f"    ✗ Failed: {response.status_code} - {response.text}")
    
    # Test /pullback/history endpoint (monthly)
    print("  Testing GET /api/v1/pullback/history?period=monthly")
    response = client.get("/api/v1/pullback/history?period=monthly")
    if response.status_code == 200:
        data = response.json()
        print(f"    ✓ Success: {len(data.get('dates', []))} dates available")
        print(f"    ✓ Latest date: {data.get('latest')}")
    else:
        print(f"    ✗ Failed: {response.status_code} - {response.text}")
    
    # Test /pullback endpoint with date parameter
    dates_weekly = list_dates("pullback_weekly")
    if dates_weekly:
        test_date = dates_weekly[-1]
        print(f"  Testing GET /api/v1/pullback?period=weekly&date={test_date}")
        response = client.get(f"/api/v1/pullback?period=weekly&date={test_date}")
        if response.status_code == 200:
            data = response.json()
            results_count = len(data.get("results", []))
            print(f"    ✓ Success: {results_count} results returned")
            print(f"    ✓ Timestamp: {data.get('timestamp')}")
        else:
            print(f"    ✗ Failed: {response.status_code} - {response.text}")
    
    # Test /pullback/{date} endpoint
    if dates_weekly:
        test_date = dates_weekly[-1]
        print(f"  Testing GET /api/v1/pullback/{test_date}?period=weekly")
        response = client.get(f"/api/v1/pullback/{test_date}?period=weekly")
        if response.status_code == 200:
            data = response.json()
            results_count = len(data.get("results", []))
            print(f"    ✓ Success: {results_count} results returned")
            print(f"    ✓ Timestamp: {data.get('timestamp')}")
        else:
            print(f"    ✗ Failed: {response.status_code} - {response.text}")
    
    # Test with currency filter
    if dates_weekly:
        test_date = dates_weekly[-1]
        print(f"  Testing GET /api/v1/pullback/{test_date}?period=weekly&currency=JPY")
        response = client.get(f"/api/v1/pullback/{test_date}?period=weekly&currency=JPY")
        if response.status_code == 200:
            data = response.json()
            results_count = len(data.get("results", []))
            print(f"    ✓ Success: {results_count} JPY results returned")
            print(f"    ✓ Currency filter: {data.get('currency_filter')}")
        else:
            print(f"    ✗ Failed: {response.status_code} - {response.text}")
    
    print()

if __name__ == "__main__":
    print("=" * 60)
    print("Pullback History Endpoints Test")
    print("=" * 60)
    print()
    
    try:
        test_history_storage()
        test_api_endpoints()
        
        print("=" * 60)
        print("All tests completed!")
        print("=" * 60)
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

