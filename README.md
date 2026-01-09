# Candle Analysis System

A production-ready candle analysis system for forex trading that fetches data from OANDA, performs pattern analysis across multiple timeframes (1D, 2D, 3D, 4D), and provides a REST API for querying results.

## Features

- **Multi-timeframe Analysis**: Supports 1D, 2D, 3D, and 4D merged daily candles
- **Automated Data Management**: Automatic backup of previous analyses before running new ones
- **REST API**: FastAPI-based API for querying current and historical analysis data
- **Pattern Detection**: Identifies upclose, downclose, bullish/bearish engulfing patterns
- **Scheduled Execution**: Cron-ready scripts for daily automated analysis

## Project Structure

```
/root/candle_analysis/
├── src/
│   ├── api/              # FastAPI application
│   │   ├── main.py       # FastAPI app initialization
│   │   ├── models.py     # Pydantic models
│   │   └── routes.py     # API endpoints
│   ├── core/             # Core analysis and file management
│   │   ├── config.py     # Configuration and constants
│   │   ├── candle_analyzer.py  # Candle analysis logic
│   │   └── file_manager.py     # File operations (backup/save/load)
│   ├── schedulers/       # Daily execution scripts
│   │   └── run_timeframe.py    # Main scheduler script
│   └── utils/            # Shared utilities
│       └── timeframe.py  # Timeframe normalization
├── tests/                # Unit tests
│   ├── test_utils/
│   ├── test_core/
│   └── test_api/
├── data/                 # Data storage
│   ├── latest/           # Current analysis (1D/, 2D/, 3D/, 4D/)
│   ├── backups/          # Date-based backups (YYYY-MM-DD/timeframe/)
│   └── logs/             # Execution logs (YYYY-MM-DD/)
├── examples/             # Example scripts (reference)
├── requirements.txt
├── .cursorrules
├── README.md
└── crontab.example
```

## Setup

### Prerequisites

- Python 3.8 or higher
- OANDA API access token (configured in `src/core/config.py`)

### Installation

1. Clone or navigate to the project directory:
```bash
cd /root/candle_analysis
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Ensure data directories exist (they will be created automatically, but you can create them manually):
```bash
mkdir -p data/latest data/backups data/logs
```

## Usage

### Running Analysis Manually

Run analysis for a specific timeframe:

```bash
python -m src.schedulers.run_timeframe --timeframe 1D
python -m src.schedulers.run_timeframe --timeframe 2D
python -m src.schedulers.run_timeframe --timeframe 3D
python -m src.schedulers.run_timeframe --timeframe 4D
```

Or with case-insensitive formats:
```bash
python -m src.schedulers.run_timeframe -t d      # Normalizes to 1D
python -m src.schedulers.run_timeframe -t 1d      # Normalizes to 1D
python -m src.schedulers.run_timeframe -t 2D      # Normalizes to 2D
```

Options:
- `--timeframe, -t`: Timeframe (1D, 2D, 3D, or 4D)
- `--ignore-candles`: Number of candles to ignore at the end (default: 1)

### Scheduled Execution with Cron

1. Make the scheduler script executable:
```bash
chmod +x src/schedulers/run_timeframe.py
```

2. Edit crontab:
```bash
crontab -e
```

3. Add entries for each timeframe (see `crontab.example` for examples):
```cron
# Run 1D analysis daily at 00:00 UTC
0 0 * * * cd /root/candle_analysis && /usr/bin/python3 -m src.schedulers.run_timeframe --timeframe 1D

# Run 2D analysis daily at 00:05 UTC
5 0 * * * cd /root/candle_analysis && /usr/bin/python3 -m src.schedulers.run_timeframe --timeframe 2D

# Run 3D analysis daily at 00:10 UTC
10 0 * * * cd /root/candle_analysis && /usr/bin/python3 -m src.schedulers.run_timeframe --timeframe 3D

# Run 4D analysis daily at 00:15 UTC
15 0 * * * cd /root/candle_analysis && /usr/bin/python3 -m src.schedulers.run_timeframe --timeframe 4D
```

### Starting the REST API

Start the FastAPI server:

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

Or with reload for development:
```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:
- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Health check: http://localhost:8000/api/v1/health

## API Documentation

### Endpoints

