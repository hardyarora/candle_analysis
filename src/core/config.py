"""
Configuration settings for the candle analysis system.
"""
import os
from pathlib import Path
from typing import List, Dict

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Data directories
DATA_DIR = PROJECT_ROOT / "data"
LATEST_DIR = DATA_DIR / "latest"
BACKUPS_DIR = DATA_DIR / "backups"
LOGS_DIR = DATA_DIR / "logs"

# OANDA saved data directory (from first_test_app)
OANDA_SAVED_DATA_DIR = Path("/root/first_test_app/data/oanda_saved_data")

# OANDA API Configuration
OANDA_API_URL = "https://api-fxpractice.oanda.com/v3/instruments/{instrument}/candles"
ACCESS_TOKEN = "3e243a07175dad2e3b13b43f7b0c3db2-e158044d41883ede91b90cb98b577e0f"

# Full instrument list
INSTRUMENTS: List[str] = [
    "GBP_AUD",
    "GBP_NZD",
    "GBP_USD",
    "GBP_CAD",
    "GBP_JPY",
    "GBP_CHF",
    "EUR_AUD",
    "EUR_NZD",
    "EUR_JPY",
    "EUR_CAD",
    "EUR_CHF",
    "EUR_USD",
    "USD_JPY",
    "USD_CHF",
    "CAD_CHF",
    "CAD_JPY",
    "AUD_USD",
    "AUD_JPY",
    "AUD_CAD",
    "AUD_CHF",
    "NZD_USD",
    "NZD_JPY",
    "NZD_CAD",
    "NZD_CHF",
    "EUR_GBP",
    "USD_CAD",
    "AUD_NZD",
    "CHF_JPY",
    "XAU_USD",
    "XAG_USD"
]

# Remove duplicates
INSTRUMENTS = list(set(INSTRUMENTS))

# Full currency names for display in summaries
CURRENCY_FULL_NAMES: Dict[str, str] = {
    "USD": "United States Dollar",
    "EUR": "Euro",
    "GBP": "British Pound",
    "JPY": "Japanese Yen",
    "CHF": "Swiss Franc",
    "CAD": "Canadian Dollar",
    "AUD": "Australian Dollar",
    "NZD": "New Zealand Dollar",
}

# Supported timeframes for daily analysis
SUPPORTED_TIMEFRAMES = ["1D", "2D", "3D", "4D"]

# Default analysis settings
DEFAULT_IGNORE_CANDLES = 1
DEFAULT_CANDLE_COUNT_DAILY = 30
DEFAULT_CANDLE_COUNT_WEEKLY = 120
DEFAULT_CANDLE_COUNT_MONTHLY = 240

# Engulfing pattern detection threshold
# Percentage threshold for body engulfing detection (0.05 = 0.05%)
# Allows slight tolerance when mc2's body is very close to engulfing mc1's body
DEFAULT_ENGULFING_THRESHOLD_PERCENT = 0.10  # 0.05% threshold

# Engulfing feedback storage directories
ENGULFING_FEEDBACK_DIR = DATA_DIR / "engulfing_feedback"
ENGULFING_FEEDBACK_MERGED_DIR = ENGULFING_FEEDBACK_DIR / "merged"
