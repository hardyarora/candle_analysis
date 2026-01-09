"""
Database storage for candle analysis results.
Stores hourly snapshots of daily and weekly analysis in PostgreSQL.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from psycopg2.extras import Json, RealDictCursor

from .database import get_db_connection
from .candle_analyzer import analyze_all_currencies
from .config import DEFAULT_IGNORE_CANDLES

logger = logging.getLogger("candle_analysis_api.db_storage")


def extract_patterns_from_analysis(analysis_data: Dict, snapshot_id: int, snapshot_timestamp: datetime, timeframe: str, granularity: str) -> List[Dict]:
    """
    Extract currency patterns from analysis data for storage in currency_patterns table.
    
    Args:
        analysis_data: Full analysis data dictionary
        snapshot_id: ID of the snapshot record
        snapshot_timestamp: Timestamp of the snapshot
        timeframe: Timeframe string (e.g., '1D', 'W')
        granularity: Granularity ('D' or 'W')
        
    Returns:
        List of pattern dictionaries ready for insertion
    """
    patterns = []
    instruments = analysis_data.get("instruments", [])
    pattern_instruments_map = analysis_data.get("patterns", {})
    
    # Build reverse mapping: instrument -> pattern types
    instrument_to_patterns = {}
    for pattern_type, instrument_list in pattern_instruments_map.items():
        for instrument in instrument_list:
            if instrument not in instrument_to_patterns:
                instrument_to_patterns[instrument] = []
            instrument_to_patterns[instrument].append(pattern_type)
    
    # Extract patterns for each instrument
    for instrument_data in instruments:
        instrument = instrument_data.get("instrument", "").replace("_", "")
        if not instrument:
            continue
        
        # Get pattern types for this instrument
        pattern_types = instrument_to_patterns.get(instrument, [])
        
        # If no pattern, check relation for basic patterns
        relation = instrument_data.get("relation", "")
        if not pattern_types and relation and relation != "neutral":
            # Extract basic pattern from relation
            if "upclose" in relation.lower():
                pattern_types = ["upclose"]
            elif "downclose" in relation.lower():
                pattern_types = ["downclose"]
        
        # Get candle data
        mc1 = instrument_data.get("mc1", {})
        mc2 = instrument_data.get("mc2", {})
        
        # Create pattern record for each pattern type
        for pattern_type in pattern_types:
            patterns.append({
                "snapshot_id": snapshot_id,
                "snapshot_timestamp": snapshot_timestamp,
                "timeframe": timeframe,
                "granularity": granularity,
                "instrument": instrument,
                "pattern_type": pattern_type,
                "relation": relation,
                "color": instrument_data.get("color", ""),
                "mc1_open": mc1.get("open"),
                "mc1_high": mc1.get("high"),
                "mc1_low": mc1.get("low"),
                "mc1_close": mc1.get("close"),
                "mc2_open": mc2.get("open"),
                "mc2_high": mc2.get("high"),
                "mc2_low": mc2.get("low"),
                "mc2_close": mc2.get("close"),
            })
        
        # If no patterns found, still create a record with relation
        if not patterns or not any(p["instrument"] == instrument for p in patterns):
            patterns.append({
                "snapshot_id": snapshot_id,
                "snapshot_timestamp": snapshot_timestamp,
                "timeframe": timeframe,
                "granularity": granularity,
                "instrument": instrument,
                "pattern_type": relation if relation else "neutral",
                "relation": relation,
                "color": instrument_data.get("color", ""),
                "mc1_open": mc1.get("open"),
                "mc1_high": mc1.get("high"),
                "mc1_low": mc1.get("low"),
                "mc1_close": mc1.get("close"),
                "mc2_open": mc2.get("open"),
                "mc2_high": mc2.get("high"),
                "mc2_low": mc2.get("low"),
                "mc2_close": mc2.get("close"),
            })
    
    return patterns


def store_analysis_snapshot(
    timeframe: str,
    granularity: str,
    analysis_data: Dict,
    snapshot_timestamp: Optional[datetime] = None,
    ignore_candles: int = DEFAULT_IGNORE_CANDLES
) -> Optional[int]:
    """
    Store an analysis snapshot in the database.
    
    Args:
        timeframe: Timeframe string (e.g., '1D', '2D', 'W')
        granularity: Granularity ('D' for daily, 'W' for weekly)
        analysis_data: Full analysis data dictionary
        snapshot_timestamp: Timestamp for the snapshot (default: current time)
        ignore_candles: Number of candles ignored in analysis
        
    Returns:
        ID of the inserted snapshot record, or None if insertion failed
    """
    if snapshot_timestamp is None:
        snapshot_timestamp = datetime.now()
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Insert into candle_analysis_snapshots
            insert_query = """
                INSERT INTO candle_analysis_snapshots 
                (snapshot_timestamp, timeframe, granularity, analysis_data, ignore_candles)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (snapshot_timestamp, timeframe) 
                DO UPDATE SET 
                    analysis_data = EXCLUDED.analysis_data,
                    ignore_candles = EXCLUDED.ignore_candles,
                    created_at = CURRENT_TIMESTAMP
                RETURNING id
            """
            
            cursor.execute(
                insert_query,
                (
                    snapshot_timestamp,
                    timeframe,
                    granularity,
                    Json(analysis_data),
                    ignore_candles
                )
            )
            
            snapshot_id = cursor.fetchone()[0]
            
            # Extract and insert patterns
            patterns = extract_patterns_from_analysis(
                analysis_data, snapshot_id, snapshot_timestamp, timeframe, granularity
            )
            
            if patterns:
                # Delete existing patterns for this snapshot
                cursor.execute(
                    "DELETE FROM currency_patterns WHERE snapshot_id = %s",
                    (snapshot_id,)
                )
                
                # Insert new patterns
                pattern_insert = """
                    INSERT INTO currency_patterns 
                    (snapshot_id, snapshot_timestamp, timeframe, granularity, instrument, 
                     pattern_type, relation, color, mc1_open, mc1_high, mc1_low, mc1_close,
                     mc2_open, mc2_high, mc2_low, mc2_close)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                for pattern in patterns:
                    cursor.execute(
                        pattern_insert,
                        (
                            pattern["snapshot_id"],
                            pattern["snapshot_timestamp"],
                            pattern["timeframe"],
                            pattern["granularity"],
                            pattern["instrument"],
                            pattern["pattern_type"],
                            pattern["relation"],
                            pattern["color"],
                            pattern["mc1_open"],
                            pattern["mc1_high"],
                            pattern["mc1_low"],
                            pattern["mc1_close"],
                            pattern["mc2_open"],
                            pattern["mc2_high"],
                            pattern["mc2_low"],
                            pattern["mc2_close"],
                        )
                    )
            
            conn.commit()
            logger.info(f"Stored analysis snapshot: timeframe={timeframe}, granularity={granularity}, snapshot_id={snapshot_id}")
            return snapshot_id
            
    except Exception as e:
        logger.error(f"Failed to store analysis snapshot: {e}", exc_info=True)
        return None


