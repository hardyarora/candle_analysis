"""
FastAPI middleware for capturing API responses for historical storage.
"""
import json
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from ..core.history_storage import store_snapshot
from ..utils.endpoint_mapper import extract_endpoint_identifier, should_capture_endpoint

logger = logging.getLogger("candle_analysis_api.middleware")


class HistoryCaptureMiddleware(BaseHTTPMiddleware):
    """
    Middleware to capture API responses for historical storage.
    
    Intercepts GET requests to /api/* endpoints and stores their responses.
    """
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request and capture response if applicable.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler in chain
            
        Returns:
            Response to client
        """
        # Process request normally
        response = await call_next(request)
        
        # Only capture successful GET requests to /api/* endpoints
        if (
            request.method == "GET"
            and request.url.path.startswith("/api/")
            and 200 <= response.status_code < 300
        ):
            try:
                # Extract endpoint identifier
                query_string = request.url.query
                endpoint = extract_endpoint_identifier(request.url.path, query_string)
                
                if endpoint and should_capture_endpoint(endpoint):
                    # Read response body
                    body = b""
                    async for chunk in response.body_iterator:
                        body += chunk
                    
                    # Recreate response with body for client
                    response = Response(
                        content=body,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type=response.media_type
                    )
                    
                    # Try to parse as JSON and store
                    try:
                        data = json.loads(body.decode('utf-8'))
                        
                        # Store snapshot (non-blocking, fire and forget)
                        # Use today's date
                        try:
                            store_snapshot(endpoint, data)
                            logger.debug(f"Captured response for endpoint: {endpoint}")
                        except Exception as e:
                            # Log but don't fail the request
                            logger.warning(f"Failed to store snapshot for {endpoint}: {e}")
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        # Not JSON, skip capture
                        logger.debug(f"Skipping capture for {endpoint}: response is not JSON")
                
            except Exception as e:
                # Log but don't fail the request
                logger.warning(f"Error in history capture middleware: {e}")
        
        return response

