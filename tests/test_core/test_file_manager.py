"""
Unit tests for file manager.
"""
import json
import shutil
from datetime import datetime
from pathlib import Path
import pytest

from src.core.file_manager import (
    backup_current_analysis,
    save_analysis,
    load_analysis,
    list_backup_dates,
    get_current_analysis_date,
    list_available_dates,
)
from src.core.config import LATEST_DIR, BACKUPS_DIR


@pytest.fixture
def cleanup_dirs():
    """Fixture to clean up test directories."""
    yield
    # Cleanup after test
    if LATEST_DIR.exists():
        shutil.rmtree(LATEST_DIR)
    if BACKUPS_DIR.exists():
        shutil.rmtree(BACKUPS_DIR)


class TestFileManager:
    """Tests for file manager functions."""
    
    def test_save_and_load_analysis(self, cleanup_dirs):
        """Test saving and loading analysis."""
        analysis_data = {
            "timeframe": "1D",
            "timestamp": datetime.now().isoformat(),
            "patterns": {"test": ["GBPUSD"]},
            "instruments": []
        }
        
        # Save
        saved_path = save_analysis(analysis_data, "1D")
        assert saved_path.exists()
        
        # Load
        loaded_data = load_analysis("1D", date=None)
        assert loaded_data is not None
        assert loaded_data["timeframe"] == "1D"
        assert loaded_data["patterns"] == {"test": ["GBPUSD"]}
    
    def test_backup_current_analysis(self, cleanup_dirs):
        """Test backing up current analysis."""
        # First save some data
        analysis_data = {
            "timeframe": "2D",
            "timestamp": datetime.now().isoformat(),
            "patterns": {},
            "instruments": []
        }
        save_analysis(analysis_data, "2D")
        
        # Backup
        backup_dir = backup_current_analysis("2D")
        assert backup_dir.exists()
        
        # Check that latest is empty or doesn't exist
        latest_dir = LATEST_DIR / "2D"
        if latest_dir.exists():
            assert not any(latest_dir.glob("*.json"))
    
    def test_list_backup_dates(self, cleanup_dirs):
        """Test listing backup dates."""
        # Create a backup
        analysis_data = {
            "timeframe": "3D",
            "timestamp": datetime.now().isoformat(),
            "patterns": {},
            "instruments": []
        }
        save_analysis(analysis_data, "3D")
        
        today = datetime.now().strftime("%Y-%m-%d")
        backup_dir = backup_current_analysis("3D", backup_date=today)
        
        # List backups
        dates = list_backup_dates("3D")
        assert today in dates
    
    def test_get_current_analysis_date(self, cleanup_dirs):
        """Test getting current analysis date."""
        analysis_data = {
            "timeframe": "4D",
            "timestamp": datetime.now().isoformat(),
            "patterns": {},
            "instruments": []
        }
        save_analysis(analysis_data, "4D")
        
        date = get_current_analysis_date("4D")
        assert date is not None
        assert len(date) == 10  # YYYY-MM-DD format
    
    def test_list_available_dates(self, cleanup_dirs):
        """Test listing all available dates."""
        # Save current
        analysis_data = {
            "timeframe": "1D",
            "timestamp": datetime.now().isoformat(),
            "patterns": {},
            "instruments": []
        }
        save_analysis(analysis_data, "1D")
        
        # Create backup
        today = datetime.now().strftime("%Y-%m-%d")
        backup_current_analysis("1D", backup_date=today)
        
        # List all dates
        dates = list_available_dates("1D")
        assert "current" in dates
        assert "backups" in dates
        assert len(dates["backups"]) >= 1
    
    def test_normalize_timeframe_in_file_ops(self, cleanup_dirs):
        """Test that file operations normalize timeframes."""
        analysis_data = {
            "timeframe": "1D",
            "timestamp": datetime.now().isoformat(),
            "patterns": {},
            "instruments": []
        }
        
        # Save with various formats
        save_analysis(analysis_data, "D")
        save_analysis(analysis_data, "1d")
        
        # Both should save to same directory
        assert (LATEST_DIR / "1D").exists()

