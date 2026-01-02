"""
FastAPI routes for candle analysis API.
"""
import json
import logging
from fastapi import APIRouter, HTTPException, Path as PathParam, Query, Request
from typing import Optional, List, Literal

from .models import (
    AnalysisResponse,
    DateListResponse,
    HealthResponse,
    RunAnalysisRequest,
    PullbackResponse,
    RunPullbackRequest,
    StrengthWeaknessCategorizationResponse,
    CurrencyCategorization,
    CurrencySummaryEntry,
    StrengthWeaknessSummary,
    HistoryRangeResponse,
    HistorySingleResponse,
    HistoryDatesResponse,
    HistoricalSnapshot,
    CaptureHistoryRequest,
    CaptureHistoryResponse,
    CaptureResult,
    FeedbackRequest,
    GeneralFeedbackRequest,
    FeedbackResponse,
    StatisticsResponse,
    BacktestRequest,
    BacktestResponse,
)
from ..core.file_manager import load_analysis, list_available_dates, save_analysis, backup_current_analysis
from ..core.candle_analyzer import analyze_all_currencies, enhance_analysis_with_feedback, fetch_candles_raw, merge_candles, analyze_candle_relation
from ..core.pullback import analyze_all_pullbacks, categorize_currencies_strength_weakness
from ..core.engulfing_feedback import (
    store_feedback,
    store_general_feedback,
    aggregate_feedback_across_timeframes,
    get_feedback,
    get_merged_feedback,
)
from ..core.engulfing_metrics import calculate_engulfing_metrics
from ..core.adaptive_learning import learn_from_feedback, calculate_adaptive_similarity
from ..core.engulfing_backtest import backtest_pattern
from ..core.history_storage import (
    store_snapshot,
    get_snapshot,
    get_snapshots_range,
    get_last_n_days,
    list_dates,
    get_latest_snapshot,
)
from ..utils.timeframe import normalize_timeframe, is_valid_timeframe
from datetime import datetime, timedelta

