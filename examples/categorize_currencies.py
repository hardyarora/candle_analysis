import json

def categorize_currencies(input_file="pullback_weekly.json", output_file="currency_categorized.json"):
    with open(input_file, "r") as f:
        data = json.load(f)
    
    all_currencies = data.get("all_currencies_strength_weakness", {})
    result = {}
    
    for currency, details in all_currencies.items():
        # Collect all tested_high and tested_low instruments
        all_tested_high = set()
        all_tested_low = set()
        
        if "strength_details" in details:
            all_tested_high.update(details["strength_details"].get("tested_high_instruments", []))
            all_tested_low.update(details["strength_details"].get("tested_low_instruments", []))
        
        if "weakness_details" in details:
            all_tested_high.update(details["weakness_details"].get("tested_high_instruments", []))
            all_tested_low.update(details["weakness_details"].get("tested_low_instruments", []))
        
        # Categorize based on position in pair
        currency_tested_high = []
        currency_tested_low = []
        
        for instrument in all_tested_high:
            base, quote = instrument.split("_")
            if base == currency:
                currency_tested_high.append(instrument)
            elif quote == currency:
                # Reverse the name when quote currency goes to tested_low
                currency_tested_low.append(f"{quote}_{base}")
        
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
        
        result[currency] = {
            "tested_high": tested_high_list,
            "tested_high_count": tested_high_count,
            "tested_low": tested_low_list,
            "tested_low_count": tested_low_count,
            "strength": tested_high_count / total if total > 0 else 0,
            "weakness": tested_low_count / total if total > 0 else 0
        }
    
    # Print to console
    print("\n=== Currency Pair Categorization ===\n")
    for currency, data in sorted(result.items()):
        print(f"{currency}:")
        print(f"  tested_high ({data['tested_high_count']}): {data['tested_high']}")
        print(f"  tested_low ({data['tested_low_count']}): {data['tested_low']}")
        print(f"  strength: {data['strength']:.2%}, weakness: {data['weakness']:.2%}")
        print()
    
    # Summary
    print("=== SUMMARY ===\n")
    by_strength = sorted(result.items(), key=lambda x: x[1]['strength'], reverse=True)
    by_weakness = sorted(result.items(), key=lambda x: x[1]['weakness'], reverse=True)
    
    print("Strength (descending):")
    for currency, data in by_strength:
        print(f"  {currency}: {data['strength']:.2%}")
    
    print("\nWeakness (descending):")
    for currency, data in by_weakness:
        print(f"  {currency}: {data['weakness']:.2%}")
    print()
    
    # Save to JSON
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Results saved to {output_file}")

if __name__ == "__main__":
    categorize_currencies()

