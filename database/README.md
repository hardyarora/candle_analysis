# PostgreSQL Database Schema for OANDA Candle Analysis

## Overview

This database schema stores hourly snapshots of OANDA candle analysis results, including both daily and weekly timeframes. The schema is designed to efficiently store and query currency strength/weakness patterns over time.

## Data Model

### Main Tables

#### `candle_analysis_snapshots`
Stores complete analysis snapshots with full JSON data.

**Columns:**
- `id` (SERIAL PRIMARY KEY): Unique identifier
- `snapshot_timestamp` (TIMESTAMP WITH TIME ZONE): When the analysis was performed
- `timeframe` (VARCHAR(10)): Timeframe string (e.g., '1D', '2D', '3D', '4D', 'W', '2W')
- `granularity` (VARCHAR(10)): 'D' for daily, 'W' for weekly
- `analysis_data` (JSONB): Complete analysis results as JSON
- `ignore_candles` (INTEGER): Number of candles ignored in analysis
- `created_at` (TIMESTAMP WITH TIME ZONE): Record creation timestamp

**Unique Constraint:** `(snapshot_timestamp, timeframe)` - Prevents duplicate snapshots

#### `currency_patterns`
Extracts and stores individual currency patterns for easier querying.

**Columns:**
- `id` (SERIAL PRIMARY KEY): Unique identifier
- `snapshot_id` (INTEGER): Foreign key to `candle_analysis_snapshots`
- `snapshot_timestamp` (TIMESTAMP WITH TIME ZONE): When the analysis was performed
- `timeframe` (VARCHAR(10)): Timeframe string
- `granularity` (VARCHAR(10)): 'D' or 'W'
- `instrument` (VARCHAR(20)): Currency pair (e.g., 'GBPUSD', 'EURUSD')
- `pattern_type` (VARCHAR(50)): Pattern classification (e.g., 'bullish engulfing + upclose')
- `relation` (VARCHAR(100)): Full relation string from analysis
- `color` (VARCHAR(10)): 'GREEN', 'RED', or 'NEUTRAL'
- `mc1_open`, `mc1_high`, `mc1_low`, `mc1_close`: Previous period candle data
- `mc2_open`, `mc2_high`, `mc2_low`, `mc2_close`: Current period candle data
- `created_at` (TIMESTAMP WITH TIME ZONE): Record creation timestamp

### Views

#### `latest_analysis_by_timeframe`
Returns the most recent snapshot for each timeframe.

#### `strength_weakness_summary`
Aggregates currency patterns by pattern type, showing which instruments exhibit each pattern.

### Functions

#### `get_latest_snapshot(p_timeframe VARCHAR)`
Returns the latest snapshot for a specific timeframe.

#### `get_snapshots_range(p_timeframe VARCHAR, p_start_time TIMESTAMP, p_end_time TIMESTAMP)`
Returns all snapshots within a time range for a specific timeframe.

## Pattern Types

The analysis identifies the following pattern types indicating currency strength/weakness:

**Bullish Patterns (Strength):**
- `bullish engulfing + upclose` - Strongest bullish signal
- `bullish engulfing` - Strong bullish signal
- `bullish + upclose` - Moderate bullish signal
- `upclose` - Basic bullish signal

**Bearish Patterns (Weakness):**
- `bearish engulfing + downclose` - Strongest bearish signal
- `bearish engulfing` - Strong bearish signal
- `bearish + downclose` - Moderate bearish signal
- `downclose` - Basic bearish signal

**Neutral:**
- `neutral` - No clear pattern

## Setup

### 1. Install PostgreSQL

Ensure PostgreSQL is installed and running on your system.

### 2. Create Database

```sql
CREATE DATABASE candle_analysis;
```

### 3. Set Environment Variables

```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=candle_analysis
export DB_USER=postgres
export DB_PASSWORD=your_password
```

Or create a `.env` file:
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=candle_analysis
DB_USER=postgres
DB_PASSWORD=your_password
```

### 4. Initialize Schema

```bash
psql -U postgres -d candle_analysis -f database/schema.sql
```

Or use Python:
```python
from src.core.database import execute_schema_file
execute_schema_file("database/schema.sql")
```

## Usage

### Running Hourly Analysis

The hourly scheduler fetches data from OANDA API and stores results:

```bash
# Run with default settings (daily timeframes: 1D, 2D, 3D, 4D)
python -m src.schedulers.hourly_analysis

# Run with custom timeframes
python -m src.schedulers.hourly_analysis --daily 1D 2D --weekly W

# Force loading from OANDA API (skip cache)
python -m src.schedulers.hourly_analysis --force-oanda
```

### Setting Up Cron Job

To run every hour, add to crontab:

```bash
0 * * * * cd /path/to/project && python -m src.schedulers.hourly_analysis >> /var/log/hourly_analysis.log 2>&1
```

### Querying Data

#### Get Latest Analysis for a Timeframe

```python
from src.core.db_storage import get_latest_snapshot

snapshot = get_latest_snapshot('1D')
if snapshot:
    print(snapshot['analysis_data'])
```

#### Get Snapshots in a Time Range

```python
from src.core.db_storage import get_snapshots_range
from datetime import datetime, timedelta

start = datetime.now() - timedelta(days=7)
end = datetime.now()
snapshots = get_snapshots_range('1D', start, end)
```

#### Query Patterns Directly

```sql
-- Get all bullish patterns in the last 24 hours
SELECT 
    snapshot_timestamp,
    instrument,
    pattern_type,
    color
FROM currency_patterns
WHERE pattern_type LIKE 'bullish%'
    AND snapshot_timestamp >= NOW() - INTERVAL '24 hours'
ORDER BY snapshot_timestamp DESC;

-- Get strength/weakness summary for a timeframe
SELECT * FROM strength_weakness_summary
WHERE timeframe = '1D'
ORDER BY snapshot_timestamp DESC
LIMIT 10;
```

## Data Model Design Decisions

1. **JSONB Storage**: The full analysis data is stored as JSONB to preserve all details while allowing efficient querying.

2. **Separate Patterns Table**: Currency patterns are extracted into a separate table for:
   - Faster queries on specific patterns
   - Easier aggregation and reporting
   - Reduced need to parse JSON for common queries

3. **Hourly Snapshots**: Each snapshot represents a point-in-time analysis, allowing historical tracking of currency strength/weakness.

4. **Unique Constraint**: Prevents duplicate snapshots for the same timeframe at the same timestamp.

5. **Indexes**: Comprehensive indexing for:
   - Timestamp-based queries
   - Timeframe filtering
   - JSONB queries (GIN index)
   - Pattern-based queries

## Maintenance

### Cleanup Old Data

```sql
-- Delete snapshots older than 90 days
DELETE FROM candle_analysis_snapshots
WHERE snapshot_timestamp < NOW() - INTERVAL '90 days';
```

### Monitor Database Size

```sql
-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## Notes

- Weekly timeframe analysis requires extending the `analyze_all_currencies` function to support weekly granularity
- The schema supports both daily and weekly analysis, but weekly analysis is not yet fully implemented in the analyzer
- Consider partitioning the `candle_analysis_snapshots` table by time if storing very large amounts of historical data
