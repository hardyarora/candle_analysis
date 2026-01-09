# PostgreSQL Data Model for OANDA Analysis Storage

## Overview

This document describes the PostgreSQL data model designed to store hourly snapshots of OANDA candle analysis results, including both daily and weekly timeframes. The system processes candle data to identify currency strength/weakness patterns and stores them for historical tracking and analysis.

## Data Model Architecture

### Core Tables

#### 1. `candle_analysis_snapshots`
**Purpose**: Stores complete analysis snapshots with full JSON data.

**Schema**:
```sql
- id: SERIAL PRIMARY KEY
- snapshot_timestamp: TIMESTAMP WITH TIME ZONE (when analysis was performed)
- timeframe: VARCHAR(10) (e.g., '1D', '2D', '3D', '4D', 'W', '2W')
- granularity: VARCHAR(10) ('D' for daily, 'W' for weekly)
- analysis_data: JSONB (complete analysis results)
- ignore_candles: INTEGER (number of candles ignored)
- created_at: TIMESTAMP WITH TIME ZONE
```

**Key Features**:
- Unique constraint on `(snapshot_timestamp, timeframe)` prevents duplicates
- JSONB storage allows flexible querying of nested data
- Indexed for efficient timestamp and timeframe queries

#### 2. `currency_patterns`
**Purpose**: Extracts individual currency patterns for easier querying and aggregation.

**Schema**:
```sql
- id: SERIAL PRIMARY KEY
- snapshot_id: INTEGER (FK to candle_analysis_snapshots)
- snapshot_timestamp: TIMESTAMP WITH TIME ZONE
- timeframe: VARCHAR(10)
- granularity: VARCHAR(10)
- instrument: VARCHAR(20) (e.g., 'GBPUSD', 'EURUSD')
- pattern_type: VARCHAR(50) (e.g., 'bullish engulfing + upclose')
- relation: VARCHAR(100) (full relation string)
- color: VARCHAR(10) ('GREEN', 'RED', 'NEUTRAL')
- mc1_open, mc1_high, mc1_low, mc1_close: NUMERIC(15,5)
- mc2_open, mc2_high, mc2_low, mc2_close: NUMERIC(15,5)
- created_at: TIMESTAMP WITH TIME ZONE
```

**Key Features**:
- Denormalized for fast pattern-based queries
- Stores both previous (mc1) and current (mc2) period candle data
- Indexed for efficient filtering by instrument, pattern, and timeframe

### Views

1. **`latest_analysis_by_timeframe`**: Returns the most recent snapshot for each timeframe
2. **`strength_weakness_summary`**: Aggregates patterns by type, showing which instruments exhibit each pattern

### Functions

1. **`get_latest_snapshot(p_timeframe)`**: Get latest snapshot for a timeframe
2. **`get_snapshots_range(p_timeframe, p_start_time, p_end_time)`**: Get snapshots in a time range

## Pattern Types (Strength/Weakness Indicators)

### Bullish Patterns (Strength)
- `bullish engulfing + upclose` - Strongest bullish signal
- `bullish engulfing` - Strong bullish signal  
- `bullish + upclose` - Moderate bullish signal
- `upclose` - Basic bullish signal

### Bearish Patterns (Weakness)
- `bearish engulfing + downclose` - Strongest bearish signal
- `bearish engulfing` - Strong bearish signal
- `bearish + downclose` - Moderate bearish signal
- `downclose` - Basic bearish signal

### Neutral
- `neutral` - No clear pattern

## Files Created

### Database Schema
- **`database/schema.sql`**: Complete PostgreSQL schema with tables, indexes, views, and functions

### Python Modules
- **`src/core/database.py`**: Database connection pool management
- **`src/core/db_storage.py`**: Functions for storing and retrieving analysis results
- **`src/schedulers/hourly_analysis.py`**: Hourly scheduler script to fetch and store data

### Utilities
- **`database/init_db.py`**: Script to initialize the database schema
- **`database/README.md`**: Detailed documentation

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Database
Set environment variables:
```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=candle_analysis
export DB_USER=postgres
export DB_PASSWORD=your_password
```

### 3. Create Database
```sql
CREATE DATABASE candle_analysis;
```

### 4. Initialize Schema
```bash
python database/init_db.py
```

