"""
Pydantic models for API request/response schemas.
"""
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class InstrumentAnalysis(BaseModel):
    """Analysis result for a single instrument."""
    instrument: str = Field(..., description="Currency pair (e.g., GBP_USD)")
    mc1: Optional[Dict] = Field(None, description="Previous period merged candle data")
    mc2: Optional[Dict] = Field(None, description="Current period merged candle data")
    relation: str = Field(..., description="Pattern relation between MC1 and MC2")
    color: str = Field(..., description="Candle color: GREEN, RED, or NEUTRAL")
    error: Optional[str] = Field(None, description="Error message if analysis failed")


class AnalysisResponse(BaseModel):
    """Response model for analysis endpoint."""
    timeframe: str = Field(..., description="Normalized timeframe (e.g., 1D, 2D)")
    timestamp: str = Field(..., description="ISO timestamp of when analysis was performed")
    ignore_candles: int = Field(..., description="Number of candles ignored")
    patterns: Dict[str, List[str]] = Field(..., description="Pattern-based groupings of instruments")
    instruments: List[InstrumentAnalysis] = Field(..., description="Detailed analysis for each instrument")


class DateListResponse(BaseModel):
    """Response model for available dates endpoint."""
    timeframe: str = Field(..., description="Normalized timeframe")
    current: List[str] = Field(..., description="List of current analysis dates (usually one)")
    backups: List[str] = Field(..., description="List of backup dates available")
    all_dates: List[str] = Field(..., description="Combined list of all available dates (current + backups)")


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""
    status: str = Field(..., description="Service status")
    timestamp: str = Field(..., description="Current server timestamp")


class RunAnalysisRequest(BaseModel):
    """Request model for running analysis."""
    timeframe: str = Field(..., description="Timeframe: 1D, 2D, 3D, or 4D (case insensitive)")
    ignore_candles: int = Field(default=1, ge=0, description="Number of candles to ignore at the end (default: 1)")
    save: bool = Field(default=True, description="Whether to save the analysis results to disk (default: True)")


class PreviousWeekCandle(BaseModel):
    """Previous period candle data used for pullback calculations."""

    time: str = Field(..., description="Previous period date")
    open: float = Field(..., description="Previous period open price")
    high: float = Field(..., description="Previous period high price")
    low: float = Field(..., description="Previous period low price")
    close: float = Field(..., description="Previous period close price")


class CurrentWeekCandle(BaseModel):
    """Current period candle data used for pullback calculations."""

    time: Optional[str] = Field(None, description="Current period date")
    high: float = Field(..., description="Current period high price")
    low: float = Field(..., description="Current period low price")


class PullbackResult(BaseModel):
    """Pullback analysis result for a single instrument."""
    instrument: str = Field(..., description="Currency pair (e.g., GBP_USD)")
    current_price: float = Field(..., description="Current price")
    prev_week: PreviousWeekCandle = Field(..., description="Previous period candle data")
    pullback_percentage: float = Field(..., description="Pullback percentage (0% = at low, 100% = at high)")
    tested_high: bool = Field(..., description="Whether price has tested previous week high")
    tested_low: bool = Field(..., description="Whether price has tested previous week low")
    current_week: Optional[CurrentWeekCandle] = Field(None, description="Current week candle data (if available)")
    max_pullback_percentage: Optional[float] = Field(None, description="Maximum pullback percentage reached this week (using current week low)")
    max_extension_percentage: Optional[float] = Field(None, description="Maximum extension percentage reached this week (using current week high)")


class StrengthWeaknessDetails(BaseModel):
    """
    Detailed breakdown for strength/weakness calculations for a given currency.

    Note:
        For strength:
            - tested_high_* correspond to base-currency tested high instruments
            - tested_low_* correspond to quote-currency tested low instruments
        For weakness:
            - tested_high_* correspond to quote-currency tested high instruments
            - tested_low_* correspond to base-currency tested low instruments
    """

    total_count: int = Field(..., description="Total number of instruments considered for this currency")
    total_instruments: List[str] = Field(..., description="List of all instruments considered")
    tested_high_count: int = Field(..., description="Number of instruments contributing via tested high condition")
    tested_high_instruments: List[str] = Field(..., description="Instrument names contributing via tested high condition")
    tested_low_count: int = Field(..., description="Number of instruments contributing via tested low condition")
    tested_low_instruments: List[str] = Field(..., description="Instrument names contributing via tested low condition")


