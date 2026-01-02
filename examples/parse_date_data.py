import json
from collections import defaultdict

# Input data
data_lines = """2025-12-08  EUR_CHF (HIGH_BROKEN) (FIRST TEST)
2025-12-08  CAD_CHF (HIGH_BROKEN) (FIRST TEST)
2025-12-08  EUR_NZD (LOW_BROKEN) (FIRST TEST)
2025-12-08  USD_CHF (HIGH_BROKEN) (FIRST TEST)
2025-12-08  AUD_CHF (HIGH_BROKEN) (FIRST TEST)
2025-12-08  USD_CAD (LOW_BROKEN) (FIRST TEST)
2025-12-08  NZD_CAD (LOW_BROKEN) (FIRST TEST)
2025-12-08  NZD_USD (HIGH_BROKEN) (FIRST TEST)
2025-12-08  CAD_JPY (HIGH_BROKEN) (FIRST TEST)
2025-12-08  EUR_AUD (LOW_BROKEN) (FIRST TEST)
2025-12-08  GBP_CAD (LOW_BROKEN) (FIRST TEST)
2025-12-08  GBP_CHF (HIGH_BROKEN) (FIRST TEST)
2025-12-08  NZD_JPY (HIGH_BROKEN) (FIRST TEST)
2025-12-08  GBP_JPY (HIGH_BROKEN) (FIRST TEST)
2025-12-08  EUR_CAD (LOW_BROKEN) (FIRST TEST)
2025-12-08  GBP_AUD (LOW_BROKEN) (FIRST TEST)
2025-12-08  NZD_CHF (HIGH_BROKEN) (FIRST TEST)
2025-12-08  EUR_JPY (HIGH_BROKEN) (FIRST TEST)
2025-12-08  AUD_JPY (HIGH_BROKEN) (FIRST TEST)
2025-12-09  EUR_GBP (LOW_BROKEN) (FIRST TEST)
2025-12-09  GBP_NZD (LOW_BROKEN) (FIRST TEST)
2025-12-09  AUD_USD (HIGH_BROKEN) (FIRST TEST)
2025-12-09  USD_JPY (HIGH_BROKEN) (FIRST TEST)
2025-12-09  CHF_JPY (HIGH_BROKEN) (FIRST TEST)
2025-12-10  EUR_USD (HIGH_BROKEN) (FIRST TEST)
2025-12-10  GBP_USD (HIGH_BROKEN) (FIRST TEST)
2025-12-10  AUD_NZD (HIGH_BROKEN) (FIRST TEST)
2025-12-11  USD_CHF (LOW_BROKEN) (FIRST TEST)"""

def parse_data_by_date(data_lines: str) -> dict:
    """Parse the data and group by date."""
    date_data = defaultdict(lambda: {"tested_high": set(), "tested_low": set()})
    
    for line in data_lines.strip().split('\n'):
        parts = line.split()
        if len(parts) < 3:
            continue
        
        date = parts[0]
        instrument = parts[1]
        status = parts[2].strip('()')
        
        if status == "HIGH_BROKEN":
            date_data[date]["tested_high"].add(instrument)
        elif status == "LOW_BROKEN":
            date_data[date]["tested_low"].add(instrument)
    
    return date_data

