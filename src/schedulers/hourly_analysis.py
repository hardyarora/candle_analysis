#!/usr/bin/env python3
"""
Hourly scheduler for OANDA candle analysis.

This script:
1. Fetches daily and weekly data from OANDA API
2. Processes it to get weakness/strength patterns
3. Stores results in PostgreSQL database as JSON
4. Runs every hour (intended to be called by cron)
"""
import sys
import logging
import argparse
from datetime import datetime
from pathlib import Path

from ..core.db_storage import run_and_store_analysis
from ..core.database import init_connection_pool, test_connection, close_connection_pool
from ..core.config import LOGS_DIR, DEFAULT_IGNORE_CANDLES
from ..utils.timeframe import normalize_timeframe


def setup_logging() -> logging.Logger:
    """
    Set up logging to both file and console.
    
    Returns:
        Configured logger instance
    """
    # Create logs directory with date subdirectory
    today = datetime.now().strftime("%Y-%m-%d")
    log_dir = LOGS_DIR / today
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"hourly_analysis_{timestamp}.log"
    
    # Configure logger
    logger = logging.getLogger("hourly_analysis")
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


def run_hourly_analysis(
    daily_timeframes: list = None,
    weekly_timeframes: list = None,
    ignore_candles: int = DEFAULT_IGNORE_CANDLES,
    force_oanda: bool = False,
    logger: logging.Logger = None
) -> dict:
    """
    Run hourly analysis for specified timeframes.
    
    Args:
        daily_timeframes: List of daily timeframes to analyze (e.g., ['1D', '2D', '3D', '4D'])
        weekly_timeframes: List of weekly timeframes to analyze (e.g., ['W', '2W'])
        ignore_candles: Number of candles to ignore
        force_oanda: Force loading from OANDA API
        logger: Logger instance
        
    Returns:
        Dictionary with execution results
    """
    if logger is None:
        logger = logging.getLogger("hourly_analysis")
    
    if daily_timeframes is None:
        daily_timeframes = ['1D', '2D', '3D', '4D']
    
    if weekly_timeframes is None:
        weekly_timeframes = ['W']
    
    results = {
        "success": [],
        "failed": [],
        "total": 0,
        "successful": 0,
        "failed_count": 0
    }
    
    # Test database connection
    logger.info("Testing database connection...")
    if not test_connection():
        logger.error("Database connection test failed. Aborting.")
        return results
    
    logger.info("Database connection successful")
    
    # Process daily timeframes
    for timeframe in daily_timeframes:
        try:
            normalized_tf = normalize_timeframe(timeframe)
            logger.info(f"Processing daily timeframe: {normalized_tf}")
            
            snapshot_id = run_and_store_analysis(
                timeframe=normalized_tf,
                granularity='D',
                ignore_candles=ignore_candles,
                force_oanda=force_oanda
            )
            
            if snapshot_id:
                results["success"].append({
                    "timeframe": normalized_tf,
                    "granularity": "D",
                    "snapshot_id": snapshot_id
                })
                results["successful"] += 1
                logger.info(f"✓ Successfully stored {normalized_tf} (snapshot_id={snapshot_id})")
            else:
                results["failed"].append({
                    "timeframe": normalized_tf,
                    "granularity": "D",
                    "error": "Failed to store snapshot"
                })
                results["failed_count"] += 1
                logger.error(f"✗ Failed to store {normalized_tf}")
                
        except Exception as e:
            results["failed"].append({
                "timeframe": timeframe,
                "granularity": "D",
                "error": str(e)
            })
            results["failed_count"] += 1
            logger.error(f"✗ Error processing {timeframe}: {e}", exc_info=True)
        
        results["total"] += 1
    
    # Process weekly timeframes
    for timeframe in weekly_timeframes:
        try:
            # For weekly, we need to handle differently
            # Weekly timeframe like 'W' means 1 week, '2W' means 2 weeks
            if timeframe.upper() == 'W':
                normalized_tf = '1W'
            else:
                normalized_tf = timeframe.upper()
            
            logger.info(f"Processing weekly timeframe: {normalized_tf}")
            
            # Note: analyze_all_currencies currently only supports daily timeframes
            # For weekly, we would need to extend the analyzer or use a different approach
            # For now, we'll log a warning and skip
            logger.warning(f"Weekly timeframe {normalized_tf} not yet supported by analyzer. Skipping.")
            results["failed"].append({
                "timeframe": normalized_tf,
                "granularity": "W",
                "error": "Weekly analysis not yet implemented"
            })
            results["failed_count"] += 1
            
        except Exception as e:
            results["failed"].append({
                "timeframe": timeframe,
                "granularity": "W",
                "error": str(e)
            })
            results["failed_count"] += 1
            logger.error(f"✗ Error processing weekly {timeframe}: {e}", exc_info=True)
        
        results["total"] += 1
    
    return results