class PullbackResponse(BaseModel):
    """Response model for pullback analysis endpoint."""
    timestamp: str = Field(..., description="ISO timestamp of when analysis was performed")
    currency_filter: Optional[str] = Field(None, description="Currency filter applied (if any)")
    ignore_candles: int = Field(..., description="Number of candles ignored for the selected period")
    period: str = Field(..., description="Aggregation period used: 'weekly' or 'monthly'")
    results: List[PullbackResult] = Field(..., description="Pullback analysis results for each instrument")
    strength: Optional[float] = Field(
        None,
        description=(
            "Strength metric for the requested currency in range [0.0, 1.0]. "
            "Only populated when a specific currency_filter is provided. "
            "Formula: (base tested_high + quote tested_low) / total_related_pairs"
        ),
    )
    weakness: Optional[float] = Field(
        None,
        description=(
            "Weakness metric for the requested currency in range [0.0, 1.0]. "
            "Only populated when a specific currency_filter is provided. "
            "Formula: (base tested_low + quote tested_high) / total_related_pairs"
        ),
    )
    strength_details: Optional[StrengthWeaknessDetails] = Field(
        None,
        description=(
            "Detailed breakdown of strength calculation for the requested currency. "
            "Only populated when a specific currency_filter is provided."
        ),
    )
    weakness_details: Optional[StrengthWeaknessDetails] = Field(
        None,
        description=(
            "Detailed breakdown of weakness calculation for the requested currency. "
            "Only populated when a specific currency_filter is provided."
        ),
    )
    all_currencies_strength_weakness: Optional[Dict[str, Dict[str, object]]] = Field(
        None,
        description=(
            "When no specific currency_filter is provided, this contains strength/weakness "
            "statistics for all currencies, keyed by currency code. Each entry has the same "
            "structure as the individual currency stats (strength, weakness, strength_details, "
            "weakness_details)."
        ),
    )


class RunPullbackRequest(BaseModel):
    """Request model for running pullback analysis."""
    currency: Optional[str] = Field(None, description="Optional currency code to filter by (e.g., JPY, USD, EUR)")
    ignore_candles: int = Field(
        default=0,
        ge=0,
        description="Number of candles to ignore at the end for the selected period (default: 0)",
    )
    period: str = Field(
        default="weekly",
        description="Aggregation period for pullback analysis: 'weekly' or 'monthly' (default: 'weekly')",
    )


class CurrencyCategorization(BaseModel):
    """Categorized strength/weakness data for a single currency."""
    tested_high: List[str] = Field(..., description="Instruments where currency tested high (normalized to show currency as base)")
    tested_high_count: int = Field(..., description="Number of instruments where currency tested high")
    tested_low: List[str] = Field(..., description="Instruments where currency tested low (normalized to show currency as base)")
    tested_low_count: int = Field(..., description="Number of instruments where currency tested low")
    strength: float = Field(..., description="Strength percentage (0.0-1.0)")
    weakness: float = Field(..., description="Weakness percentage (0.0-1.0)")


class CurrencySummaryEntry(BaseModel):
    """Single entry in strength/weakness summary."""
    currency: str = Field(..., description="Currency code")
    value: float = Field(..., description="Strength or weakness percentage")


class StrengthWeaknessSummary(BaseModel):
    """Summary of currencies sorted by strength and weakness."""
    by_strength: List[CurrencySummaryEntry] = Field(..., description="Currencies sorted by strength (descending)")
    by_weakness: List[CurrencySummaryEntry] = Field(..., description="Currencies sorted by weakness (descending)")


class StrengthWeaknessCategorizationResponse(BaseModel):
    """Response model for strength/weakness categorization endpoint."""
    timestamp: str = Field(..., description="ISO timestamp of when analysis was performed")
    currency_filter: Optional[str] = Field(None, description="Currency filter applied (if any)")
    ignore_candles: int = Field(..., description="Number of candles ignored for the selected period")
    period: str = Field(..., description="Aggregation period used: 'weekly' or 'monthly'")
    currencies: Dict[str, CurrencyCategorization] = Field(..., description="Categorized data for each currency")
    summary: StrengthWeaknessSummary = Field(..., description="Summary with currencies sorted by strength and weakness")


class HistoricalSnapshot(BaseModel):
    """Single historical snapshot."""
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    timestamp: str = Field(..., description="ISO timestamp when snapshot was captured")
    data: Dict = Field(..., description="Original response data")


class HistoryRangeResponse(BaseModel):
    """Response model for date range history endpoint."""
    endpoint: str = Field(..., description="Endpoint identifier")
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")
    snapshots: List[HistoricalSnapshot] = Field(..., description="List of snapshots within date range")


class HistorySingleResponse(BaseModel):
    """Response model for single date history endpoint."""
    endpoint: str = Field(..., description="Endpoint identifier")
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    timestamp: str = Field(..., description="ISO timestamp when snapshot was captured")
    data: Dict = Field(..., description="Original response data")


class HistoryDatesResponse(BaseModel):
    """Response model for available dates endpoint."""
    endpoint: str = Field(..., description="Endpoint identifier")
    dates: List[str] = Field(..., description="List of available dates in YYYY-MM-DD format")
    latest: Optional[str] = Field(None, description="Latest available date")


class CaptureHistoryRequest(BaseModel):
    """Request model for manual history capture."""
    endpoints: Optional[List[str]] = Field(None, description="List of endpoint identifiers to capture. If empty, captures all.")
    date: Optional[str] = Field(None, description="Date in YYYY-MM-DD format. If None, uses today.")


class CaptureResult(BaseModel):
    """Result of a single endpoint capture."""
    endpoint: str = Field(..., description="Endpoint identifier")
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    status: str = Field(..., description="Capture status: 'success' or 'error'")
    error: Optional[str] = Field(None, description="Error message if status is 'error'")


class CaptureHistoryResponse(BaseModel):
    """Response model for capture history endpoint."""
    success: bool = Field(..., description="Overall success status")
    captured: List[CaptureResult] = Field(..., description="List of capture results")
    errors: List[str] = Field(default_factory=list, description="List of error messages")
