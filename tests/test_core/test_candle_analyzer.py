"""
Unit tests for candle analyzer.

Note: These tests may require mocking OANDA API calls in a real scenario.
"""
import pytest
from unittest.mock import patch, MagicMock

from src.core.candle_analyzer import (
    merge_candles,
    analyze_candle_relation,
)


class TestMergeCandles:
    """Tests for merge_candles function."""
    
    def test_merge_single_candle(self):
        """Test merging a single candle."""
        candles = [{
            "mid": {"o": "1.1000", "h": "1.1100", "l": "1.0900", "c": "1.1050"},
            "time": "2025-01-01T00:00:00Z"
        }]
        
        merged = merge_candles(candles)
        assert merged is not None
        assert merged["open"] == "1.1000"
        assert merged["close"] == "1.1050"
        assert merged["high"] == 1.1100
        assert merged["low"] == 1.0900
        assert merged["candle_count"] == 1
    
    def test_merge_multiple_candles(self):
        """Test merging multiple candles."""
        candles = [
            {
                "mid": {"o": "1.1000", "h": "1.1100", "l": "1.0900", "c": "1.1050"},
                "time": "2025-01-01T00:00:00Z"
            },
            {
                "mid": {"o": "1.1050", "h": "1.1200", "l": "1.1000", "c": "1.1150"},
                "time": "2025-01-02T00:00:00Z"
            }
        ]
        
        merged = merge_candles(candles)
        assert merged is not None
        assert merged["open"] == "1.1000"  # First candle's open
        assert merged["close"] == "1.1150"  # Last candle's close
        assert merged["high"] == 1.1200  # Max high
        assert merged["low"] == 1.0900  # Min low
        assert merged["candle_count"] == 2
    
    def test_merge_empty_list(self):
        """Test merging empty list returns None."""
        assert merge_candles([]) is None


class TestAnalyzeCandleRelation:
    """Tests for analyze_candle_relation function."""
    
    def test_upclose_pattern(self):
        """Test upclose pattern detection."""
        mc1 = {"high": 1.1000, "low": 1.0900, "open": "1.0950", "close": "1.0950"}
        mc2 = {"high": 1.1200, "low": 1.1000, "open": "1.1050", "close": "1.1100"}
        
        relation = analyze_candle_relation(mc1, mc2)
        assert "upclose ⬆️" in relation
    
    def test_downclose_pattern(self):
        """Test downclose pattern detection."""
        mc1 = {"high": 1.1000, "low": 1.0900, "open": "1.0950", "close": "1.0950"}
        mc2 = {"high": 1.0900, "low": 1.0800, "open": "1.0850", "close": "1.0850"}
        
        relation = analyze_candle_relation(mc1, mc2)
        assert "downclose ⬇️" in relation
    
    def test_bullish_engulfing(self):
        """Test bullish engulfing pattern."""
        mc1 = {"high": 1.1000, "low": 1.0900, "open": "1.0950", "close": "1.0920"}
        mc2 = {"high": 1.1100, "low": 1.0850, "open": "1.0880", "close": "1.1050"}
        
        relation = analyze_candle_relation(mc1, mc2)
        assert "bullish engulfing" in relation
    
    def test_bearish_engulfing(self):
        """Test bearish engulfing pattern."""
        mc1 = {"high": 1.1000, "low": 1.0900, "open": "1.0920", "close": "1.0950"}
        mc2 = {"high": 1.1050, "low": 1.0850, "open": "1.1050", "close": "1.0880"}
        
        relation = analyze_candle_relation(mc1, mc2)
        assert "bearish engulfing" in relation
    
    def test_bullish_engulfing_requires_red_mc1(self):
        """Test that bullish engulfing requires MC1 to be red (close < open)."""
        # MC1 is green (close > open), MC2 is green - should NOT be bullish engulfing
        mc1 = {"high": 1.1000, "low": 1.0900, "open": "1.0920", "close": "1.0950"}  # MC1 green
        mc2 = {"high": 1.1100, "low": 1.0850, "open": "1.0880", "close": "1.1050"}  # MC2 green, engulfs
        
        relation = analyze_candle_relation(mc1, mc2)
        assert "bullish engulfing" not in relation
    
    def test_bearish_engulfing_requires_green_mc1(self):
        """Test that bearish engulfing requires MC1 to be green (close > open)."""
        # MC1 is red (close < open), MC2 is red - should NOT be bearish engulfing
        mc1 = {"high": 1.1000, "low": 1.0900, "open": "1.0950", "close": "1.0920"}  # MC1 red
        mc2 = {"high": 1.1050, "low": 1.0850, "open": "1.1050", "close": "1.0880"}  # MC2 red, engulfs
        
        relation = analyze_candle_relation(mc1, mc2)
        assert "bearish engulfing" not in relation
    
    def test_neutral_pattern(self):
        """Test neutral pattern when no special patterns detected."""
        mc1 = {"high": 1.1000, "low": 1.0900, "open": "1.0950", "close": "1.0950"}
        mc2 = {"high": 1.1000, "low": 1.0900, "open": "1.0950", "close": "1.0950"}
        
        relation = analyze_candle_relation(mc1, mc2)
        assert relation == "neutral"
    
    def test_error_on_none(self):
        """Test that None inputs return 'error'."""
        assert analyze_candle_relation(None, {}) == "error"
        assert analyze_candle_relation({}, None) == "error"
        assert analyze_candle_relation(None, None) == "error"