#### GET `/api/v1/health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-01T00:00:00"
}
```

#### GET `/api/v1/analysis/{timeframe}`
Get current analysis for a timeframe.

**Parameters:**
- `timeframe` (path): Timeframe string (1D, 2D, 3D, or 4D, case insensitive)

**Response:**
```json
{
  "timeframe": "1D",
  "timestamp": "2025-01-01T00:00:00",
  "ignore_candles": 1,
  "patterns": {
    "bullish engulfing + upclose": ["GBPUSD", "EURUSD"],
    "bearish engulfing": ["USDJPY"]
  },
  "instruments": [
    {
      "instrument": "GBP_USD",
      "mc1": {
        "time": "2025-01-01 to 2025-01-01",
        "open": 1.25000,
        "high": 1.26000,
        "low": 1.24000,
        "close": 1.25500
      },
      "mc2": {
        "time": "2025-01-02 to 2025-01-02",
        "open": 1.25500,
        "high": 1.27000,
        "low": 1.25000,
        "close": 1.26500
      },
      "relation": "upclose ⬆️ + bullish engulfing",
      "color": "GREEN"
    }
  ]
}
```

#### GET `/api/v1/analysis/{timeframe}/history`
Get list of available dates (current + backups) for a timeframe.

**Parameters:**
- `timeframe` (path): Timeframe string (1D, 2D, 3D, or 4D, case insensitive)

**Response:**
```json
{
  "timeframe": "1D",
  "current": ["2025-01-01"],
  "backups": ["2025-01-02", "2025-01-03"],
  "all_dates": ["2025-01-01", "2025-01-02", "2025-01-03"]
}
```

#### GET `/api/v1/analysis/{timeframe}/{date}`
Get historical analysis for a specific timeframe and date.

**Parameters:**
- `timeframe` (path): Timeframe string (1D, 2D, 3D, or 4D, case insensitive)
- `date` (path): Date string in YYYY-MM-DD format

**Response:** Same as current analysis endpoint.

**Error Responses:**
- `400`: Invalid timeframe or date format
- `404`: Analysis not found for the specified timeframe/date

## Data Management

### Directory Structure

- **`data/latest/{timeframe}/`**: Contains the most recent analysis for each timeframe
- **`data/backups/{date}/{timeframe}/`**: Contains historical backups organized by date
- **`data/logs/{date}/`**: Contains execution logs organized by date

### Backup Process

When a new analysis is run:
1. Existing data in `data/latest/{timeframe}/` is moved to `data/backups/{today}/{timeframe}/`
2. New analysis is saved to `data/latest/{timeframe}/`
3. Logs are written to `data/logs/{today}/`

This ensures:
- Current analysis is always in `latest/`
- Historical data is preserved in `backups/`
- Easy cleanup of old backups if needed

## Pattern Detection

The system detects the following patterns (in priority order):

### Bullish Patterns
1. **Bullish engulfing + upclose**: Has engulfing AND upclose AND bullish (strongest bullish signal)
2. **Bullish engulfing**: Has engulfing AND bullish (no upclose)
   - **Color Requirements**: MC1 (previous) must be RED (close < open) AND MC2 (current) must be GREEN (close > open)
3. **Bullish + upclose**: Has upclose AND bullish BUT NO engulfing
4. **Upclose**: Has upclose but not bullish and not engulfing

### Bearish Patterns
1. **Bearish engulfing + downclose**: Has engulfing AND downclose AND bearish (strongest bearish signal)
2. **Bearish engulfing**: Has engulfing AND bearish (no downclose)
   - **Color Requirements**: MC1 (previous) must be GREEN (close > open) AND MC2 (current) must be RED (close < open)
3. **Bearish + downclose**: Has downclose AND bearish BUT NO engulfing
4. **Downclose**: Has downclose but not bearish and not engulfing

### Other
- **Neutral**: No clear directional pattern

**Note**: Patterns are classified based on priority. For example, if a pattern has both engulfing and upclose, it will be classified as "Bullish engulfing + upclose" (highest priority) rather than just "Bullish engulfing" or "Bullish + upclose".

## Testing

Run all tests:
```bash
pytest tests/
```

Run specific test file:
```bash
pytest tests/test_utils/test_timeframe.py
pytest tests/test_core/test_file_manager.py
pytest tests/test_api/test_routes.py
```

## Configuration

Main configuration is in `src/core/config.py`:
- OANDA API URL and access token
- Supported instruments list
- Default settings (ignore candles, candle counts)

## Timeframe Support

The system supports the following timeframes:
- **1D** (or **D**): Single daily candle
- **2D**: Merge 2 daily candles
- **3D**: Merge 3 daily candles
- **4D**: Merge 4 daily candles

All formats are case-insensitive (D, 1D, 1d all normalize to "1D").

## Troubleshooting

### API returns 404 for analysis
- Ensure the scheduler has run at least once for the requested timeframe
- Check that `data/latest/{timeframe}/` contains JSON files

### Scheduler fails
- Check OANDA API credentials in `src/core/config.py`
- Verify network connectivity to OANDA API
- Check logs in `data/logs/{date}/`

### Import errors
- Ensure you're running from the project root directory
- Verify all dependencies are installed: `pip install -r requirements.txt`
- Check that `src/` is in Python path

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

