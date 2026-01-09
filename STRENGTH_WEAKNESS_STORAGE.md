# Strength-Weakness Data Storage

## Overview

The hourly scheduler now captures and stores strength-weakness data from the API endpoint `/api/candle_analysis/api/v1/strength-weakness?period=weekly` in PostgreSQL.

## Database Schema Updates

### New Tables

1. **`strength_weakness_snapshots`**
   - Stores complete strength-weakness response data as JSONB
   - Tracks period ('daily', 'weekly', 'monthly')
   - Unique constraint on `(snapshot_timestamp, period)`

2. **`currency_strength_weakness`**
   - Extracts individual currency data for easier querying
   - Stores tested_high_count, tested_low_count, strength, weakness
   - Stores arrays of tested_high_instruments and tested_low_instruments

### New Views and Functions

- `latest_strength_weakness_by_period`: Latest snapshot for each period
- `get_latest_strength_weakness(p_period)`: Function to get latest snapshot

## Usage

### Running the Hourly Scheduler

The scheduler now automatically fetches and stores strength-weakness data:

```bash
# Run with default settings (includes weekly strength-weakness)
python -m src.schedulers.hourly_analysis

# Run with custom base URL
python -m src.schedulers.hourly_analysis --base-url http://45.33.12.68

# Fetch multiple periods
python -m src.schedulers.hourly_analysis --strength-weakness-periods weekly monthly

# Skip strength-weakness storage
python -m src.schedulers.hourly_analysis --no-store-strength-weakness
```

### Setting Up Cron

```bash
# Run every hour
0 * * * * cd /path/to/project && python -m src.schedulers.hourly_analysis --base-url http://45.33.12.68 >> /var/log/hourly_analysis.log 2>&1
```

## Data Structure

The strength-weakness endpoint returns:

```json
{
  "timestamp": "2024-01-15T10:00:00",
  "currency_filter": null,
  "ignore_candles": 0,
  "period": "weekly",
  "currencies": {
    "USD": {
      "tested_high": ["USD_JPY", "USD_CAD"],
      "tested_high_count": 2,
      "tested_low": ["EUR_USD", "GBP_USD"],
      "tested_low_count": 2,
      "strength": 0.5,
      "weakness": 0.5
    },
    ...
  },
  "summary": {
    "by_strength": [...],
    "by_weakness": [...]
  }
}
```

This data is stored:
- As complete JSON in `strength_weakness_snapshots.response_data`
- As extracted currency records in `currency_strength_weakness`

## Querying Data

### Get Latest Weekly Strength-Weakness

```python
from src.core.db_storage import get_latest_strength_weakness

snapshot = get_latest_strength_weakness('weekly')
if snapshot:
    data = snapshot['response_data']
    print(data['currencies'])
```

### SQL Queries

```sql
-- Get latest weekly strength-weakness
SELECT * FROM latest_strength_weakness_by_period
WHERE period = 'weekly';

-- Get currencies sorted by strength
SELECT currency, strength, weakness, snapshot_timestamp
FROM currency_strength_weakness
WHERE period = 'weekly'
ORDER BY snapshot_timestamp DESC, strength DESC
LIMIT 10;

-- Get strength trends over time
SELECT 
    DATE(snapshot_timestamp) as date,
    currency,
    AVG(strength) as avg_strength,
    AVG(weakness) as avg_weakness
FROM currency_strength_weakness
WHERE period = 'weekly'
    AND snapshot_timestamp >= NOW() - INTERVAL '7 days'
GROUP BY DATE(snapshot_timestamp), currency
ORDER BY date DESC, avg_strength DESC;
```

## Configuration

The scheduler supports the following options:

- `--base-url`: API base URL (default: http://localhost:8000)
- `--store-strength-weakness`: Enable strength-weakness storage (default: True)
- `--no-store-strength-weakness`: Disable strength-weakness storage
- `--strength-weakness-periods`: Periods to fetch (default: ['weekly'])

## Notes

- The weekly strength-weakness data is now automatically captured every hour
- Data is stored with full JSON response for complete historical record
- Currency-level data is extracted for efficient querying
- The endpoint URL is: `http://45.33.12.68/api/candle_analysis/api/v1/strength-weakness?period=weekly`
