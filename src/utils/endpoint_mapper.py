"""
Endpoint identifier mapping utilities.

Converts URL paths to endpoint identifiers for historical data storage.
"""
import re
from urllib.parse import urlparse, parse_qs
from typing import Optional


def extract_endpoint_identifier(path: str, query_string: Optional[str] = None) -> Optional[str]:
    """
    Convert URL path to endpoint identifier for storage.
    
    Handles:
    - Removing /api/candle_analysis prefix
    - Converting path parameters to identifiers
    - Including query parameters in identifier when relevant
    
    Examples:
        /api/candle_analysis/api/v1/strength-weakness?period=weekly -> "strength_weakness_weekly"
        /api/candle_analysis/api/v1/strength-weakness?period=monthly -> "strength_weakness_monthly"
        /api/candle_analysis/api/v1/analysis/1D -> "analysis_1D"
        /api/candle_analysis/api/v1/pullback?period=weekly -> "pullback_weekly"
        /api/candle_analysis/api/v1/health -> "health"
    
    Args:
        path: URL path (e.g., "/api/candle_analysis/api/v1/strength-weakness")
        query_string: Optional query string (e.g., "period=weekly")
        
    Returns:
        Endpoint identifier string, or None if endpoint should not be captured
    """
    # Remove /api/candle_analysis prefix if present
    if path.startswith("/api/candle_analysis"):
        path = path[len("/api/candle_analysis"):]
    
    # Remove /api prefix if present
    if path.startswith("/api"):
        path = path[len("/api"):]
    
    # Remove /v1 prefix if present (router prefix)
    if path.startswith("/v1"):
        path = path[len("/v1"):]
    
    # Remove leading/trailing slashes
    path = path.strip("/")
    
    # Split path into components
    parts = [p for p in path.split("/") if p]
    
    if not parts:
        return None
    
    # Build base identifier from path parts
    # Replace hyphens with underscores
    identifier_parts = [part.replace("-", "_") for part in parts]
    base_identifier = "_".join(identifier_parts)
    
    # Handle query parameters for specific endpoints
    if query_string:
        query_params = parse_qs(query_string)
        
        # For strength-weakness and pullback endpoints, include period parameter
        if "strength-weakness" in path or "strength_weakness" in base_identifier:
            if "period" in query_params:
                period = query_params["period"][0].lower()
                base_identifier = f"strength_weakness_{period}"
        elif "pullback" in base_identifier:
            if "period" in query_params:
                period = query_params["period"][0].lower()
                base_identifier = f"pullback_{period}"
    
    return base_identifier if base_identifier else None


def should_capture_endpoint(endpoint: str, exclude_patterns: Optional[list] = None) -> bool:
    """
    Determine if an endpoint should be captured for history.
    
    Args:
        endpoint: Endpoint identifier
        exclude_patterns: List of patterns to exclude (e.g., ["health", "docs"])
        
    Returns:
        True if endpoint should be captured, False otherwise
    """
    if exclude_patterns is None:
        exclude_patterns = ["health", "docs", "openapi.json", "redoc"]
    
    # Don't capture excluded patterns
    for pattern in exclude_patterns:
        if pattern in endpoint.lower():
            return False
    
    # Don't capture history endpoints themselves (to avoid recursion)
    if endpoint.startswith("history_"):
        return False
    
    return True

