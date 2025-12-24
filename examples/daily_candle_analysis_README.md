# Daily Candle Analysis Tool

A powerful tool for analyzing daily candle patterns across multiple merged timeframes for forex trading.

## Features

- **Multiple Timeframes**: Analyze D (daily), 2D, 3D, 4D, 5D, 6D, or 7D merged candles
- **Currency Focus**: Analyze specific currency pairs or view all currencies in a strength table
- **Pattern Detection**: Identifies upclose, downclose, bullish engulfing, bearish engulfing, and regular bullish/bearish patterns
- **Comprehensive Analysis**: Shows OHLOC data for merged candle pairs with color coding

## Usage

### Single Currency Analysis

Analyze all pairs containing a specific currency:

```bash
python3 daily_candle_analysis.py --currency GBP --tf 4D
```

This will:
- Fetch all currency pairs containing GBP (e.g., GBP_USD, EUR_GBP, GBP_AUD, etc.)
- Get 30 daily candles for each pair
- Ignore the last candle
- Merge the last 4 days into MC2 (current period)
- Merge the 4 days before that into MC1 (previous period)
- Analyze the relationship between MC1 and MC2

### All Currencies Strength Table

View a comprehensive comparison of all currencies:

```bash
python3 daily_candle_analysis.py --all --tf 4D
```

This shows:
- Net strength score for each currency (strongest to weakest)
- Count of upclose/downclose events
- Bullish/bearish engulfing patterns
- Green/red candle counts
- Total signal count across all pairs

## Timeframes

- **D**: Single daily candle
- **2D**: Merge 2 daily candles
- **3D**: Merge 3 daily candles
- **4D**: Merge 4 daily candles
- **5D-7D**: Merge 5-7 daily candles

## Pattern Types

The tool detects these patterns between merged candle pairs:

1. **Upclose ⬆️**: Current merged candle (MC2) closes above previous merged candle (MC1) high
2. **Downclose ⬇️**: MC2 closes below MC1 low
3. **Bullish Engulfing**: MC2 engulfs MC1 and closes higher
4. **Bearish Engulfing**: MC2 engulfs MC1 and closes lower
5. **Bullish**: MC2 is a bullish candle (close > open) but no special pattern
6. **Bearish**: MC2 is a bearish candle (close < open) but no special pattern
7. **Neutral**: No clear directional pattern

## Examples

```bash
# Analyze EUR pairs with 4-day merged candles
python3 daily_candle_analysis.py --currency EUR --tf 4D

# Analyze USD pairs with single daily candles
python3 daily_candle_analysis.py --currency USD --tf D

# Analyze JPY pairs with 2-day merged candles
python3 daily_candle_analysis.py --currency JPY --tf 2D

# Show all currency strength (sorted by net strength)
python3 daily_candle_analysis.py --all --tf 3D
```

## Output

### Single Currency Analysis
- Shows detailed table with MC1 and MC2 OHLC data
- Displays relationship type and candle color
- Summary statistics at the bottom

### All Currencies Analysis
- Sorted by net strength (strongest to weakest)
- Shows counts for each pattern type
- Highlights strongest and weakest currencies

## How Merging Works

When you use 4D timeframe with candles c1, c2, c3, c4, c5, c6, c7, c8, c9:

- Ignore c9 (last incomplete candle)
- MC1 (previous period): merge c1, c2, c3, c4
  - High: max(c1.high, c2.high, c3.high, c4.high)
  - Low: min(c1.low, c2.low, c3.low, c4.low)
  - Open: c1.open
  - Close: c4.close

- MC2 (current period): merge c5, c6, c7, c8
  - High: max(c5.high, c6.high, c7.high, c8.high)
  - Low: min(c5.low, c6.low, c7.low, c8.low)
  - Open: c5.open
  - Close: c8.close

## Requirements

- Python 3.x
- requests library
- tabulate library

```bash
pip install requests tabulate
```

## Supported Currencies

The tool analyzes all major currency pairs including:
- AUD, CAD, CHF, EUR, GBP, JPY, NZD, USD

And all their combinations (GBP_USD, EUR_JPY, AUD_NZD, etc.)