def get_latest_snapshot(timeframe: str) -> Optional[Dict]:
    """
    Get the latest analysis snapshot for a timeframe.
    
    Args:
        timeframe: Timeframe string (e.g., '1D', 'W')
        
    Returns:
        Dictionary with snapshot data, or None if not found
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute(
                """
                SELECT id, snapshot_timestamp, timeframe, granularity, 
                       analysis_data, ignore_candles, created_at
                FROM candle_analysis_snapshots
                WHERE timeframe = %s
                ORDER BY snapshot_timestamp DESC
                LIMIT 1
                """,
                (timeframe,)
            )
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
            
    except Exception as e:
        logger.error(f"Failed to get latest snapshot: {e}", exc_info=True)
        return None


def get_snapshots_range(
    timeframe: str,
    start_time: datetime,
    end_time: datetime
) -> List[Dict]:
    """
    Get snapshots within a time range for a timeframe.
    
    Args:
        timeframe: Timeframe string
        start_time: Start timestamp
        end_time: End timestamp
        
    Returns:
        List of snapshot dictionaries
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute(
                """
                SELECT id, snapshot_timestamp, timeframe, granularity,
                       analysis_data, ignore_candles, created_at
                FROM candle_analysis_snapshots
                WHERE timeframe = %s
                    AND snapshot_timestamp >= %s
                    AND snapshot_timestamp <= %s
                ORDER BY snapshot_timestamp DESC
                """,
                (timeframe, start_time, end_time)
            )
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
            
    except Exception as e:
        logger.error(f"Failed to get snapshots range: {e}", exc_info=True)
        return []


