"""
Logging configuration for the FastAPI application.
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..core.config import LOGS_DIR


def setup_api_logging(log_level: str = "DEBUG") -> logging.Logger:
    """
    Set up logging for the FastAPI API application.
    
    Configures logging to both file and console with appropriate formatters.
    Logs are stored in data/logs/api/ directory with date-based subdirectories.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        Configured logger instance
    """
    # Create logs directory with date subdirectory
    today = datetime.now().strftime("%Y-%m-%d")
    api_log_dir = LOGS_DIR / "api" / today
    api_log_dir.mkdir(parents=True, exist_ok=True)
    
    # Log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = api_log_dir / f"api_{timestamp}.log"
    
    # Get root logger for the application
    logger = logging.getLogger("candle_analysis_api")
    logger.setLevel(getattr(logging, log_level.upper(), logging.DEBUG))
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    # File handler with detailed format
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)  # Always log everything to file
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console handler with simpler format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.DEBUG))
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Also configure uvicorn loggers
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.setLevel(logging.DEBUG)
    uvicorn_logger.addHandler(file_handler)
    uvicorn_logger.addHandler(console_handler)
    
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.setLevel(logging.DEBUG)
    uvicorn_access.addHandler(file_handler)
    uvicorn_access.addHandler(console_handler)
    
    logger.info(f"Logging configured. Log file: {log_file}")
    logger.debug(f"Log level: {log_level}")
    
    return logger


