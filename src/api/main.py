"""
FastAPI main application.
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router
from .logging_config import setup_api_logging

# Set up logging
logger = setup_api_logging(log_level="DEBUG")

# Create FastAPI app
app = FastAPI(
    title="Candle Analysis API",
    description="REST API for retrieving candle analysis data across multiple timeframes",
    version="1.0.0",
    root_path="/api/candle_analysis",
)

logger.info("FastAPI application initialized")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint with API information."""
    logger.debug("Root endpoint accessed")
    return {
        "name": "Candle Analysis API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health"
    }
