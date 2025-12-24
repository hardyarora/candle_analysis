"""
Unit tests for timeframe utilities.
"""
import pytest

from src.utils.timeframe import normalize_timeframe, parse_timeframe, is_valid_timeframe


class TestNormalizeTimeframe:
    """Tests for normalize_timeframe function."""
    
    def test_single_d(self):
        """Test that D normalizes to 1D."""
        assert normalize_timeframe("D") == "1D"
        assert normalize_timeframe("d") == "1D"
        assert normalize_timeframe(" D ") == "1D"
    
    def test_numeric_prefixes(self):
        """Test numeric prefixes with D."""
        assert normalize_timeframe("1D") == "1D"
        assert normalize_timeframe("1d") == "1D"
        assert normalize_timeframe("2D") == "2D"
        assert normalize_timeframe("2d") == "2D"
        assert normalize_timeframe("3D") == "3D"
        assert normalize_timeframe("4D") == "4D"
    
    def test_invalid_timeframes(self):
        """Test that invalid timeframes raise ValueError."""
        with pytest.raises(ValueError):
            normalize_timeframe("5D")
        
        with pytest.raises(ValueError):
            normalize_timeframe("0D")
        
        with pytest.raises(ValueError):
            normalize_timeframe("W")
        
        with pytest.raises(ValueError):
            normalize_timeframe("")
        
        with pytest.raises(ValueError):
            normalize_timeframe("invalid")


class TestParseTimeframe:
    """Tests for parse_timeframe function."""
    
    def test_parse_single_d(self):
        """Test parsing single D."""
        granularity, count = parse_timeframe("D")
        assert granularity == "D"
        assert count == 1
    
    def test_parse_numeric_prefixes(self):
        """Test parsing numeric prefixes."""
        assert parse_timeframe("1D") == ("D", 1)
        assert parse_timeframe("2D") == ("D", 2)
        assert parse_timeframe("3D") == ("D", 3)
        assert parse_timeframe("4D") == ("D", 4)
    
    def test_parse_case_insensitive(self):
        """Test that parsing is case insensitive."""
        assert parse_timeframe("1d") == ("D", 1)
        assert parse_timeframe("2d") == ("D", 2)


class TestIsValidTimeframe:
    """Tests for is_valid_timeframe function."""
    
    def test_valid_timeframes(self):
        """Test that valid timeframes return True."""
        assert is_valid_timeframe("D") is True
        assert is_valid_timeframe("1D") is True
        assert is_valid_timeframe("2D") is True
        assert is_valid_timeframe("3D") is True
        assert is_valid_timeframe("4D") is True
        assert is_valid_timeframe("1d") is True
        assert is_valid_timeframe("2d") is True
    
    def test_invalid_timeframes(self):
        """Test that invalid timeframes return False."""
        assert is_valid_timeframe("5D") is False
        assert is_valid_timeframe("W") is False
        assert is_valid_timeframe("") is False
        assert is_valid_timeframe("invalid") is False