Or manually:
```bash
psql -U postgres -d candle_analysis -f database/schema.sql
```

### 5. Run Hourly Scheduler
```bash
# Run once
python -m src.schedulers.hourly_analysis

# Set up cron job (runs every hour)
0 * * * * cd /path/to/project && python -m src.schedulers.hourly_analysis >> /var/log/hourly_analysis.log 2>&1
```

## Usage Examples

### Store Analysis Results
```python
from src.core.db_storage import run_and_store_analysis

# Run and store daily analysis
snapshot_id = run_and_store_analysis(
    timeframe='1D',
    granularity='D',
    ignore_candles=1
)
```

### Query Latest Analysis
```python
from src.core.db_storage import get_latest_snapshot

snapshot = get_latest_snapshot('1D')
if snapshot:
    analysis_data = snapshot['analysis_data']
    print(analysis_data['patterns'])
```

### Query Historical Data
```python
from src.core.db_storage import get_snapshots_range
from datetime import datetime, timedelta

start = datetime.now() - timedelta(days=7)
end = datetime.now()
snapshots = get_snapshots_range('1D', start, end)
```

### SQL Queries
```sql
-- Get all bullish patterns in last 24 hours
SELECT instrument, pattern_type, snapshot_timestamp
FROM currency_patterns
WHERE pattern_type LIKE 'bullish%'
    AND snapshot_timestamp >= NOW() - INTERVAL '24 hours'
ORDER BY snapshot_timestamp DESC;

-- Get strength/weakness summary
SELECT * FROM strength_weakness_summary
WHERE timeframe = '1D'
ORDER BY snapshot_timestamp DESC
LIMIT 10;
```

## Data Flow

1. **Hourly Scheduler** (`src/schedulers/hourly_analysis.py`)
   - Runs every hour (via cron)
   - Fetches daily and weekly data from OANDA API
   - Processes data using `analyze_all_currencies()`
   - Stores results in PostgreSQL

2. **Analysis Processing** (`src/core/candle_analyzer.py`)
   - Fetches candles from OANDA API
   - Merges candles based on timeframe
   - Analyzes candle relationships (upclose, downclose, engulfing patterns)
   - Returns structured analysis data

3. **Storage** (`src/core/db_storage.py`)
   - Stores complete analysis as JSONB in `candle_analysis_snapshots`
   - Extracts patterns into `currency_patterns` table
   - Maintains referential integrity

## Design Decisions

1. **Dual Storage Strategy**:
   - JSONB for complete data preservation
   - Denormalized patterns table for fast queries

2. **Hourly Snapshots**:
   - Captures point-in-time analysis
   - Enables historical trend analysis
   - Prevents data loss from overwrites

3. **Indexing Strategy**:
   - Timestamp indexes for time-based queries
   - GIN index on JSONB for flexible JSON queries
   - Composite indexes for common query patterns

4. **Unique Constraints**:
   - Prevents duplicate snapshots
   - Ensures data integrity

## Current Limitations

1. **Weekly Analysis**: The `analyze_all_currencies()` function currently only supports daily timeframes (1D-4D). Weekly analysis requires extending the analyzer to support weekly granularity.

2. **Data Retention**: No automatic cleanup of old data. Consider implementing a retention policy based on your needs.

## Future Enhancements

1. **Weekly Analysis Support**: Extend `analyze_all_currencies()` to support weekly timeframes
2. **Partitioning**: Partition tables by time for better performance with large datasets
3. **Automated Cleanup**: Add scheduled cleanup of old snapshots
4. **API Endpoints**: Expose database queries via REST API
5. **Analytics**: Add views/functions for trend analysis and pattern detection

## Maintenance

### Monitor Database Size
```sql
SELECT 
    tablename,
    pg_size_pretty(pg_total_relation_size('public.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size('public.'||tablename) DESC;
```

### Cleanup Old Data
```sql
-- Delete snapshots older than 90 days
DELETE FROM candle_analysis_snapshots
WHERE snapshot_timestamp < NOW() - INTERVAL '90 days';
```

## Notes

- The schema supports both daily and weekly analysis, but weekly analysis is not yet fully implemented in the analyzer
- All timestamps are stored with timezone information
- The JSONB column allows flexible querying without schema changes
- Consider adding connection pooling configuration based on your load
