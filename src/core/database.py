"""
Database connection and utilities for PostgreSQL storage.
"""
import os
import logging
from typing import Optional, Dict, List, Any
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2.pool import ThreadedConnectionPool
from psycopg2 import sql

logger = logging.getLogger("candle_analysis_api.database")

# Database connection pool
_connection_pool: Optional[ThreadedConnectionPool] = None


def get_db_config() -> Dict[str, str]:
    """
    Get database configuration from environment variables.
    
    Returns:
        Dictionary with database connection parameters
    """
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "database": os.getenv("DB_NAME", "candle_analysis"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
    }


def init_connection_pool(min_conn: int = 1, max_conn: int = 10) -> ThreadedConnectionPool:
    """
    Initialize the database connection pool.
    
    Args:
        min_conn: Minimum number of connections in the pool
        max_conn: Maximum number of connections in the pool
        
    Returns:
        ThreadedConnectionPool instance
        
    Raises:
        psycopg2.Error: If connection fails
    """
    global _connection_pool
    
    if _connection_pool is not None:
        return _connection_pool
    
    config = get_db_config()
    
    try:
        _connection_pool = ThreadedConnectionPool(
            min_conn,
            max_conn,
            host=config["host"],
            port=config["port"],
            database=config["database"],
            user=config["user"],
            password=config["password"],
        )
        logger.info(f"Database connection pool initialized: {config['database']}@{config['host']}:{config['port']}")
        return _connection_pool
    except Exception as e:
        logger.error(f"Failed to initialize database connection pool: {e}")
        raise


def get_connection():
    """
    Get a connection from the pool.
    
    Returns:
        psycopg2 connection object
        
    Raises:
        RuntimeError: If pool is not initialized
    """
    if _connection_pool is None:
        init_connection_pool()
    
    return _connection_pool.getconn()


def return_connection(conn):
    """
    Return a connection to the pool.
    
    Args:
        conn: psycopg2 connection object
    """
    if _connection_pool is not None:
        _connection_pool.putconn(conn)


@contextmanager
def get_db_connection():
    """
    Context manager for database connections.
    
    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ...")
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        return_connection(conn)


def close_connection_pool():
    """
    Close all connections in the pool.
    """
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("Database connection pool closed")


def test_connection() -> bool:
    """
    Test database connection.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


def execute_schema_file(schema_file_path: str) -> bool:
    """
    Execute a SQL schema file to initialize the database.
    
    Args:
        schema_file_path: Path to the SQL schema file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        with open(schema_file_path, 'r') as f:
            schema_sql = f.read()
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(schema_sql)
            conn.commit()
            logger.info(f"Schema file executed successfully: {schema_file_path}")
            return True
    except Exception as e:
        logger.error(f"Failed to execute schema file {schema_file_path}: {e}")
        return False
