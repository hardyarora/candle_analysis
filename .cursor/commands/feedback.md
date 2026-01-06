Execute the interactive feedback script to add feedback for engulfing candle patterns.

Parse the user's input and execute the script with the provided arguments.

If the user provides arguments in the format: `/feedback <currency> <timeframe> rating <rating>` or `/feedback <currency> <timeframe> <rating>`, extract:
- currency: Currency pair (e.g., GBP_NZD, NZD_CHF)
- timeframe: Timeframe (1D, 2D, 3D, or 4D)
- rating: Rating number (1-10)

Then execute: `python3 scripts/add_feedback.py <currency> <timeframe> <rating>`

Examples:
- User input: `/feedback GBP_NZD 1D rating 5` → Execute: `python3 scripts/add_feedback.py GBP_NZD 1D 5`
- User input: `/feedback GBP_NZD 1D 5` → Execute: `python3 scripts/add_feedback.py GBP_NZD 1D 5`
- User input: `/feedback GBP_NZD 1D 5 --date 2025-12-30` → Execute: `python3 scripts/add_feedback.py GBP_NZD 1D 5 --date 2025-12-30`

The script will automatically:
- Fetch candles for the currency and timeframe
- Analyze the latest pattern (or specified date)
- Calculate metrics
- Store the feedback

If no arguments are provided, run interactively: `python3 scripts/add_feedback.py`

