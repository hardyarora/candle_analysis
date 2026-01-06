#!/usr/bin/env python3
"""
Script to recalculate and update body_overlap_percentage in all feedback JSON files.

This script updates the body_overlap_percentage metric using the corrected calculation
that uses the combined body range as the denominator instead of just mc1's body size.
"""
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.engulfing_metrics import calculate_body_overlap
from src.core.config import ENGULFING_FEEDBACK_DIR


def update_feedback_file(filepath: Path) -> bool:
    """
    Update body_overlap_percentage in a single feedback file.
    
    Args:
        filepath: Path to the feedback JSON file
        
    Returns:
        True if updated successfully, False otherwise
    """
    try:
        # Read the file
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check if required data exists
        if 'candles' not in data or 'metrics' not in data:
            print(f"  ⚠️  Skipping {filepath.name}: missing candles or metrics")
            return False
        
        mc1 = data['candles'].get('mc1')
        mc2 = data['candles'].get('mc2')
        
        if not mc1 or not mc2:
            print(f"  ⚠️  Skipping {filepath.name}: missing mc1 or mc2 candles")
            return False
        
        # Recalculate body_overlap_percentage
        old_value = data['metrics'].get('body_overlap_percentage')
        new_value = calculate_body_overlap(mc1, mc2)
        
        # Update the value
        data['metrics']['body_overlap_percentage'] = new_value
        
        # Write back to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"  ✓ Updated {filepath.name}: {old_value:.6f} → {new_value:.6f}")
        return True
        
    except Exception as e:
        print(f"  ✗ Error updating {filepath.name}: {e}")
        return False


def main():
    """Update all feedback JSON files."""
    feedback_dir = ENGULFING_FEEDBACK_DIR
    
    if not feedback_dir.exists():
        print(f"Feedback directory not found: {feedback_dir}")
        return
    
    # Find all JSON files
    json_files = list(feedback_dir.rglob("*.json"))
    
    if not json_files:
        print("No JSON files found in feedback directory")
        return
    
    print(f"Found {len(json_files)} feedback files to update\n")
    
    updated_count = 0
    failed_count = 0
    
    for filepath in sorted(json_files):
        if update_feedback_file(filepath):
            updated_count += 1
        else:
            failed_count += 1
    
    print(f"\n{'='*60}")
    print(f"Update complete:")
    print(f"  ✓ Successfully updated: {updated_count}")
    print(f"  ✗ Failed: {failed_count}")
    print(f"  Total: {len(json_files)}")


if __name__ == "__main__":
    main()



