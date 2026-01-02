#!/usr/bin/env python3
"""
Scheduler script for capturing historical snapshots of API endpoints.

This script:
1. Makes requests to configured endpoints
2. Stores their responses as historical snapshots
3. Logs execution to logs/{date}/
"""
import sys
import logging
import httpx
from datetime import datetime
from pathlib import Path

from ..core.history_storage import store_snapshot
from ..core.config import LOGS_DIR


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
    log_file = log_dir / f"history_capture_{timestamp}.log"
    
    # Configure logger
    logger = logging.getLogger("history_capture")
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


def capture_endpoints(base_url: str = "http://localhost:8000", logger: logging.Logger = None) -> dict:
    """
    Capture historical snapshots for all configured endpoints.
    
    Args:
        base_url: Base URL of the API (default: http://localhost:8000)
        logger: Logger instance (optional)
        
    Returns:
        Dictionary with capture results
    """
    if logger is None:
        logger = logging.getLogger("history_capture")
    
    # Map endpoint identifiers to URLs
    endpoint_url_map = {
        "strength_weakness_weekly": "/api/candle_analysis/api/v1/strength-weakness?period=weekly",
        "strength_weakness_monthly": "/api/candle_analysis/api/v1/strength-weakness?period=monthly",
        "pullback_weekly": "/api/candle_analysis/api/v1/pullback?period=weekly",
        "pullback_monthly": "/api/candle_analysis/api/v1/pullback?period=monthly",
        "analysis_1D": "/api/candle_analysis/api/v1/analysis/1D",
        "analysis_2D": "/api/candle_analysis/api/v1/analysis/2D",
        "analysis_3D": "/api/candle_analysis/api/v1/analysis/3D",
        "analysis_4D": "/api/candle_analysis/api/v1/analysis/4D",
    }
    
    captured = []
    errors = []
    capture_date = datetime.now().strftime("%Y-%m-%d")
    
    logger.info(f"Starting history capture for {len(endpoint_url_map)} endpoints")
    logger.info(f"Capture date: {capture_date}")
    logger.info(f"Base URL: {base_url}")
    
    async def capture_all():
        async with httpx.AsyncClient(timeout=30.0) as client:
            for endpoint_id, url in endpoint_url_map.items():
                full_url = f"{base_url}{url}"
                logger.info(f"Capturing {endpoint_id} from {full_url}")
                
                try:
                    response = await client.get(full_url)
                    if response.status_code == 200:
                        data = response.json()
                        store_snapshot(endpoint_id, data, capture_date)
                        captured.append({
                            "endpoint": endpoint_id,
                            "date": capture_date,
                            "status": "success"
                        })
                        logger.info(f"✓ Successfully captured {endpoint_id}")
                    else:
                        error_msg = f"HTTP {response.status_code}: {response.text[:100]}"
                        errors.append(f"{endpoint_id}: {error_msg}")
                        logger.error(f"✗ Failed to capture {endpoint_id}: {error_msg}")
                except Exception as e:
                    error_msg = str(e)
                    errors.append(f"{endpoint_id}: {error_msg}")
                    logger.error(f"✗ Error capturing {endpoint_id}: {error_msg}", exc_info=True)
    
    # Run async capture
    import asyncio
    asyncio.run(capture_all())
    
    return {
        "success": len(errors) == 0,
        "captured": captured,
        "errors": errors,
        "total": len(endpoint_url_map),
        "successful": len(captured),
        "failed": len(errors)
    }


def main():
    """Main entry point for the history capture scheduler."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Capture historical snapshots of API endpoints",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s
  %(prog)s --base-url http://45.33.12.68
  %(prog)s --base-url http://localhost:8000
        """
    )
    
    parser.add_argument(
        "--base-url",
        type=str,
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)"
    )
    
    args = parser.parse_args()
    
    # Set up logging
    logger = setup_logging()
    
    try:
        logger.info("=" * 60)
        logger.info("History Capture Scheduler")
        logger.info("=" * 60)
        
        # Capture endpoints
        results = capture_endpoints(args.base_url, logger)
        
        # Summary
        logger.info("=" * 60)
        logger.info("Capture Summary")
        logger.info("=" * 60)
        logger.info(f"Total endpoints: {results['total']}")
        logger.info(f"Successful: {results['successful']}")
        logger.info(f"Failed: {results['failed']}")
        
        if results['errors']:
            logger.warning("Errors encountered:")
            for error in results['errors']:
                logger.warning(f"  - {error}")
        
        if results['success']:
            logger.info("History capture completed successfully")
            sys.exit(0)
        else:
            logger.warning("History capture completed with errors")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Capture interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()