logger = logging.getLogger("candle_analysis_api")

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        Health status and current timestamp
    """
    logger.debug("Health check endpoint accessed")
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat()
    )


@router.get("/analysis/{timeframe}", response_model=AnalysisResponse, tags=["analysis"])
async def get_current_analysis(
    timeframe: str = PathParam(..., description="Timeframe: 1D, 2D, 3D, or 4D (case insensitive)")
):
    """
    Get current analysis for a timeframe.
    
    Returns the most recent analysis from the latest directory, which contains
    all currencies merged together.
    
    Args:
        timeframe: Timeframe string (e.g., "1D", "2D", "3D", "4D")
        
    Returns:
        AnalysisResponse with all currency analysis merged
        
    Raises:
        HTTPException: If timeframe is invalid or analysis not found
    """
    logger.debug(f"Getting current analysis for timeframe: {timeframe}")
    try:
        normalized_tf = normalize_timeframe(timeframe)
        logger.debug(f"Normalized timeframe: {normalized_tf}")
    except ValueError as e:
        logger.warning(f"Invalid timeframe: {timeframe} - {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    # Load from latest
    logger.debug(f"Loading analysis for timeframe: {normalized_tf}")
    analysis_data = load_analysis(normalized_tf, date=None)
    
    if analysis_data is None:
        logger.warning(f"No analysis found for timeframe {normalized_tf}")
        raise HTTPException(
            status_code=404,
            detail=f"No analysis found for timeframe {normalized_tf}. Run the scheduler first."
        )
    
    logger.debug(f"Analysis loaded successfully. Instruments: {len(analysis_data.get('instruments', []))}")
    return AnalysisResponse(**analysis_data)


@router.get("/analysis/{timeframe}/history", response_model=DateListResponse, tags=["analysis"])
async def get_analysis_history(
    timeframe: str = PathParam(..., description="Timeframe: 1D, 2D, 3D, or 4D (case insensitive)")
):
    """
    Get list of available dates (current + backups) for a timeframe.
    
    Args:
        timeframe: Timeframe string (e.g., "1D", "2D", "3D", "4D")
        
    Returns:
        DateListResponse with current and backup dates
        
    Raises:
        HTTPException: If timeframe is invalid
    """
    try:
        normalized_tf = normalize_timeframe(timeframe)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    dates = list_available_dates(normalized_tf)
    
    # Combine all dates
    all_dates = dates["current"] + dates["backups"]
    
    return DateListResponse(
        timeframe=normalized_tf,
        current=dates["current"],
        backups=dates["backups"],
        all_dates=all_dates
    )


@router.get("/analysis/{timeframe}/{date}", response_model=AnalysisResponse, tags=["analysis"])
async def get_historical_analysis(
    timeframe: str = PathParam(..., description="Timeframe: 1D, 2D, 3D, or 4D (case insensitive)"),
    date: str = PathParam(..., description="Date in YYYY-MM-DD format")
):
    """
    Get historical analysis for a specific timeframe and date.
    
    Args:
        timeframe: Timeframe string (e.g., "1D", "2D", "3D", "4D")
        date: Date string in YYYY-MM-DD format
        
    Returns:
        AnalysisResponse with historical analysis data
        
    Raises:
        HTTPException: If timeframe is invalid, date format is invalid, or analysis not found
    """
    try:
        normalized_tf = normalize_timeframe(timeframe)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {date}. Expected YYYY-MM-DD")
    
    # Load from backup
    analysis_data = load_analysis(normalized_tf, date=date)
    
    if analysis_data is None:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis found for timeframe {normalized_tf} on date {date}"
        )
    
    return AnalysisResponse(**analysis_data)


@router.post("/analysis/run", response_model=AnalysisResponse, tags=["analysis"])
async def run_analysis(
    request: RunAnalysisRequest,
    force_oanda: bool = Query(default=False, description="Force loading from OANDA API instead of saved data")
):
    """
    Run analysis for a given timeframe with a given ignore value.
    
    This endpoint triggers a new analysis run, fetching fresh data from OANDA API
    and analyzing all instruments. Optionally saves the results to disk.
    
    Args:
        request: RunAnalysisRequest with timeframe and ignore_candles
        
    Returns:
        AnalysisResponse with the analysis results
        
    Raises:
        HTTPException: If timeframe is invalid or analysis fails
    """
    try:
        normalized_tf = normalize_timeframe(request.timeframe)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Validate ignore_candles
    if request.ignore_candles < 0:
        raise HTTPException(
            status_code=400,
            detail=f"ignore_candles must be >= 0, got {request.ignore_candles}"
        )
    
    logger.info(f"Running analysis: timeframe={normalized_tf}, ignore_candles={request.ignore_candles}, force_oanda={force_oanda}, save={request.save}")
    try:
        # Run the analysis
        analysis_data = analyze_all_currencies(
            timeframe=normalized_tf,
            ignore_candles=request.ignore_candles,
            force_oanda=force_oanda
        )
        
        # Save to disk if requested
        if request.save:
            # Backup existing analysis if it exists
            try:
                backup_current_analysis(normalized_tf)
            except Exception:
                # If backup fails, continue anyway
                pass
            
            # Save new analysis
            save_analysis(analysis_data, normalized_tf)
        
        return AnalysisResponse(**analysis_data)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )


@router.get("/analysis/{timeframe}/enhanced", response_model=AnalysisResponse, tags=["analysis"])
async def get_enhanced_analysis(
    timeframe: str = PathParam(..., description="Timeframe: 1D, 2D, 3D, or 4D (case insensitive)"),
    use_merged: bool = Query(default=True, description="Use merged feedback (default: True)"),
    use_adaptive: bool = Query(default=True, description="Use adaptive learning (default: True)")
):
    """
    Get enhanced analysis with feedback-based scoring and statistics.
    
    This endpoint returns the current analysis enhanced with:
    - Similarity scores for engulfing patterns (compared to historical feedback)
    - Adaptive scoring using learned patterns
    - Confidence indicators
    
    Args:
        timeframe: Timeframe string (e.g., "1D", "2D", "3D", "4D")
        use_merged: Use merged feedback across timeframes (default: True)
        use_adaptive: Use adaptive learning for scoring (default: True)
        
    Returns:
        Enhanced AnalysisResponse with feedback information
        
    Raises:
        HTTPException: If timeframe is invalid or analysis not found
    """
    try:
        normalized_tf = normalize_timeframe(timeframe)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Load current analysis
    analysis_data = load_analysis(normalized_tf)
    if not analysis_data:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis found for timeframe {normalized_tf}. Run analysis first."
        )
    
    # Enhance with feedback
    try:
        enhanced_data = enhance_analysis_with_feedback(
            analysis_data=analysis_data,
            timeframe=normalized_tf,
            use_merged=use_merged,
            use_adaptive=use_adaptive
        )
    except Exception as e:
        logger.warning(f"Failed to enhance analysis with feedback: {e}")
        enhanced_data = analysis_data
    
    return AnalysisResponse(**enhanced_data)


@router.post("/analysis/{timeframe}/run", response_model=AnalysisResponse, tags=["analysis"])
async def run_analysis_by_timeframe(
    timeframe: str = PathParam(..., description="Timeframe: 1D, 2D, 3D, or 4D (case insensitive)"),
    ignore_candles: int = Query(default=1, ge=0, description="Number of candles to ignore at the end"),
    save: bool = Query(default=True, description="Whether to save the analysis results to disk"),
    force_oanda: bool = Query(default=False, description="Force loading from OANDA API instead of saved data")
):
    """
    Run analysis for a specific timeframe with a given ignore value.
    
    This endpoint triggers a new analysis run, fetching fresh data from OANDA API
    and analyzing all instruments. Optionally saves the results to disk.
    
    Args:
        timeframe: Timeframe string (e.g., "1D", "2D", "3D", "4D")
        ignore_candles: Number of candles to ignore at the end (default: 1, query parameter)
        save: Whether to save the analysis results to disk (default: True, query parameter)
        
    Returns:
        AnalysisResponse with the analysis results
        
    Raises:
        HTTPException: If timeframe is invalid or analysis fails
    """
    try:
        normalized_tf = normalize_timeframe(timeframe)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Validate ignore_candles
    if ignore_candles < 0:
        raise HTTPException(
            status_code=400,
            detail=f"ignore_candles must be >= 0, got {ignore_candles}"
        )
    
    logger.info(f"Running analysis by timeframe: timeframe={normalized_tf}, ignore_candles={ignore_candles}, force_oanda={force_oanda}, save={save}")
    try:
        # Run the analysis
        analysis_data = analyze_all_currencies(
            timeframe=normalized_tf,
            ignore_candles=ignore_candles,
            force_oanda=force_oanda
        )
        
        # Save to disk if requested
        if save:
            # Backup existing analysis if it exists
            try:
                backup_current_analysis(normalized_tf)
            except Exception:
                # If backup fails, continue anyway
                pass
            
            # Save new analysis
            save_analysis(analysis_data, normalized_tf)
        
        return AnalysisResponse(**analysis_data)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )


@router.get("/pullback", response_model=PullbackResponse, tags=["pullback"])
async def get_pullback_analysis(
    currency: Optional[str] = Query(None, description="Filter by currency code (e.g., JPY, USD, EUR)"),
    ignore_candles: int = Query(
        default=0,
        ge=0,
        description="Number of candles to ignore at the end for the selected period (default: 0)",
    ),
    period: str = Query(
        default="weekly",
        description="Aggregation period for pullback analysis: 'weekly' or 'monthly' (default: 'weekly')",
    ),
    force_oanda: bool = Query(default=False, description="Force loading from OANDA API instead of saved data"),
    date: Optional[str] = Query(None, description="Load historical data for a specific date (YYYY-MM-DD format). If provided, returns historical snapshot instead of computing fresh data."),
):
    """
    Get pullback analysis for all currency pairs.
    
    Calculates how much each currency pair has pulled back from the previous period's high,
    relative to the previous period's candle range (low to high). The period can be weekly
    or monthly, controlled via the `period` query parameter.
    
    By default, this endpoint loads weekly and monthly candle data from saved cache files
    located at `/root/first_test_app/data/oanda_saved_data/`. To force loading fresh data
    from OANDA API, use the `force_oanda=true` query parameter.
    
    If a `date` parameter is provided, the endpoint will load historical data from that date
    instead of computing fresh analysis. Historical data must have been previously captured
    by the history capture scheduler.
    
    - 0% = at previous week's low
    - 100% = at previous week's high
    - < 0% = below previous week's low
    - > 100% = above previous week's high
    
    Args:
        currency: Optional currency code to filter by (e.g., "JPY" to show all JPY pairs)
        ignore_candles: Number of candles to ignore at the end for the selected period (default: 0)
        period: Aggregation period for pullback analysis: "weekly" or "monthly"
        force_oanda: If True, force loading from OANDA API instead of saved data (default: False)
        date: Optional date string in YYYY-MM-DD format to load historical data
        
    Returns:
        PullbackResponse with pullback analysis for each instrument
        
    Example:
        GET /api/v1/pullback                                    # All currencies (weekly, from cache)
        GET /api/v1/pullback?currency=JPY                       # Only JPY pairs (weekly, from cache)
        GET /api/v1/pullback?currency=USD&period=monthly        # Only USD pairs, monthly pullback (from cache)
        GET /api/v1/pullback?period=weekly&force_oanda=true     # Weekly pullback, force OANDA API
        GET /api/v1/pullback?period=weekly&date=2024-01-15      # Load historical data from 2024-01-15
    """
    try:
        normalized_period = period.lower() if period else "weekly"
        if normalized_period not in {"weekly", "monthly"}:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid period: {period}. Expected 'weekly' or 'monthly'.",
            )

        # If date is provided, load from history
        if date:
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid date format: {date}. Expected YYYY-MM-DD format."
                )
            
            endpoint_id = f"pullback_{normalized_period}"
            snapshot = get_snapshot(endpoint_id, date)
            
            if snapshot is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"No historical data found for pullback analysis (period={normalized_period}) on date {date}."
                )
            
            # Extract the data from snapshot
            historical_data = snapshot.get("data", {})
            
            # Apply currency filter if provided
            if currency:
                currency_upper = currency.upper()
                results = historical_data.get("results", [])
                filtered_results = [
                    r for r in results
                    if currency_upper in r.get("instrument", "")
                ]
                historical_data = {**historical_data, "results": filtered_results}
                historical_data["currency_filter"] = currency_upper
            
            logger.info(f"Loaded historical pullback analysis: date={date}, period={normalized_period}, currency={currency}")
            return PullbackResponse(**historical_data)

        logger.info(f"Getting pullback analysis: currency={currency}, ignore_candles={ignore_candles}, period={normalized_period}, force_oanda={force_oanda}")
        analysis_data = analyze_all_pullbacks(
            currency_filter=currency,
            ignore_candles=ignore_candles,
            period=normalized_period,
            force_oanda=force_oanda,
        )
        
        return PullbackResponse(**analysis_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Pullback analysis failed: {str(e)}"
        )


@router.post("/pullback/run", response_model=PullbackResponse, tags=["pullback"])
async def run_pullback_analysis(
    request: RunPullbackRequest,
    force_oanda: bool = Query(default=False, description="Force loading from OANDA API instead of saved data")
):
    """
    Run pullback analysis for all currency pairs and return results in JSON.
    
    This endpoint triggers a fresh pullback analysis run, fetching current data from OANDA API
    and analyzing all instruments (or filtered by currency). Returns complete JSON results.
    
    Calculates how much each currency pair has pulled back from the previous period's high,
    relative to the previous period's candle range (low to high). The period can be weekly
    or monthly, controlled via the request body.
    
    - 0% = at previous week's low
    - 100% = at previous week's high
    - < 0% = below previous week's low
    - > 100% = above previous week's high
    
    Args:
        request: RunPullbackRequest with optional currency filter, ignore_candles, and period
        
    Returns:
        PullbackResponse with pullback analysis results in JSON format
        
    Example:
        POST /api/v1/pullback/run
        {
            "currency": "JPY",
            "ignore_candles": 0
        }
    """
    try:
        # Validate ignore_candles
        if request.ignore_candles < 0:
            raise HTTPException(
                status_code=400,
                detail=f"ignore_candles must be >= 0, got {request.ignore_candles}"
            )

        normalized_period = request.period.lower() if request.period else "weekly"
        if normalized_period not in {"weekly", "monthly"}:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid period: {request.period}. Expected 'weekly' or 'monthly'.",
            )
        
        logger.info(f"Running pullback analysis: currency={request.currency}, ignore_candles={request.ignore_candles}, period={normalized_period}, force_oanda={force_oanda}")
        # Run the pullback analysis
        analysis_data = analyze_all_pullbacks(
            currency_filter=request.currency,
            ignore_candles=request.ignore_candles,
            period=normalized_period,
            force_oanda=force_oanda,
        )
        
        return PullbackResponse(**analysis_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Pullback analysis failed: {str(e)}"
        )


@router.get("/pullback/history", response_model=HistoryDatesResponse, tags=["pullback"])
async def get_pullback_history(
    period: str = Query(
        default="weekly",
        description="Aggregation period for pullback analysis: 'weekly' or 'monthly' (default: 'weekly')",
    ),
):
    """
    Get list of available dates for historical pullback analysis.
    
    Args:
        period: Aggregation period for pullback analysis: "weekly" or "monthly"
        
    Returns:
        HistoryDatesResponse with list of available dates and latest date
        
    Example:
        GET /api/v1/pullback/history?period=weekly
        GET /api/v1/pullback/history?period=monthly
    """
    try:
        normalized_period = period.lower() if period else "weekly"
        if normalized_period not in {"weekly", "monthly"}:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid period: {period}. Expected 'weekly' or 'monthly'.",
            )
        
        endpoint_id = f"pullback_{normalized_period}"
        dates = list_dates(endpoint_id)
        
        latest_date = dates[-1] if dates else None
        
        return HistoryDatesResponse(
            endpoint=endpoint_id,
            dates=dates,
            latest=latest_date
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get pullback history dates: {str(e)}"
        )


@router.get("/pullback/{date}", response_model=PullbackResponse, tags=["pullback"])
async def get_historical_pullback(
    date: str = PathParam(..., description="Date in YYYY-MM-DD format"),
    currency: Optional[str] = Query(None, description="Filter by currency code (e.g., JPY, USD, EUR)"),
    period: str = Query(
        default="weekly",
        description="Aggregation period for pullback analysis: 'weekly' or 'monthly' (default: 'weekly')",
    ),
):
    """
    Get historical pullback analysis for a specific date.
    
    Args:
        date: Date string in YYYY-MM-DD format
        currency: Optional currency code to filter by (e.g., "JPY" to show all JPY pairs)
        period: Aggregation period for pullback analysis: "weekly" or "monthly"
        
    Returns:
        PullbackResponse with historical pullback analysis data
        
    Raises:
        HTTPException: If date format is invalid, period is invalid, or historical data not found
        
    Example:
        GET /api/v1/pullback/2024-01-15?period=weekly
        GET /api/v1/pullback/2024-01-15?period=monthly&currency=JPY
    """
    try:
        normalized_period = period.lower() if period else "weekly"
        if normalized_period not in {"weekly", "monthly"}:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid period: {period}. Expected 'weekly' or 'monthly'.",
            )
        
        # Validate date format
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date format: {date}. Expected YYYY-MM-DD format."
            )
        
        endpoint_id = f"pullback_{normalized_period}"
        snapshot = get_snapshot(endpoint_id, date)
        
        if snapshot is None:
            raise HTTPException(
                status_code=404,
                detail=f"No historical data found for pullback analysis (period={normalized_period}) on date {date}."
            )
        
        # Extract the data from snapshot
        historical_data = snapshot.get("data", {})
        
        # Apply currency filter if provided
        if currency:
            currency_upper = currency.upper()
            results = historical_data.get("results", [])
            filtered_results = [
                r for r in results
                if currency_upper in r.get("instrument", "")
            ]
            historical_data = {**historical_data, "results": filtered_results}
            historical_data["currency_filter"] = currency_upper
        
        logger.info(f"Loaded historical pullback analysis: date={date}, period={normalized_period}, currency={currency}")
        return PullbackResponse(**historical_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get historical pullback analysis: {str(e)}"
        )


@router.get("/strength-weakness", response_model=StrengthWeaknessCategorizationResponse, tags=["strength-weakness"])
async def get_strength_weakness_categorization(
    currency: Optional[str] = Query(None, description="Filter by currency code (e.g., JPY, USD, EUR)"),
    ignore_candles: int = Query(
        default=0,
        ge=0,
        description="Number of candles to ignore at the end for the selected period (default: 0)",
    ),
    period: str = Query(
        default="weekly",
        description="Aggregation period for pullback analysis: 'weekly' or 'monthly' (default: 'weekly')",
    ),
    force_oanda: bool = Query(default=False, description="Force loading from OANDA API instead of saved data"),
):
    """
    Get strength/weakness categorization for all currencies based on pullback analysis.
    
    This endpoint processes pullback analysis data to categorize currencies by their
    strength/weakness patterns. It shows which instruments tested high/low for each currency,
    normalized to show the currency's perspective (as base currency).
    
    The categorization logic:
    - When currency is base and instrument tested high → currency tested high
    - When currency is quote and instrument tested high → reverse pair and currency tested low
    - When currency is base and instrument tested low → currency tested low
    - When currency is quote and instrument tested low → reverse pair and currency tested high
    
    Args:
        currency: Optional currency code to filter by (e.g., "JPY" to show only JPY)
        ignore_candles: Number of candles to ignore at the end for the selected period (default: 0)
        period: Aggregation period for pullback analysis: "weekly" or "monthly"
        force_oanda: If True, force loading from OANDA API instead of saved data (default: False)
        
    Returns:
        StrengthWeaknessCategorizationResponse with categorized data for each currency
        
    Example:
        GET /api/v1/strength-weakness                                    # All currencies (weekly, from cache)
        GET /api/v1/strength-weakness?currency=JPY                       # Only JPY (weekly, from cache)
        GET /api/v1/strength-weakness?currency=USD&period=monthly         # Only USD, monthly (from cache)
        GET /api/v1/strength-weakness?period=weekly&force_oanda=true     # Weekly, force OANDA API
    """
    try:
        normalized_period = period.lower() if period else "weekly"
        if normalized_period not in {"weekly", "monthly"}:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid period: {period}. Expected 'weekly' or 'monthly'.",
            )

        logger.info(f"Getting strength/weakness categorization: currency={currency}, ignore_candles={ignore_candles}, period={normalized_period}, force_oanda={force_oanda}")
        # Get pullback analysis data
        analysis_data = analyze_all_pullbacks(
            currency_filter=None,  # Always get all currencies for categorization
            ignore_candles=ignore_candles,
            period=normalized_period,
            force_oanda=force_oanda,
        )
        
        # Extract all_currencies_strength_weakness data
        all_currencies_data = analysis_data.get("all_currencies_strength_weakness")
        if not all_currencies_data:
            raise HTTPException(
                status_code=500,
                detail="No strength/weakness data available. Ensure pullback analysis includes all currencies.",
            )
        
        # Categorize currencies
        categorized_data = categorize_currencies_strength_weakness(all_currencies_data)
        
        # Filter by currency if provided
        currency_filter_upper = currency.upper() if currency else None
        if currency_filter_upper:
            if currency_filter_upper not in categorized_data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Currency '{currency}' not found in categorization data.",
                )
            categorized_data = {currency_filter_upper: categorized_data[currency_filter_upper]}
        
        # Generate summary
        by_strength = sorted(
            categorized_data.items(),
            key=lambda x: x[1]["strength"],
            reverse=True,
        )
        by_weakness = sorted(
            categorized_data.items(),
            key=lambda x: x[1]["weakness"],
            reverse=True,
        )
        
        summary = StrengthWeaknessSummary(
            by_strength=[
                CurrencySummaryEntry(currency=curr, value=data["strength"])
                for curr, data in by_strength
            ],
            by_weakness=[
                CurrencySummaryEntry(currency=curr, value=data["weakness"])
                for curr, data in by_weakness
            ],
        )
        
        # Convert categorized data to Pydantic models
        currencies_dict = {
            curr: CurrencyCategorization(**data)
            for curr, data in categorized_data.items()
        }
        
        return StrengthWeaknessCategorizationResponse(
            timestamp=analysis_data["timestamp"],
            currency_filter=currency_filter_upper,
            ignore_candles=ignore_candles,
            period=normalized_period,
            currencies=currencies_dict,
            summary=summary,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Strength/weakness categorization failed: {str(e)}"
        )


@router.post("/strength-weakness/run", response_model=StrengthWeaknessCategorizationResponse, tags=["strength-weakness"])
async def run_strength_weakness_categorization(
    request: RunPullbackRequest,
    force_oanda: bool = Query(default=False, description="Force loading from OANDA API instead of saved data")
):
    """
    Run strength/weakness categorization analysis for all currencies and return results.
    
    This endpoint triggers a fresh pullback analysis run, then categorizes the results
    to show strength/weakness patterns for each currency. Returns complete categorized data.
    
    Args:
        request: RunPullbackRequest with optional currency filter, ignore_candles, and period
        
    Returns:
        StrengthWeaknessCategorizationResponse with categorized data for each currency
        
    Example:
        POST /api/v1/strength-weakness/run
        {
            "currency": "JPY",
            "ignore_candles": 0,
            "period": "weekly"
        }
    """
    try:
        # Validate ignore_candles
        if request.ignore_candles < 0:
            raise HTTPException(
                status_code=400,
                detail=f"ignore_candles must be >= 0, got {request.ignore_candles}"
            )

        normalized_period = request.period.lower() if request.period else "weekly"
        if normalized_period not in {"weekly", "monthly"}:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid period: {request.period}. Expected 'weekly' or 'monthly'.",
            )

        logger.info(f"Running strength/weakness categorization: currency={request.currency}, ignore_candles={request.ignore_candles}, period={normalized_period}, force_oanda={force_oanda}")
        # Get pullback analysis data
        analysis_data = analyze_all_pullbacks(
            currency_filter=None,  # Always get all currencies for categorization
            ignore_candles=request.ignore_candles,
            period=normalized_period,
            force_oanda=force_oanda,
        )
        
        # Extract all_currencies_strength_weakness data
        all_currencies_data = analysis_data.get("all_currencies_strength_weakness")
        if not all_currencies_data:
            raise HTTPException(
                status_code=500,
                detail="No strength/weakness data available. Ensure pullback analysis includes all currencies.",
            )
        
        # Categorize currencies
        categorized_data = categorize_currencies_strength_weakness(all_currencies_data)
        
        # Filter by currency if provided
        currency_filter_upper = request.currency.upper() if request.currency else None
        if currency_filter_upper:
            if currency_filter_upper not in categorized_data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Currency '{request.currency}' not found in categorization data.",
                )
            categorized_data = {currency_filter_upper: categorized_data[currency_filter_upper]}
        
        # Generate summary
        by_strength = sorted(
            categorized_data.items(),
            key=lambda x: x[1]["strength"],
            reverse=True,
        )
        by_weakness = sorted(
            categorized_data.items(),
            key=lambda x: x[1]["weakness"],
            reverse=True,
        )
        
        summary = StrengthWeaknessSummary(
            by_strength=[
                CurrencySummaryEntry(currency=curr, value=data["strength"])
                for curr, data in by_strength
            ],
            by_weakness=[
                CurrencySummaryEntry(currency=curr, value=data["weakness"])
                for curr, data in by_weakness
            ],
        )
        
        # Convert categorized data to Pydantic models
        currencies_dict = {
            curr: CurrencyCategorization(**data)
            for curr, data in categorized_data.items()
        }
        
        return StrengthWeaknessCategorizationResponse(
            timestamp=analysis_data["timestamp"],
            currency_filter=currency_filter_upper,
            ignore_candles=request.ignore_candles,
            period=normalized_period,
            currencies=currencies_dict,
            summary=summary,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Strength/weakness categorization failed: {str(e)}"
        )


# History endpoints
@router.get("/history/{endpoint}", response_model=HistoryRangeResponse, tags=["history"])
async def get_history_range(
    endpoint: str = PathParam(..., description="Endpoint identifier (e.g., 'strength_weakness_weekly')"),
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    date: Optional[str] = Query(None, description="Single date in YYYY-MM-DD format (alternative to range)"),
):
    """
    Get historical snapshots for an endpoint.
    
    Supports two modes:
    1. Date range: Provide start_date and end_date (or omit both for last 10 days)
    2. Single date: Provide date parameter
    
    Args:
        endpoint: Endpoint identifier (e.g., "strength_weakness_weekly")
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
        date: Single date in YYYY-MM-DD format (optional, alternative to range)
        
    Returns:
        HistoryRangeResponse with snapshots in date range, or HistorySingleResponse for single date
        
    Raises:
        HTTPException: If date format is invalid or data not found
    """
    # Single date mode
    if date:
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {date}. Expected YYYY-MM-DD")
        
        snapshot = get_snapshot(endpoint, date)
        if snapshot is None:
            raise HTTPException(
                status_code=404,
                detail=f"No snapshot found for endpoint '{endpoint}' on date {date}"
            )
        
        return HistorySingleResponse(
            endpoint=snapshot["endpoint"],
            date=snapshot["date"],
            timestamp=snapshot["timestamp"],
            data=snapshot["data"]
        )
    
    # Date range mode
    if start_date and end_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid date format. Expected YYYY-MM-DD: {e}")
        
        if start > end:
            raise HTTPException(
                status_code=400,
                detail=f"start_date ({start_date}) must be <= end_date ({end_date})"
            )
    elif start_date or end_date:
        raise HTTPException(
            status_code=400,
            detail="Both start_date and end_date must be provided, or neither (for last 10 days)"
        )
    else:
        # Default to last 10 days
        end = datetime.now()
        start = end - timedelta(days=9)  # 10 days inclusive
        start_date = start.strftime("%Y-%m-%d")
        end_date = end.strftime("%Y-%m-%d")
    
    snapshots = get_snapshots_range(endpoint, start_date, end_date)
    
    return HistoryRangeResponse(
        endpoint=endpoint,
        start_date=start_date,
        end_date=end_date,
        snapshots=[
            HistoricalSnapshot(
                date=s["date"],
                timestamp=s["timestamp"],
                data=s["data"]
            )
            for s in snapshots
        ]
    )


@router.get("/history/{endpoint}/dates", response_model=HistoryDatesResponse, tags=["history"])
async def get_history_dates(
    endpoint: str = PathParam(..., description="Endpoint identifier (e.g., 'strength_weakness_weekly')")
):
    """
    List all available dates for an endpoint.
    
    Args:
        endpoint: Endpoint identifier
        
    Returns:
        HistoryDatesResponse with list of available dates and latest date
    """
    dates = list_dates(endpoint)
    latest = dates[-1] if dates else None
    
    return HistoryDatesResponse(
        endpoint=endpoint,
        dates=dates,
        latest=latest
    )


@router.get("/history/{endpoint}/latest", response_model=HistorySingleResponse, tags=["history"])
async def get_history_latest(
    endpoint: str = PathParam(..., description="Endpoint identifier (e.g., 'strength_weakness_weekly')")
):
    """
    Get the latest snapshot for an endpoint.
    
    Args:
        endpoint: Endpoint identifier
        
    Returns:
        HistorySingleResponse with latest snapshot
        
    Raises:
        HTTPException: If no snapshots exist
    """
    snapshot = get_latest_snapshot(endpoint)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail=f"No snapshots found for endpoint '{endpoint}'"
        )
    
    return HistorySingleResponse(
        endpoint=snapshot["endpoint"],
        date=snapshot["date"],
        timestamp=snapshot["timestamp"],
        data=snapshot["data"]
    )


@router.post("/capture-history", response_model=CaptureHistoryResponse, tags=["history"])
async def capture_history(
    request_body: Optional[CaptureHistoryRequest] = None,
    request: Request = None
):
    """
    Manually trigger history capture for specified endpoints.
    
    This endpoint can be called by a scheduler (e.g., cron) to capture
    current state of all endpoints or specific endpoints.
    
    Args:
        request_body: Optional CaptureHistoryRequest with endpoints list and date
        request: FastAPI Request object for getting base URL
        
    Returns:
        CaptureHistoryResponse with capture results
    """
    import httpx
    
    if request_body is None:
        request_body = CaptureHistoryRequest()
    
    # Determine date
    capture_date = request_body.date
    if capture_date is None:
        capture_date = datetime.now().strftime("%Y-%m-%d")
    else:
        try:
            datetime.strptime(capture_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {capture_date}. Expected YYYY-MM-DD")
    
    # List of endpoints to capture
    # If not specified, we'll need to fetch from actual endpoints
    # For now, we'll define a default list
    endpoints_to_capture = request_body.endpoints or [
        "strength_weakness_weekly",
        "strength_weakness_monthly",
        "pullback_weekly",
        "pullback_monthly",
        "analysis_1D",
        "analysis_2D",
        "analysis_3D",
        "analysis_4D",
    ]
    
    captured = []
    errors = []
    
    # Map endpoint identifiers back to URLs
    endpoint_url_map = {
        "strength_weakness_weekly": "/api/v1/strength-weakness?period=weekly",
        "strength_weakness_monthly": "/api/v1/strength-weakness?period=monthly",
        "pullback_weekly": "/api/v1/pullback?period=weekly",
        "pullback_monthly": "/api/v1/pullback?period=monthly",
        "analysis_1D": "/api/v1/analysis/1D",
        "analysis_2D": "/api/v1/analysis/2D",
        "analysis_3D": "/api/v1/analysis/3D",
        "analysis_4D": "/api/v1/analysis/4D",
    }
    
    # For endpoints we can't map, skip them
    for endpoint_id in endpoints_to_capture:
        if endpoint_id not in endpoint_url_map:
            errors.append(f"Unknown endpoint: {endpoint_id}")
            continue
        
        url = endpoint_url_map[endpoint_id]
        
        try:
            # Make internal request to the endpoint
            # Note: This is a simplified approach. In production, you might want to
            # call the handler functions directly instead of making HTTP requests
            # Use request's base URL if available, otherwise default to localhost
            if request:
                base_url = str(request.base_url).rstrip("/")
            else:
                base_url = "http://localhost:8000"
            
            # Account for root_path if present
            full_url = f"{base_url}{url}"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(full_url)
                if response.status_code == 200:
                    data = response.json()
                    store_snapshot(endpoint_id, data, capture_date)
                    captured.append(CaptureResult(
                        endpoint=endpoint_id,
                        date=capture_date,
                        status="success"
                    ))
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    captured.append(CaptureResult(
                        endpoint=endpoint_id,
                        date=capture_date,
                        status="error",
                        error=error_msg
                    ))
                    errors.append(f"{endpoint_id}: {error_msg}")
        except Exception as e:
            error_msg = str(e)
            captured.append(CaptureResult(
                endpoint=endpoint_id,
                date=capture_date,
                status="error",
                error=error_msg
            ))
            errors.append(f"{endpoint_id}: {error_msg}")
    
    return CaptureHistoryResponse(
        success=len(errors) == 0,
        captured=captured,
        errors=errors
    )


# Engulfing Feedback Endpoints

@router.post("/engulfing/feedback", response_model=FeedbackResponse, tags=["engulfing"])
async def submit_feedback(request: FeedbackRequest):
    """
    Submit timeframe-specific feedback for an engulfing pattern.
    
    This endpoint calculates metrics from the current analysis data and stores
    the feedback. Optionally triggers aggregation to merged feedback.
    
    Args:
        request: FeedbackRequest with instrument, timeframe, date, pattern_type, rating, notes
        
    Returns:
        FeedbackResponse with stored feedback and calculated metrics
        
    Raises:
        HTTPException: If timeframe is invalid or analysis data not found
    """
    try:
        normalized_tf = normalize_timeframe(request.timeframe)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Validate date format
    try:
        datetime.strptime(request.date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD")
    
    # Load analysis data for the timeframe and date
    analysis_data = load_analysis(normalized_tf)
    if not analysis_data:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis data found for timeframe {normalized_tf}. Run analysis first."
        )
    
    # Find the instrument in the analysis
    instrument_data = None
    for instr in analysis_data.get("instruments", []):
        if instr.get("instrument") == request.instrument:
            instrument_data = instr
            break
    
    if not instrument_data:
        raise HTTPException(
            status_code=404,
            detail=f"Instrument {request.instrument} not found in analysis data"
        )
    
    # Get candle data
    mc1 = instrument_data.get("mc1", {})
    mc2 = instrument_data.get("mc2", {})
    
    if not mc1 or not mc2:
        raise HTTPException(
            status_code=400,
            detail="Candle data not available for this instrument"
        )
    
    # Calculate metrics
    metrics = calculate_engulfing_metrics(mc1, mc2, request.pattern_type)
    
    # Store feedback
    filepath = store_feedback(
        instrument=request.instrument,
        timeframe=normalized_tf,
        date=request.date,
        pattern_type=request.pattern_type,
        rating=request.rating,
        metrics=metrics,
        candles={"mc1": mc1, "mc2": mc2},
        notes=request.notes
    )
    
    # Optionally aggregate to merged feedback
    try:
        aggregate_feedback_across_timeframes(
            instrument=request.instrument,
            pattern_type=request.pattern_type,
            date=request.date,
            weight_by_rating=True
        )
    except Exception as e:
        logger.warning(f"Failed to aggregate feedback: {e}")
    
    # Load the stored feedback to return
    with open(filepath, 'r', encoding='utf-8') as f:
        feedback_data = json.load(f)
    
    return FeedbackResponse(**feedback_data)


@router.post("/engulfing/feedback/general", response_model=FeedbackResponse, tags=["engulfing"])
async def submit_general_feedback(request: GeneralFeedbackRequest):
    """
    Submit general/merged feedback for an engulfing pattern.
    
    This stores feedback that applies across all timeframes (not timeframe-specific).
    
    Args:
        request: GeneralFeedbackRequest with instrument, date, pattern_type, rating, notes
        
    Returns:
        FeedbackResponse with stored general feedback
        
    Raises:
        HTTPException: If date format is invalid
    """
    # Validate date format
    try:
        datetime.strptime(request.date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD")
    
    # For general feedback, we need to get candle data from analysis
    # Try to get from any available timeframe
    mc1 = None
    mc2 = None
    
    for timeframe in ["1D", "2D", "3D", "4D"]:
        try:
            analysis_data = load_analysis(timeframe)
            if analysis_data:
                for instr in analysis_data.get("instruments", []):
                    if instr.get("instrument") == request.instrument:
                        mc1 = instr.get("mc1", {})
                        mc2 = instr.get("mc2", {})
                        break
                if mc1 and mc2:
                    break
        except Exception:
            continue
    
    if not mc1 or not mc2:
        raise HTTPException(
            status_code=404,
            detail=f"Candle data not available for instrument {request.instrument}"
        )
    
    # Calculate metrics
    metrics = calculate_engulfing_metrics(mc1, mc2, request.pattern_type)
    
    # Store general feedback
    filepath = store_general_feedback(
        instrument=request.instrument,
        date=request.date,
        pattern_type=request.pattern_type,
        rating=request.rating,
        metrics=metrics,
        candles={"mc1": mc1, "mc2": mc2},
        notes=request.notes
    )
    
    # Load the stored feedback to return
    with open(filepath, 'r', encoding='utf-8') as f:
        feedback_data = json.load(f)
    
    return FeedbackResponse(**feedback_data)


@router.get("/engulfing/feedback", response_model=List[FeedbackResponse], tags=["engulfing"])
async def get_feedback_list(
    instrument: Optional[str] = Query(None, description="Filter by instrument"),
    timeframe: Optional[str] = Query(None, description="Filter by timeframe (ignored if merged=true)"),
    pattern_type: Optional[Literal["bullish", "bearish"]] = Query(None, description="Filter by pattern type"),
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    merged: bool = Query(False, description="Return merged feedback (ignores timeframe)")
):
    """
    Query stored feedback entries.
    
    Args:
        instrument: Optional instrument filter
        timeframe: Optional timeframe filter (ignored if merged=true)
        pattern_type: Optional pattern type filter
        start_date: Optional start date for date range
        end_date: Optional end date for date range
        merged: If True, return merged feedback
        
    Returns:
        List of FeedbackResponse matching criteria
    """
    date_range = None
    if start_date and end_date:
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
            date_range = (start_date, end_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD")
    
    feedback_list = get_feedback(
        instrument=instrument,
        timeframe=timeframe,
        pattern_type=pattern_type,
        date_range=date_range,
        merged=merged
    )
    
    return [FeedbackResponse(**f) for f in feedback_list]


@router.get("/engulfing/statistics", response_model=StatisticsResponse, tags=["engulfing"])
async def get_feedback_statistics(
    pattern_type: Literal["bullish", "bearish"] = Query(..., description="Pattern type: bullish or bearish"),
    instrument: Optional[str] = Query(None, description="Filter by instrument"),
    use_merged: bool = Query(True, description="Use merged feedback (default: True)")
):
    """
    Get statistics about feedback patterns.
    
    Uses merged feedback by default to provide comprehensive statistics
    across all timeframes.
    
    Args:
        pattern_type: Pattern type (bullish or bearish)
        instrument: Optional instrument filter
        use_merged: Whether to use merged feedback (default: True)
        
    Returns:
        StatisticsResponse with statistics about good patterns
    """
    # Get feedback
    if use_merged:
        feedback_list = get_merged_feedback(instrument=instrument, pattern_type=pattern_type)
    else:
        feedback_list = get_feedback(instrument=instrument, pattern_type=pattern_type, merged=False)
    
    if not feedback_list:
        return StatisticsResponse(
            pattern_type=pattern_type,
            use_merged=use_merged,
            total_feedback_count=0,
            average_rating=0.0,
            position_distribution={},
            metric_statistics={},
            top_characteristics=[],
            learned_patterns=None,
            confidence_scores=None
        )
    
    # Calculate statistics
    total_count = len(feedback_list)
    average_rating = sum(f.get("rating", 0) for f in feedback_list) / total_count
    
    # Position distribution
    position_counts = {}
    for f in feedback_list:
        pos = f.get("metrics", {}).get("body_position", "unknown")
        position_counts[pos] = position_counts.get(pos, 0) + 1
    
    # Metric statistics
    metric_stats = {}
    numeric_metrics = ["body_size_ratio", "body_overlap_percentage", "mc1_body_size", "mc2_body_size"]
    for key in numeric_metrics:
        values = [f.get("metrics", {}).get(key, 0) for f in feedback_list if isinstance(f.get("metrics", {}).get(key), (int, float))]
        if values:
            metric_stats[key] = {
                "mean": sum(values) / len(values),
                "min": min(values),
                "max": max(values)
            }
    
    # Top characteristics (high-rated patterns)
    high_rated = [f for f in feedback_list if f.get("rating", 0) >= 8]
    top_characteristics = []
    if high_rated:
        high_rated_positions = {}
        for f in high_rated:
            pos = f.get("metrics", {}).get("body_position", "unknown")
            high_rated_positions[pos] = high_rated_positions.get(pos, 0) + 1
        if high_rated_positions:
            top_characteristics.append({
                "characteristic": "body_position",
                "value": max(high_rated_positions.items(), key=lambda x: x[1])[0],
                "frequency": max(high_rated_positions.values()) / len(high_rated)
            })
    
    # Learned patterns
    learned_patterns = learn_from_feedback(pattern_type=pattern_type, use_merged=use_merged)
    
    # Confidence scores
    confidence_scores = {}
    if use_merged:
        merged_with_confidence = [f for f in feedback_list if f.get("confidence_score") is not None]
        if merged_with_confidence:
            confidence_scores["average"] = sum(f.get("confidence_score", 0) for f in merged_with_confidence) / len(merged_with_confidence)
            confidence_scores["min"] = min(f.get("confidence_score", 0) for f in merged_with_confidence)
            confidence_scores["max"] = max(f.get("confidence_score", 0) for f in merged_with_confidence)
    
    return StatisticsResponse(
        pattern_type=pattern_type,
        use_merged=use_merged,
        total_feedback_count=total_count,
        average_rating=round(average_rating, 2),
        position_distribution=position_counts,
        metric_statistics=metric_stats,
        top_characteristics=top_characteristics,
        learned_patterns=learned_patterns,
        confidence_scores=confidence_scores if confidence_scores else None
    )


@router.get("/engulfing/backtest", response_model=BacktestResponse, tags=["engulfing"])
async def backtest_engulfing_patterns(
    instrument: str = Query(..., description="Currency pair (e.g., GBP_USD)"),
    pattern_type: Literal["bullish", "bearish"] = Query(..., description="Pattern type: bullish or bearish"),
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format"),
    timeframe: str = Query(..., description="Timeframe: 1D, 2D, 3D, or 4D (case insensitive)")
):
    """
    Backtest engulfing patterns against historical data.
    
    Args:
        instrument: Currency pair
        pattern_type: Pattern type (bullish or bearish)
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        timeframe: Timeframe (1D, 2D, 3D, or 4D)
        
    Returns:
        BacktestResponse with backtest results
        
    Raises:
        HTTPException: If dates or timeframe are invalid
    """
    # Validate dates
    try:
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD")
    
    # Validate timeframe
    try:
        normalized_tf = normalize_timeframe(timeframe)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Run backtest
    try:
        result = backtest_pattern(
            instrument=instrument,
            pattern_type=pattern_type,
            start_date=start_date,
            end_date=end_date,
            timeframe=normalized_tf
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return BacktestResponse(**result)
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(e)}")
