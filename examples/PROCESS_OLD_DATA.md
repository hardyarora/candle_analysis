# Processing Old Currency Strength/Weakness Data

This document explains how to process historical currency strength/weakness data from text format and add it to the historical storage system.

## Input Data Format

The input data should be in the following text format, with one entry per line:

```
YYYY-MM-DD  INSTRUMENT (STATUS) (TEST_TYPE)
```

**Example:**
```
2025-12-15  USD_CAD (LOW_BROKEN) (FIRST TEST)
2025-12-15  NZD_CHF (LOW_BROKEN) (FIRST TEST)
2025-12-15  EUR_CAD (HIGH_BROKEN) (FIRST TEST)
2025-12-15  EUR_NZD (HIGH_BROKEN) (FIRST TEST)
2025-12-16  NZD_USD (LOW_BROKEN) (FIRST TEST)
2025-12-16  GBP_AUD (HIGH_BROKEN) (FIRST TEST)
```

**Field Descriptions:**
- `YYYY-MM-DD`: Date in ISO format
- `INSTRUMENT`: Currency pair (e.g., `USD_CAD`, `EUR_GBP`)
- `STATUS`: Either `HIGH_BROKEN` or `LOW_BROKEN`
  - `HIGH_BROKEN`: Base currency tested high, quote currency tested low
  - `LOW_BROKEN`: Base currency tested low, quote currency tested high
- `TEST_TYPE`: Usually `(FIRST TEST)` - can be ignored for processing

## Processing Steps

### Step 1: Prepare Your Data

Save your data in a text format (can be in a file or paste directly into the script). The data should follow the format shown above.

### Step 2: Update the Parse Script

Edit `examples/parse_date_data.py` and update the `data_lines` variable with your data:

```python
data_lines = """2025-12-15  USD_CAD (LOW_BROKEN) (FIRST TEST)
2025-12-15  NZD_CHF (LOW_BROKEN) (FIRST TEST)
2025-12-15  EUR_CAD (HIGH_BROKEN) (FIRST TEST)
... your data here ...
"""
```

Alternatively, you can modify the script to read from a file:

```python
# At the top of the script, replace data_lines with:
with open("your_data.txt", "r") as f:
    data_lines = f.read()
```

### Step 3: Run the Parse Script

Execute the script to process the data:

```bash
cd /root/candle_analysis
python3 examples/parse_date_data.py
```

This will:
1. Parse the data by date
2. **Accumulate data cumulatively** - each date includes all pairs from previous dates in the week
   - Example: If USD has 3 tested_low pairs on day 15, and 1 new pair on day 16, day 16 will show 4 total (3 from previous + 1 new)
3. Categorize currencies based on strength/weakness
4. Calculate strength and weakness percentages for each currency
5. Generate output showing:
   - Total count of pairs tested per currency (cumulative)
   - Tested high count and list (cumulative)
   - Tested low count and list (cumulative)
   - Strength and weakness percentages (based on cumulative counts)
   - Summary sorted by strength and weakness
6. Save results to `currency_by_date.json`

### Step 4: Review the Output

Check the generated `currency_by_date.json` file to verify the data looks correct. The structure should be:

```json
{
  "2025-12-15": {
    "currencies": {
      "USD": {
        "tested_high": [],
        "tested_high_count": 0,
        "tested_low": ["USD_CAD", "USD_EUR"],
        "tested_low_count": 2,
        "strength": 0.0,
        "weakness": 1.0
      },
      ...
    },
    "summary": {
      "by_strength": [
        {"currency": "EUR", "value": 1.0},
        ...
      ],
      "by_weakness": [
        {"currency": "USD", "value": 1.0},
        ...
      ]
    }
  },
  ...
}
```

### Step 5: Add to Historical Storage

Once you've verified the data, add it to the historical storage system:

```bash
python3 examples/add_to_history.py --input currency_by_date.json
```

This will:
- Transform each date's data to match the API response format
- Store snapshots in `data/history/strength_weakness_weekly/`
- Create one JSON file per date (e.g., `2025-12-15.json`)

### Step 6: Verify Historical Storage

Test that the data can be retrieved:

```bash
# Check that files were created
ls -la data/history/strength_weakness_weekly/

# Test retrieval (Python)
python3 -c "
from src.core.history_storage import get_snapshot
snapshot = get_snapshot('strength_weakness_weekly', '2025-12-15')
print('✓ Data retrieved successfully' if snapshot else '✗ Data not found')
"
```

