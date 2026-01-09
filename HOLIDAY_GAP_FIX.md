# Holiday/Vacation Gap Handling Fix

## Problem

When merging candles for multi-day timeframes (2D, 3D, 4D), the system was incorrectly merging candles that had holiday/vacation gaps between them. This caused incorrect pattern classifications.

### Example Issue: EURCHF 2D ignore=2

**Before Fix:**
- MC1 period: 2025-12-30 to 2026-01-01 (2-day gap due to New Year's Eve holiday)
- MC1 merged incorrectly: O=0.93002 (Dec 30 open) C=0.92858 (Jan 1 close)
- This incorrectly classified as "bullish engulfing"

**After Fix:**
- MC1 period: 2025-12-30 to 2026-01-01 (gap detected)
- MC1 uses last candle only: O=0.93155 (Jan 1 open) C=0.92858 (Jan 1 close)
- Correctly classified as "neutral" (not engulfing)

## Solution

Modified `merge_candles()` function in `src/core/candle_analyzer.py` to:

1. **Detect gaps**: Check if there's a gap > 1 day between any consecutive candles
2. **Handle gaps**: When a gap is detected, return only the last candle (most recent complete candle) instead of merging
3. **Normal merge**: When no gaps are detected, merge normally as before

### Logic

```python
# Check for gaps > 1 day between consecutive candles
for i in range(len(candles) - 1):
    gap_days = (time2 - time1).days
    if gap_days > 1:
        # Gap detected - use last candle only
        return last_candle_only

# No gaps - merge normally
return merged_candle
```

## Why This Matters

- **Accuracy**: Merged periods should represent true consecutive trading days
- **Pattern Classification**: Incorrect merges lead to false pattern detections (e.g., false "bullish engulfing")
- **Data Integrity**: Holiday gaps shouldn't be treated as normal trading periods

## Examples

### Normal Merge (No Gaps)
- Candles: [Day1, Day2] (1-day gap)
- Result: Merged candle with Day1 open and Day2 close

### Gap Detected
- Candles: [Dec 30, Jan 1] (2-day gap - New Year's Eve)
- Result: Jan 1 candle only (not merged)

## Testing

The fix was tested with EURCHF 2D ignore=2:
- ✅ MC1 now correctly uses last candle only (O=0.93155 C=0.92858)
- ✅ MC2 merges normally (O=0.92813 C=0.93000)
- ✅ Pattern classification corrected from "bullish engulfing" to "neutral"

## Code Location

- **File**: `src/core/candle_analyzer.py`
- **Function**: `merge_candles()` (lines 132-220)
- **Date**: 2026-01-08

## Related Issues

- Fixes incorrect "bullish engulfing" classification for EURCHF 2D ignore=2
- Prevents similar issues with other instruments during holiday periods