def categorize_currencies_by_date(date_data: dict) -> dict:
    """Apply the same categorization logic as the original script, per date.
    
    Data is cumulative - each date includes all pairs from previous dates in the week.
    """
    result = {}
    
    # Sort dates to process chronologically
    sorted_dates = sorted(date_data.keys())
    
    # Accumulate data as we process each date
    cumulative_tested_high = set()
    cumulative_tested_low = set()
    
    for date in sorted_dates:
        # Add current date's data to cumulative sets
        cumulative_tested_high.update(date_data[date]["tested_high"])
        cumulative_tested_low.update(date_data[date]["tested_low"])
        
        # Use cumulative data for categorization
        all_tested_high = cumulative_tested_high.copy()
        all_tested_low = cumulative_tested_low.copy()
        
        # Get all unique currencies
        all_currencies = set()
        for instrument in all_tested_high | all_tested_low:
            base, quote = instrument.split("_")
            all_currencies.add(base)
            all_currencies.add(quote)
        
        currencies_dict = {}
        
        for currency in all_currencies:
            # Categorize based on position in pair (same logic as original script)
            currency_tested_high = []
            currency_tested_low = []
            
            # Process tested_high instruments
            for instrument in all_tested_high:
                base, quote = instrument.split("_")
                if base == currency:
                    currency_tested_high.append(instrument)
                elif quote == currency:
                    # Reverse the name when quote currency goes to tested_low
                    currency_tested_low.append(f"{quote}_{base}")
            
            # Process tested_low instruments
            for instrument in all_tested_low:
                base, quote = instrument.split("_")
                if base == currency:
                    currency_tested_low.append(instrument)
                elif quote == currency:
                    # Reverse the name when quote currency goes to tested_high
                    currency_tested_high.append(f"{quote}_{base}")
            
            tested_high_list = sorted(set(currency_tested_high))
            tested_low_list = sorted(set(currency_tested_low))
            tested_high_count = len(tested_high_list)
            tested_low_count = len(tested_low_list)
            total = tested_high_count + tested_low_count
            
            currencies_dict[currency] = {
                "tested_high": tested_high_list,
                "tested_high_count": tested_high_count,
                "tested_low": tested_low_list,
                "tested_low_count": tested_low_count,
                "strength": tested_high_count / total if total > 0 else 0.0,
                "weakness": tested_low_count / total if total > 0 else 0.0
            }
        
        # Create summary section matching API format
        by_strength = sorted(
            [{"currency": curr, "value": data["strength"]} 
             for curr, data in currencies_dict.items()],
            key=lambda x: x["value"],
            reverse=True
        )
        by_weakness = sorted(
            [{"currency": curr, "value": data["weakness"]} 
             for curr, data in currencies_dict.items()],
            key=lambda x: x["value"],
            reverse=True
        )
        
        result[date] = {
            "currencies": currencies_dict,
            "summary": {
                "by_strength": by_strength,
                "by_weakness": by_weakness
            }
        }
    
    return result

def print_results(result: dict):
    """Print results matching the API format with detailed information."""
    for date, date_data in sorted(result.items()):
        currencies = date_data["currencies"]
        summary = date_data["summary"]
        
        print(f"\n{'='*70}")
        print(f"DATE: {date}")
        print(f"{'='*70}\n")
        
        print("=== Currency Details ===\n")
        for currency, data in sorted(currencies.items()):
            total = data['tested_high_count'] + data['tested_low_count']
            print(f"{currency}:")
            print(f"  Total Count: {total}")
            print(f"  Tested High: {data['tested_high_count']} - {data['tested_high']}")
            print(f"  Tested Low:  {data['tested_low_count']} - {data['tested_low']}")
            print(f"  Strength: {data['strength']:.2%} ({data['strength']:.4f})")
            print(f"  Weakness: {data['weakness']:.2%} ({data['weakness']:.4f})")
            print()
        
        # Summary
        print("=== SUMMARY ===\n")
        print("By Strength (descending):")
        for item in summary["by_strength"]:
            print(f"  {item['currency']}: {item['value']:.2%} ({item['value']:.4f})")
        
        print("\nBy Weakness (descending):")
        for item in summary["by_weakness"]:
            print(f"  {item['currency']}: {item['value']:.2%} ({item['value']:.4f})")
        print()

if __name__ == "__main__":
    date_data = parse_data_by_date(data_lines)
    result = categorize_currencies_by_date(date_data)
    print_results(result)
    
    # Also save to JSON
    output_file = "currency_by_date.json"
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nResults saved to {output_file}")