## How the Categorization Logic Works

The script uses the same logic as `categorize_currencies.py` with **cumulative accumulation**:

1. **Data Accumulation (Cumulative):**
   - Data is processed chronologically by date
   - Each date includes all pairs from previous dates in the week
   - Example: 
     - Day 15: USD has 3 tested_low pairs → `tested_low_count = 3`
     - Day 16: 1 new USD pair tested low → `tested_low_count = 4` (3 from day 15 + 1 from day 16)
   - This reflects the cumulative state of the week up to that date

2. **For HIGH_BROKEN pairs:**
   - Base currency → tested high
   - Quote currency → tested low (pair name reversed)

3. **For LOW_BROKEN pairs:**
   - Base currency → tested low
   - Quote currency → tested high (pair name reversed)

4. **Strength/Weakness Calculation:**
   - `strength = tested_high_count / total_count`
   - `weakness = tested_low_count / total_count`
   - Where `total_count = tested_high_count + tested_low_count`
   - Counts are cumulative (include all previous dates in the week)

## Example: Complete Workflow

Here's a complete example of processing data:

```bash
# 1. Create a file with your data
cat > old_data.txt << 'EOF'
2025-12-15  USD_CAD (LOW_BROKEN) (FIRST TEST)
2025-12-15  EUR_USD (HIGH_BROKEN) (FIRST TEST)
2025-12-16  GBP_AUD (HIGH_BROKEN) (FIRST TEST)
EOF

# 2. Update parse_date_data.py to read from file (or paste data directly)

# 3. Run the parser
python3 examples/parse_date_data.py

# 4. Review currency_by_date.json

# 5. Add to historical storage
python3 examples/add_to_history.py --input currency_by_date.json

# 6. Verify
ls data/history/strength_weakness_weekly/
```

## Accessing the Data via API

Once stored, the data is accessible through the historical API endpoints:

1. **Get a single date:**
   ```
   GET /api/v1/history/strength_weakness_weekly?date=2025-12-15
   ```

2. **Get a date range:**
   ```
   GET /api/v1/history/strength_weakness_weekly?start_date=2025-12-15&end_date=2025-12-19
   ```

3. **Get last 10 days (default):**
   ```
   GET /api/v1/history/strength_weakness_weekly
   ```

4. **List available dates:**
   ```
   GET /api/v1/history/strength_weakness_weekly/dates
   ```

## Troubleshooting

### Issue: Dates not parsing correctly
- Ensure dates are in `YYYY-MM-DD` format
- Check for extra spaces or formatting issues

### Issue: Currency pairs not recognized
- Verify pair format is `BASE_QUOTE` (e.g., `USD_CAD`, not `USD/CAD`)
- Check for typos in currency codes

### Issue: Data not storing
- Verify `data/history/` directory exists and is writable
- Check file permissions

### Issue: Wrong endpoint identifier
- Default is `strength_weakness_weekly`
- Use `--endpoint` parameter to specify different endpoint:
  ```bash
  python3 examples/add_to_history.py --endpoint strength_weakness_monthly
  ```

## Quick Reference Prompt for AI Assistant

When you have old data to process, you can use this prompt:

```
I have historical currency strength/weakness data in this format:

[PASTE YOUR DATA HERE]

Please:
1. Process this data using the same logic as categorize_currencies.py
2. Calculate strength/weakness for each currency per date
3. Show me the results with total counts, tested high/low lists, and percentages
4. Add the data to historical storage for the strength_weakness_weekly endpoint

The data format is:
YYYY-MM-DD  INSTRUMENT (STATUS) (TEST_TYPE)
```

## Files Involved

- `examples/parse_date_data.py` - Parses text data and generates JSON
- `examples/add_to_history.py` - Adds processed data to historical storage
- `examples/categorize_currencies.py` - Original categorization logic (reference)
- `src/core/history_storage.py` - Historical storage functions
- `data/history/strength_weakness_weekly/` - Storage location for snapshots

## Notes

- **Cumulative Data**: Each date's data includes all pairs from previous dates in the week. This shows the cumulative state of the week up to that date.
- The system automatically handles currency pair normalization (reversing pairs when needed)
- Each date is stored as a separate snapshot
- If a snapshot already exists for a date, it will be overwritten
- The data format matches the API response format exactly
- All dates must be in `YYYY-MM-DD` format
- Data is processed chronologically to ensure proper accumulation