def run_and_store_analysis(
    timeframe: str,
    granularity: str,
    ignore_candles: int = DEFAULT_IGNORE_CANDLES,
    force_oanda: bool = False
) -> Optional[int]:
    """
    Run analysis and store results in the database.
    
    Args:
        timeframe: Timeframe string (e.g., '1D', '2D', 'W')
        granularity: Granularity ('D' or 'W')
        ignore_candles: Number of candles to ignore
        force_oanda: Force loading from OANDA API instead of cache
        
    Returns:
        ID of the stored snapshot, or None if failed
    """
    logger.info(f"Running analysis for timeframe={timeframe}, granularity={granularity}")
    
    try:
        # Run analysis
        analysis_data = analyze_all_currencies(timeframe, ignore_candles, force_oanda=force_oanda)
        
        # Store in database
        snapshot_id = store_analysis_snapshot(
            timeframe=timeframe,
            granularity=granularity,
            analysis_data=analysis_data,
            ignore_candles=ignore_candles
        )
        
        return snapshot_id
        
    except Exception as e:
        logger.error(f"Failed to run and store analysis: {e}", exc_info=True)
        return None


def store_strength_weakness_snapshot(
    period: str,
    response_data: Dict,
    snapshot_timestamp: Optional[datetime] = None,
    ignore_candles: int = 0
) -> Optional[int]:
    """
    Store a strength-weakness snapshot in the database.
    
    Args:
        period: Period string ('daily', 'weekly', 'monthly')
        response_data: Full strength-weakness response data dictionary
        snapshot_timestamp: Timestamp for the snapshot (default: current time)
        ignore_candles: Number of candles ignored in analysis
        
    Returns:
        ID of the inserted snapshot record, or None if insertion failed
    """
    if snapshot_timestamp is None:
        snapshot_timestamp = datetime.now()
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Insert into strength_weakness_snapshots
            insert_query = """
                INSERT INTO strength_weakness_snapshots 
                (snapshot_timestamp, period, ignore_candles, response_data)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (snapshot_timestamp, period) 
                DO UPDATE SET 
                    response_data = EXCLUDED.response_data,
                    ignore_candles = EXCLUDED.ignore_candles,
                    created_at = CURRENT_TIMESTAMP
                RETURNING id
            """
            
            cursor.execute(
                insert_query,
                (
                    snapshot_timestamp,
                    period,
                    ignore_candles,
                    Json(response_data)
                )
            )
            
            snapshot_id = cursor.fetchone()[0]
            
            # Extract and insert currency data
            currencies = response_data.get("currencies", {})
            
            if currencies:
                # Delete existing currency data for this snapshot
                cursor.execute(
                    "DELETE FROM currency_strength_weakness WHERE snapshot_id = %s",
                    (snapshot_id,)
                )
                
                # Insert currency data
                currency_insert = """
                    INSERT INTO currency_strength_weakness 
                    (snapshot_id, snapshot_timestamp, period, currency, 
                     tested_high_count, tested_low_count, strength, weakness,
                     tested_high_instruments, tested_low_instruments)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                for currency, data in currencies.items():
                    if isinstance(data, dict):
                        cursor.execute(
                            currency_insert,
                            (
                                snapshot_id,
                                snapshot_timestamp,
                                period,
                                currency,
                                data.get("tested_high_count", 0),
                                data.get("tested_low_count", 0),
                                data.get("strength"),
                                data.get("weakness"),
                                data.get("tested_high", []),
                                data.get("tested_low", []),
                            )
                        )
            
            conn.commit()
            logger.info(f"Stored strength-weakness snapshot: period={period}, snapshot_id={snapshot_id}")
            return snapshot_id
            
    except Exception as e:
        logger.error(f"Failed to store strength-weakness snapshot: {e}", exc_info=True)
        return None


def get_latest_strength_weakness(period: str) -> Optional[Dict]:
    """
    Get the latest strength-weakness snapshot for a period.
    
    Args:
        period: Period string ('daily', 'weekly', 'monthly')
        
    Returns:
        Dictionary with snapshot data, or None if not found
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute(
                """
                SELECT id, snapshot_timestamp, period, ignore_candles,
                       response_data, created_at
                FROM strength_weakness_snapshots
                WHERE period = %s
                ORDER BY snapshot_timestamp DESC
                LIMIT 1
                """,
                (period,)
            )
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
            
    except Exception as e:
        logger.error(f"Failed to get latest strength-weakness: {e}", exc_info=True)
        return None
