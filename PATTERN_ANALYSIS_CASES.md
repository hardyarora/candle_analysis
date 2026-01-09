# Pattern Analysis Classification Cases

This document documents specific pattern classification cases and explanations for why certain instruments are classified the way they are.

## Table of Contents
- [Pattern Categories Overview](#pattern-categories-overview)
- [EURCHF - Bullish + Upclose (Not Engulfing)](#eurchf---bullish--upclose-not-engulfing)

---

## Pattern Categories Overview

The system classifies patterns in the following priority order:

### Bullish Patterns (Priority Order)
1. **Bullish engulfing + upclose**: Has engulfing AND upclose AND bullish
   - Code: `src/core/candle_analyzer.py` lines 364-366
   - Strongest bullish signal - combines engulfing pattern with upclose confirmation

2. **Bullish engulfing**: Has engulfing AND bullish (no upclose)
   - Code: `src/core/candle_analyzer.py` lines 364, 368
   - Strong bullish signal - body engulfs previous period's body
   - **Color Requirements**: MC1 (previous) must be RED (close < open) AND MC2 (current) must be GREEN (close > open)

3. **Bullish + upclose**: Has upclose AND bullish BUT NO engulfing
   - Code: `src/core/candle_analyzer.py` lines 377-379
   - Moderate bullish signal - closes above previous high but doesn't engulf

4. **Upclose**: Has upclose but not bullish and not engulfing
   - Code: `src/core/candle_analyzer.py` lines 377, 381
   - Weak bullish signal - closes above previous high but candle itself is not bullish

### Bearish Patterns (Priority Order)
1. **Bearish engulfing + downclose**: Has engulfing AND downclose AND bearish
   - Code: `src/core/candle_analyzer.py` lines 370-372
   - Strongest bearish signal - combines engulfing pattern with downclose confirmation

2. **Bearish engulfing**: Has engulfing AND bearish (no downclose)
   - Code: `src/core/candle_analyzer.py` lines 370, 374
   - Strong bearish signal - body engulfs previous period's body
   - **Color Requirements**: MC1 (previous) must be GREEN (close > open) AND MC2 (current) must be RED (close < open)

3. **Bearish + downclose**: Has downclose AND bearish BUT NO engulfing
   - Code: `src/core/candle_analyzer.py` lines 383-385
   - Moderate bearish signal - closes below previous low but doesn't engulf

4. **Downclose**: Has downclose but not bearish and not engulfing
   - Code: `src/core/candle_analyzer.py` lines 383, 387
   - Weak bearish signal - closes below previous low but candle itself is not bearish

### Classification Logic
- Patterns are checked in priority order
- Once a pattern matches, it's classified and lower-priority patterns are not checked
- For example, if a pattern has both engulfing and upclose, it will be classified as "Bullish engulfing + upclose" (highest priority) rather than just "Bullish engulfing" or "Bullish + upclose"

---

## EURCHF - Bullish + Upclose (Not Engulfing)

### Question
**Why is EURCHF shown as "1D Bullish + upclose ignore 1" instead of "1D Bullish engulfing ignore 1"?**

### Answer
EURCHF is correctly classified as **"Bullish + upclose"** and NOT "Bullish engulfing" because it fails the bottom engulfing condition.

### Analysis Details

**Date**: 2026-01-07  
**Timeframe**: 1D  
**Ignore Candles**: 1  
**Source File**: `data/latest/1D/analysis_1D_20260107_230519.json`

#### Candle Data

**MC1 (Previous Period - 2026-01-05)**:
```
Open:  0.9281
Close: 0.93
High:  0.93028
Low:   0.92772
Body Top:    0.93
Body Bottom: 0.9281
Body Size:   0.0019
```

**MC2 (Current Period - 2026-01-06)**:
```
Open:  0.92964
Close: 0.93162
High:  0.9319
Low:   0.92938
Body Top:    0.93162
Body Bottom: 0.92964
Body Size:   0.00198
```

#### Engulfing Calculation

**Threshold Configuration**:
- `DEFAULT_ENGULFING_THRESHOLD_PERCENT = 0.10` (0.10%)
- Location: `src/core/config.py` line 85

**Threshold Calculation**:
```python
mc1_body_size = 0.0019
mc1_body_top = 0.93
engulfing_threshold_percent = 0.10

threshold_absolute = max(
    mc1_body_size * (0.10 / 100.0),      # = 0.0000019
    mc1_body_top * (0.10 / 100.0)        # = 0.000465
)
# Result: threshold_absolute = 0.000465
```

**Engulfing Conditions** (both must be true):
1. **Bottom Engulfing**: `mc2_body_bottom <= (mc1_body_bottom + threshold)`
   - `0.92964 <= (0.9281 + 0.000465)`
   - `0.92964 <= 0.928565`
   - **Result: FALSE** ❌ (0.92964 > 0.928565)

2. **Top Engulfing**: `mc2_body_top >= (mc1_body_top - threshold)`
   - `0.93162 >= (0.93 - 0.000465)`
   - `0.93162 >= 0.929535`
   - **Result: TRUE** ✅

**Final Engulfing Result**: **FALSE** (both conditions must be true)

#### Pattern Classification

**Why "Bullish + upclose"**:
- ✅ **Has upclose**: `mc2_close (0.93162) > mc1_high (0.93028)`
- ✅ **Is bullish**: `mc2_close (0.93162) > mc2_open (0.92964)`
- ❌ **NOT engulfing**: Bottom doesn't engulf (fails bottom engulfing check)

**Classification Logic** (from `src/core/candle_analyzer.py` lines 377-381):
```python
# Standalone bullish/bearish with upclose/downclose (without engulfing)
if has_upclose and not has_bullish_engulfing and not has_bearish_engulfing:
    if is_bullish:
        pattern_instruments["Bullish + upclose"].add(instrument_name)
```

### Key Insight

Even though MC2's body extends above MC1's body (top engulfs), it doesn't extend **below** MC1's body enough to meet the engulfing threshold. The bottom of MC2 (0.92964) is **higher** than the bottom of MC1 plus threshold (0.928565), so it fails the bottom engulfing check.

For a true engulfing pattern, MC2's body must extend both above AND below MC1's body (within the threshold tolerance).

### Related Code Locations

- Engulfing detection logic: `src/core/candle_analyzer.py` lines 218-231
- Pattern classification: `src/core/candle_analyzer.py` lines 354-387
- Threshold configuration: `src/core/config.py` line 85
- Latest analysis data: `data/latest/1D/analysis_1D_20260107_230519.json` (EURCHF at line 260-277)

---

## Engulfing Pattern Color Requirements

### Overview

Engulfing patterns require specific candle colors to be valid. This ensures that the pattern represents a true reversal signal.

### Bullish Engulfing Requirements

For a pattern to be classified as **bullish engulfing**, ALL of the following must be true:

1. **Body Engulfing**: MC2's body must extend both above AND below MC1's body (within threshold tolerance)
   - Bottom: `mc2_body_bottom <= (mc1_body_bottom + threshold_absolute)`
   - Top: `mc2_body_top >= (mc1_body_top - threshold_absolute)`

2. **MC1 Color**: MC1 (previous candle) must be **RED** (bearish)
   - Condition: `mc1_close < mc1_open`

3. **MC2 Color**: MC2 (current candle) must be **GREEN** (bullish)
   - Condition: `mc2_close > mc2_open`

**Code Location**: `src/core/candle_analyzer.py` lines 225-228

### Bearish Engulfing Requirements

For a pattern to be classified as **bearish engulfing**, ALL of the following must be true:

1. **Body Engulfing**: MC2's body must extend both above AND below MC1's body (within threshold tolerance)
   - Bottom: `mc2_body_bottom <= (mc1_body_bottom + threshold_absolute)`
   - Top: `mc2_body_top >= (mc1_body_top - threshold_absolute)`

2. **MC1 Color**: MC1 (previous candle) must be **GREEN** (bullish)
   - Condition: `mc1_close > mc1_open`

3. **MC2 Color**: MC2 (current candle) must be **RED** (bearish)
   - Condition: `mc2_close < mc2_open`

**Code Location**: `src/core/candle_analyzer.py` lines 229-231

### Why Color Requirements Matter

Engulfing patterns are reversal patterns. They signal a change in market sentiment:
- **Bullish engulfing**: A bearish candle (MC1) is followed by a larger bullish candle (MC2) that engulfs it, indicating a potential upward reversal
- **Bearish engulfing**: A bullish candle (MC1) is followed by a larger bearish candle (MC2) that engulfs it, indicating a potential downward reversal

If the color requirements are not met, the pattern may still have engulfing geometry but does not represent a true reversal signal, so it should not be classified as an engulfing pattern.

### Example: Invalid Engulfing

**Scenario**: MC1 is green, MC2 is green, and MC2's body engulfs MC1's body.

**Result**: This will **NOT** be classified as "bullish engulfing" because MC1 is not red. It may be classified as "bullish + upclose" or another pattern depending on other conditions.

---

## Adding New Cases

When documenting a new pattern classification case, include:
1. The question/issue
2. The answer/explanation
3. Analysis details (date, timeframe, ignore_candles)
4. Candle data (MC1 and MC2)
5. Calculation steps
6. Pattern classification logic
7. Key insights
8. Related code locations

