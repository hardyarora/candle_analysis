"""
Unit tests for API routes.

Note: These tests require mocking file operations and may need FastAPI TestClient.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from src.api.main import app
from src.api.models import AnalysisResponse, DateListResponse, PullbackResponse


client = TestClient(app)


class TestHealthEndpoint:
    """Tests for health check endpoint."""
    
    def test_health_check(self):
        """Test health endpoint returns healthy status."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data


class TestAnalysisEndpoints:
    """Tests for analysis endpoints."""
    
    @patch('src.api.routes.load_analysis')
    def test_get_current_analysis_success(self, mock_load):
        """Test successful retrieval of current analysis."""
        mock_analysis = {
            "timeframe": "1D",
            "timestamp": "2025-01-01T00:00:00",
            "ignore_candles": 1,
            "patterns": {"test": ["GBPUSD"]},
            "instruments": []
        }
        mock_load.return_value = mock_analysis
        
        response = client.get("/api/v1/analysis/1D")
        assert response.status_code == 200
        data = response.json()
        assert data["timeframe"] == "1D"
    
    def test_get_current_analysis_invalid_timeframe(self):
        """Test that invalid timeframe returns 400."""
        response = client.get("/api/v1/analysis/5D")
        assert response.status_code == 400
    
    @patch('src.api.routes.load_analysis')
    def test_get_current_analysis_not_found(self, mock_load):
        """Test that missing analysis returns 404."""
        mock_load.return_value = None
        
        response = client.get("/api/v1/analysis/1D")
        assert response.status_code == 404
    
    @patch('src.api.routes.list_available_dates')
    def test_get_analysis_history(self, mock_list):
        """Test getting analysis history."""
        mock_list.return_value = {
            "current": ["2025-01-01"],
            "backups": ["2025-01-02", "2025-01-03"]
        }
        
        response = client.get("/api/v1/analysis/1D/history")
        assert response.status_code == 200
        data = response.json()
        assert "current" in data
        assert "backups" in data
        assert "all_dates" in data
    
    @patch('src.api.routes.load_analysis')
    def test_get_historical_analysis_success(self, mock_load):
        """Test successful retrieval of historical analysis."""
        mock_analysis = {
            "timeframe": "2D",
            "timestamp": "2025-01-01T00:00:00",
            "ignore_candles": 1,
            "patterns": {},
            "instruments": []
        }
        mock_load.return_value = mock_analysis
        
        response = client.get("/api/v1/analysis/2D/2025-01-01")
        assert response.status_code == 200
        data = response.json()
        assert data["timeframe"] == "2D"
    
    def test_get_historical_analysis_invalid_date(self):
        """Test that invalid date format returns 400."""
        response = client.get("/api/v1/analysis/1D/invalid-date")
        assert response.status_code == 400
    
    @patch('src.api.routes.load_analysis')
    def test_get_historical_analysis_not_found(self, mock_load):
        """Test that missing historical analysis returns 404."""
        mock_load.return_value = None
        
        response = client.get("/api/v1/analysis/1D/2025-01-01")
        assert response.status_code == 404


class TestPullbackEndpoints:
    """Tests for pullback endpoints."""

    @patch("src.api.routes.analyze_all_pullbacks")
    def test_get_pullback_default_weekly(self, mock_analyze):
        """Test GET /pullback with default weekly period."""
        mock_analyze.return_value = {
            "timestamp": "2025-01-01T00:00:00",
            "currency_filter": None,
            "ignore_candles": 0,
            "results": [],
            "strength": None,
            "weakness": None,
            "strength_details": None,
            "weakness_details": None,
            "all_currencies_strength_weakness": None,
        }

        response = client.get("/api/v1/pullback")
        assert response.status_code == 200
        data = response.json()
        assert data["ignore_candles"] == 0
        assert data["currency_filter"] is None
        # Ensure our mock was called with weekly period by default
        mock_analyze.assert_called_once()
        _, kwargs = mock_analyze.call_args
        assert kwargs["period"] == "weekly"

    @patch("src.api.routes.analyze_all_pullbacks")
    def test_get_pullback_monthly_period(self, mock_analyze):
        """Test GET /pullback with monthly period."""
        mock_analyze.return_value = {
            "timestamp": "2025-01-01T00:00:00",
            "currency_filter": "USD",
            "ignore_candles": 2,
            "results": [],
            "strength": None,
            "weakness": None,
            "strength_details": None,
            "weakness_details": None,
            "all_currencies_strength_weakness": None,
        }

        response = client.get("/api/v1/pullback?currency=USD&ignore_candles=2&period=monthly")
        assert response.status_code == 200
        mock_analyze.assert_called_once()
        _, kwargs = mock_analyze.call_args
        assert kwargs["period"] == "monthly"
        assert kwargs["currency_filter"] == "USD"
        assert kwargs["ignore_candles"] == 2

    def test_get_pullback_invalid_period(self):
        """Test GET /pullback with invalid period returns 400."""
        response = client.get("/api/v1/pullback?period=invalid")
        assert response.status_code == 400

    @patch("src.api.routes.analyze_all_pullbacks")
    def test_run_pullback_analysis_monthly(self, mock_analyze):
        """Test POST /pullback/run with monthly period."""
        mock_analyze.return_value = {
            "timestamp": "2025-01-01T00:00:00",
            "currency_filter": "JPY",
            "ignore_candles": 1,
            "results": [],
            "strength": None,
            "weakness": None,
            "strength_details": None,
            "weakness_details": None,
            "all_currencies_strength_weakness": None,
        }

        payload = {
            "currency": "JPY",
            "ignore_candles": 1,
            "period": "monthly",
        }
        response = client.post("/api/v1/pullback/run", json=payload)
        assert response.status_code == 200
        mock_analyze.assert_called_once()
        _, kwargs = mock_analyze.call_args
        assert kwargs["period"] == "monthly"
        assert kwargs["currency_filter"] == "JPY"
        assert kwargs["ignore_candles"] == 1

    def test_run_pullback_analysis_invalid_period(self):
        """Test POST /pullback/run with invalid period returns 400."""
        payload = {
            "currency": "JPY",
            "ignore_candles": 0,
            "period": "invalid",
        }
        response = client.post("/api/v1/pullback/run", json=payload)
        assert response.status_code == 400