def main():
    """Main entry point for the hourly analysis scheduler."""
    parser = argparse.ArgumentParser(
        description="Hourly OANDA candle analysis scheduler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s
  %(prog)s --daily 1D 2D 3D 4D
  %(prog)s --weekly W
  %(prog)s --force-oanda
  %(prog)s --ignore-candles 0
        """
    )
    
    parser.add_argument(
        "--daily",
        nargs="+",
        default=['1D', '2D', '3D', '4D'],
        help="Daily timeframes to analyze (default: 1D 2D 3D 4D)"
    )
    
    parser.add_argument(
        "--weekly",
        nargs="+",
        default=['W'],
        help="Weekly timeframes to analyze (default: W)"
    )
    
    parser.add_argument(
        "--ignore-candles",
        type=int,
        default=DEFAULT_IGNORE_CANDLES,
        help=f"Number of candles to ignore (default: {DEFAULT_IGNORE_CANDLES})"
    )
    
    parser.add_argument(
        "--force-oanda",
        action="store_true",
        help="Force loading from OANDA API instead of cache"
    )
    
    args = parser.parse_args()
    
    # Set up logging
    logger = setup_logging()
    
    try:
        logger.info("=" * 60)
        logger.info("Hourly OANDA Analysis Scheduler")
        logger.info("=" * 60)
        logger.info(f"Daily timeframes: {args.daily}")
        logger.info(f"Weekly timeframes: {args.weekly}")
        logger.info(f"Ignore candles: {args.ignore_candles}")
        logger.info(f"Force OANDA: {args.force_oanda}")
        
        # Initialize database connection pool
        logger.info("Initializing database connection pool...")
        init_connection_pool()
        
        # Run analysis
        results = run_hourly_analysis(
            daily_timeframes=args.daily,
            weekly_timeframes=args.weekly,
            ignore_candles=args.ignore_candles,
            force_oanda=args.force_oanda,
            logger=logger
        )
        
        # Summary
        logger.info("=" * 60)
        logger.info("Execution Summary")
        logger.info("=" * 60)
        logger.info(f"Total timeframes: {results['total']}")
        logger.info(f"Successful: {results['successful']}")
        logger.info(f"Failed: {results['failed_count']}")
        
        if results['success']:
            logger.info("Successful executions:")
            for success in results['success']:
                logger.info(f"  ✓ {success['timeframe']} ({success['granularity']}) - snapshot_id={success['snapshot_id']}")
        
        if results['failed']:
            logger.warning("Failed executions:")
            for failure in results['failed']:
                logger.warning(f"  ✗ {failure['timeframe']} ({failure['granularity']}): {failure['error']}")
        
        if results['failed_count'] == 0:
            logger.info("All analyses completed successfully")
            sys.exit(0)
        else:
            logger.warning("Some analyses failed")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Analysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Close database connection pool
        close_connection_pool()


if __name__ == "__main__":
    main()
