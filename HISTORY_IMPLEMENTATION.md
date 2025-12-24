# Historical Data Storage Implementation

## Overview

This implementation adds automatic historical data storage for API endpoint responses, allowing the frontend to retrieve historical snapshots of endpoint data over time.

## Components

### 1. History Storage Module (`src/core/history_storage.py`)

File system-based storage for historical snapshots:
- `store_snapshot()`: Store endpoint response data with date
- `get_snapshot()`: Retrieve snapshot for a specific date
- `get_snapshots_range()`: Get all snapshots within a date range
- `get_last_n_days()`: Get last N days of snapshots (default: 10)
- `list_dates()`: List all available dates for an endpoint
- `get_latest_snapshot()`: Get the most recent snapshot

**Storage Structure:**
```
data/history/
  strength_weakness_weekly/
    2024-01-15.json
    2024-01-16.json
    ...
  strength_weakness_monthly/
    2024-01-15.json
    ...
```

### 2. Endpoint Mapper (`src/utils/endpoint_mapper.py`)

Converts URL paths to endpoint identifiers:
- `extract_endpoint_identifier()`: Maps URLs to identifiers
  - `/api/candle_analysis/api/v1/strength-weakness?period=weekly` → `strength_weakness_weekly`
  - `/api/candle_analysis/api/v1/strength-weakness?period=monthly` → `strength_weakness_monthly`
  - `/api/candle_analysis/api/v1/analysis/1D` → `analysis_1D`
- `should_capture_endpoint()`: Determines if an endpoint should be captured

### 3. History Capture Scheduler (`src/schedulers/capture_history.py`)

Scheduled script that captures endpoint responses:
- Runs daily at 4:45 PM (configurable via cron)
- Makes HTTP requests to configured endpoints
- Stores JSON responses with current date
- Logs all capture operations
- Can be run manually or via cron

### 4. History API Endpoints (`src/api/routes.py`)

New endpoints for retrieving historical data:

#### GET `/api/v1/history/{endpoint}`
Get historical snapshots for an endpoint.

**Query Parameters:**
- `start_date` (optional): Start date in YYYY-MM-DD format
- `end_date` (optional): End date in YYYY-MM-DD format
- `date` (optional): Single date in YYYY-MM-DD format (alternative to range)

**Behavior:**
- If `date` is provided: Returns single snapshot
- If `start_date` and `end_date` are provided: Returns all snapshots in range
- If neither provided: Returns last 10 days (default)

**Response:**
```json
{
  "endpoint": "strength_weakness_weekly",
  "start_date": "2024-01-10",
  "end_date": "2024-01-20",
  "snapshots": [
    {
      "date": "2024-01-10",
      "timestamp": "2024-01-10T10:30:00Z",
      "data": { /* original response data */ }
    },
    ...
  ]
}
```

#### GET `/api/v1/history/{endpoint}/dates`
List all available dates for an endpoint.

**Response:**
```json
{
  "endpoint": "strength_weakness_weekly",
  "dates": ["2024-01-15", "2024-01-16", ...],
  "latest": "2024-01-20"
}
```

#### GET `/api/v1/history/{endpoint}/latest`
Get the latest snapshot for an endpoint.

**Response:**
```json
{
  "endpoint": "strength_weakness_weekly",
  "date": "2024-01-20",
  "timestamp": "2024-01-20T10:30:00Z",
  "data": { /* original response data */ }
}
```

#### POST `/api/v1/capture-history`
Manually trigger history capture for specified endpoints.

**Request Body (optional):**
```json
{
  "endpoints": ["strength_weakness_weekly", "strength_weakness_monthly"],
  "date": "2024-01-20"
}
```

**Response:**
```json
{
  "success": true,
  "captured": [
    {
      "endpoint": "strength_weakness_weekly",
      "date": "2024-01-20",
      "status": "success"
    }
  ],
  "errors": []
}
```

## Endpoint Identifier Mapping

The system automatically maps URLs to endpoint identifiers:

| URL | Endpoint Identifier |
|-----|---------------------|
| `/api/candle_analysis/api/v1/strength-weakness?period=weekly` | `strength_weakness_weekly` |
| `/api/candle_analysis/api/v1/strength-weakness?period=monthly` | `strength_weakness_monthly` |
| `/api/candle_analysis/api/v1/pullback?period=weekly` | `pullback_weekly` |
| `/api/candle_analysis/api/v1/pullback?period=monthly` | `pullback_monthly` |
| `/api/candle_analysis/api/v1/analysis/1D` | `analysis_1D` |
| `/api/candle_analysis/api/v1/analysis/2D` | `analysis_2D` |
| `/api/candle_analysis/api/v1/analysis/3D` | `analysis_3D` |
| `/api/candle_analysis/api/v1/analysis/4D` | `analysis_4D` |

