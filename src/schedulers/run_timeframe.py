#!/usr/bin/env python3
"""
Scheduler script for running candle analysis on a specific timeframe.

This script:
1. Backs up existing analysis for the timeframe
2. Runs analysis for all currencies
3. Saves new analysis to latest/{timeframe}/
4. Logs execution to logs/{date}/
"""
import argparse
import sys
import logging
from datetime import datetime
from pathlib import Path

from ..core.candle_analyzer import analyze_all_currencies
from ..core.file_manager import backup_current_analysis, save_analysis
from ..core.config import LOGS_DIR, DEFAULT_IGNORE_CANDLES
from ..utils.timeframe import normalize_timeframe


def setup_logging(timeframe: str) -> logging.Logger:
    """
    Set up logging to both file and console.
    
    Args:
        timeframe: Normalized timeframe for log filename
        
    Returns:
        Configured logger instance
    """
    # Create logs directory with date subdirectory
    today = datetime.now().strftime("%Y-%m-%d")
    log_dir = LOGS_DIR / today
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"analysis_{timeframe}_{timestamp}.log"
    
    # Configure logger
    logger = logging.getLogger(f"candle_analysis_{timeframe}")
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger


def main():
    """Main entry point for the scheduler script."""
    parser = argparse.ArgumentParser(
        description="Run candle analysis for a specific timeframe",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --timeframe 1D
  %(prog)s --timeframe 2D --ignore-candles 0
  %(prog)s -t 3D
  %(prog)s -t 4d
        """
    )
    
    parser.add_argument(
        "--timeframe", "-t",
        required=True,
        help="Timeframe: 1D, 2D, 3D, or 4D (case insensitive, D/1D/1d all work)"
    )
    
    parser.add_argument(
        "--ignore-candles",
        type=int,
        default=DEFAULT_IGNORE_CANDLES,
        help=f"Number of candles to ignore at the end (default: {DEFAULT_IGNORE_CANDLES})"
    )
    
    args = parser.parse_args()
    
    try:
        # Normalize timeframe
        normalized_tf = normalize_timeframe(args.timeframe)
        
        # Set up logging
        logger = setup_logging(normalized_tf)
        
        logger.info(f"Starting candle analysis for timeframe: {normalized_tf}")
        logger.info(f"Ignore candles: {args.ignore_candles}")
        
        # Step 1: Backup existing analysis
        logger.info("Backing up existing analysis...")
        try:
            backup_dir = backup_current_analysis(normalized_tf)
            logger.info(f"Backup created at: {backup_dir}")
        except Exception as e:
            logger.warning(f"Backup failed (may not exist): {e}")
        
        # Step 2: Run analysis
        logger.info("Running analysis for all currencies...")
        try:
            analysis_data = analyze_all_currencies(normalized_tf, args.ignore_candles)
            logger.info(f"Analysis completed. Processed {len(analysis_data['instruments'])} instruments")
        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)
            sys.exit(1)
        
        # Step 3: Save analysis
        logger.info("Saving analysis results...")
        try:
            saved_path = save_analysis(analysis_data, normalized_tf)
            logger.info(f"Analysis saved to: {saved_path}")
        except Exception as e:
            logger.error(f"Failed to save analysis: {e}", exc_info=True)
            sys.exit(1)
        
        logger.info("Analysis completed successfully")
        
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
