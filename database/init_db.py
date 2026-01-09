#!/usr/bin/env python3
"""
Initialize PostgreSQL database with schema.

This script creates the database schema for storing candle analysis results.
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.database import init_connection_pool, execute_schema_file, test_connection, close_connection_pool
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Initialize the database schema."""
    schema_file = project_root / "database" / "schema.sql"
    
    if not schema_file.exists():
        logger.error(f"Schema file not found: {schema_file}")
        sys.exit(1)
    
    exit_code = 1
    try:
        logger.info("Initializing database connection pool...")
        try:
            init_connection_pool()
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            return 1
        
        logger.info("Testing database connection...")
        if not test_connection():
            logger.error("Database connection test failed")
            return 1
        
        logger.info(f"Executing schema file: {schema_file}")
        if execute_schema_file(str(schema_file)):
            logger.info("Database schema initialized successfully")
            exit_code = 0
        else:
            logger.error("Failed to initialize database schema")
            exit_code = 1
    finally:
        close_connection_pool()
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