## Scheduled Capture

The scheduler captures responses from configured endpoints:
- Runs daily at 4:45 PM (16:45 UTC) via cron
- Captures all configured endpoints in one run
- Stores snapshots with the current date
- Logs all operations for debugging

**Configured endpoints:**
- `strength_weakness_weekly`
- `strength_weakness_monthly`
- `pullback_weekly`
- `pullback_monthly`
- `analysis_1D`, `analysis_2D`, `analysis_3D`, `analysis_4D`

## Usage Examples

### Frontend Usage

1. **Get last 10 days of data (default):**
   ```
   GET /api/candle_analysis/api/v1/history/strength_weakness_weekly
   ```

2. **Get specific date range:**
   ```
   GET /api/candle_analysis/api/v1/history/strength_weakness_weekly?start_date=2024-01-10&end_date=2024-01-20
   ```

3. **Get single date:**
   ```
   GET /api/candle_analysis/api/v1/history/strength_weakness_weekly?date=2024-01-15
   ```

4. **List available dates:**
   ```
   GET /api/candle_analysis/api/v1/history/strength_weakness_weekly/dates
   ```

5. **Get latest snapshot:**
   ```
   GET /api/candle_analysis/api/v1/history/strength_weakness_weekly/latest
   ```

### Scheduled Capture

Set up a cron job to capture all endpoints daily at 4:45 PM:

```bash
# Add to crontab (runs at 16:45 UTC / 4:45 PM daily)
45 16 * * * cd /root/candle_analysis && /usr/bin/python3 -m src.schedulers.capture_history --base-url http://45.33.12.68 >> /root/candle_analysis/data/logs/cron.log 2>&1
```

Or run manually:

```bash
# Run with default localhost URL
python -m src.schedulers.capture_history

# Run with custom base URL
python -m src.schedulers.capture_history --base-url http://45.33.12.68
```

You can also use the manual capture endpoint with specific endpoints:

```bash
curl -X POST http://45.33.12.68/api/candle_analysis/api/v1/capture-history \
  -H "Content-Type: application/json" \
  -d '{
    "endpoints": ["strength_weakness_weekly", "strength_weakness_monthly"],
    "date": "2024-01-20"
  }'
```

## Configuration

The history storage uses the file system by default. Storage location:
- Base directory: `data/history/`
- Each endpoint has its own subdirectory
- Files are named by date: `YYYY-MM-DD.json`

## Dependencies

Added to `requirements.txt`:
- `httpx>=0.24.0` (for capture-history endpoint)

## Notes

1. **Scheduled Capture**: History is captured once per day at 4:45 PM via cron job. Adjust the time in crontab as needed.

2. **Duplicate Dates**: If an endpoint is captured multiple times in one day, the snapshot is overwritten with the latest response.

3. **Storage**: Currently uses file system storage. For production with large datasets, consider migrating to a database.

4. **Date Format**: All dates must be in `YYYY-MM-DD` format.

5. **Missing Dates**: If a date in a range has no snapshot, it is omitted from the response (no error).

6. **Base URL**: Make sure to configure the correct base URL in the cron job or scheduler script to match your API server.

## Testing

To test the implementation:

1. Run the capture scheduler manually:
   ```bash
   python -m src.schedulers.capture_history --base-url http://45.33.12.68
   ```

2. Check that snapshots were created:
   ```bash
   ls -la data/history/strength_weakness_weekly/
   ls -la data/history/strength_weakness_monthly/
   ```

3. Retrieve historical data:
   ```bash
   curl http://45.33.12.68/api/candle_analysis/api/v1/history/strength_weakness_weekly
   curl http://45.33.12.68/api/candle_analysis/api/v1/history/strength_weakness_weekly?start_date=2024-01-10&end_date=2024-01-20
   ```

## Future Enhancements

1. Database migration for large datasets
2. Compression for stored JSON files
3. Retention policies (auto-delete old snapshots)
4. Versioning instead of overwriting same-day snapshots
5. Configurable endpoint list via configuration file
6. Support for different timezones in cron scheduling

