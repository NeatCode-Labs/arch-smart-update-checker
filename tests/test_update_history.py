"""
Tests for the update history management functionality.
"""

import pytest
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, Mock

from src.utils.update_history import UpdateHistoryManager, UpdateHistoryEntry


class TestUpdateHistoryEntry:
    """Test UpdateHistoryEntry dataclass."""
    
    def test_create_entry(self):
        """Test creating a basic entry."""
        now = datetime.now()
        entry = UpdateHistoryEntry(
            timestamp=now,
            packages=['python', 'firefox'],
            succeeded=True,
            exit_code=0,
            duration_sec=45.2
        )
        
        assert entry.timestamp == now
        assert entry.packages == ['python', 'firefox']
        assert entry.succeeded is True
        assert entry.exit_code == 0
        assert entry.duration_sec == 45.2
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        now = datetime.now()
        entry = UpdateHistoryEntry(
            timestamp=now,
            packages=['vim', 'git'],
            succeeded=False,
            exit_code=1,
            duration_sec=12.5
        )
        
        data = entry.to_dict()
        
        assert data['timestamp'] == now.isoformat()
        assert data['packages'] == ['vim', 'git']
        assert data['succeeded'] is False
        assert data['exit_code'] == 1
        assert data['duration_sec'] == 12.5
    
    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            'timestamp': '2024-01-15T10:30:00.123456',
            'packages': ['kernel', 'systemd'],
            'succeeded': True,
            'exit_code': 0,
            'duration_sec': 120.8
        }
        
        entry = UpdateHistoryEntry.from_dict(data)
        
        assert entry.timestamp == datetime.fromisoformat(data['timestamp'])
        assert entry.packages == ['kernel', 'systemd']
        assert entry.succeeded is True
        assert entry.exit_code == 0
        assert entry.duration_sec == 120.8


class TestUpdateHistoryManager:
    """Test UpdateHistoryManager functionality."""
    
    def test_init(self, tmp_cache_dir):
        """Test manager initialization."""
        history_file = tmp_cache_dir / "custom_history.json"
        manager = UpdateHistoryManager(str(history_file), retention_days=30)
        
        assert manager.path == history_file
        assert manager.retention_days == 30
        assert history_file.parent.exists()
    
    def test_init_default_path(self, tmp_cache_dir):
        """Test manager initialization with default path."""
        with patch('src.utils.update_history.get_cache_dir', return_value=tmp_cache_dir):
            manager = UpdateHistoryManager()
            expected_path = tmp_cache_dir / "update_history.json"
            assert manager.path == expected_path
    
    def test_add_and_load(self, tmp_cache_dir):
        """Test adding entries and loading them back."""
        history_file = tmp_cache_dir / "test_history.json"
        manager = UpdateHistoryManager(str(history_file))
        
        # Add first entry
        entry1 = UpdateHistoryEntry(
            timestamp=datetime.now() - timedelta(hours=1),
            packages=['package1'],
            succeeded=True,
            exit_code=0,
            duration_sec=30.0
        )
        manager.add(entry1)
        
        # Add second entry
        entry2 = UpdateHistoryEntry(
            timestamp=datetime.now(),
            packages=['package2', 'package3'],
            succeeded=False,
            exit_code=1,
            duration_sec=45.5
        )
        manager.add(entry2)
        
        # Wait for async operations to complete
        manager._executor.shutdown(wait=True)
        
        # Load entries back
        entries = manager.all()
        
        assert len(entries) == 2
        # Entries should be returned newest first
        assert entries[0].packages == ['package2', 'package3']
        assert entries[0].succeeded is False
        assert entries[1].packages == ['package1']
        assert entries[1].succeeded is True
    
    def test_retention_trim(self, tmp_cache_dir):
        """Test automatic retention trimming."""
        history_file = tmp_cache_dir / "test_history.json"
        manager = UpdateHistoryManager(str(history_file), retention_days=1)
        
        # Add old entry (should be trimmed)
        old_entry = UpdateHistoryEntry(
            timestamp=datetime.now() - timedelta(days=2),
            packages=['old_package'],
            succeeded=True,
            exit_code=0,
            duration_sec=10.0
        )
        manager.add(old_entry)
        
        # Add recent entry (should be kept)
        recent_entry = UpdateHistoryEntry(
            timestamp=datetime.now(),
            packages=['new_package'],
            succeeded=True,
            exit_code=0,
            duration_sec=15.0
        )
        manager.add(recent_entry)
        
        # Wait for operations to complete
        manager._executor.shutdown(wait=True)
        
        # Load entries - only recent one should remain
        entries = manager.all()
        
        assert len(entries) == 1
        assert entries[0].packages == ['new_package']
    
    def test_clear(self, tmp_cache_dir):
        """Test clearing all history."""
        history_file = tmp_cache_dir / "test_history.json"
        manager = UpdateHistoryManager(str(history_file))
        
        # Add some entries
        entry = UpdateHistoryEntry(
            timestamp=datetime.now(),
            packages=['package1'],
            succeeded=True,
            exit_code=0,
            duration_sec=20.0
        )
        manager.add(entry)
        
        # Wait for add to complete
        manager._executor.shutdown(wait=True)
        
        # Verify entry exists
        assert len(manager.all()) == 1
        
        # Clear history
        manager.clear()
        
        # Verify it's empty
        assert len(manager.all()) == 0
        # The file should still exist but contain an empty list
        assert history_file.exists()
        with open(history_file) as f:
            data = json.load(f)
            assert data == []
    
    def test_export_json(self, tmp_cache_dir):
        """Test JSON export functionality."""
        history_file = tmp_cache_dir / "test_history.json"
        # Use longer retention to avoid trimming test entries
        manager = UpdateHistoryManager(str(history_file), retention_days=3650)
        
        # Add test entries with recent dates
        entry1 = UpdateHistoryEntry(
            timestamp=datetime.now() - timedelta(hours=2),
            packages=['pkg1'],
            succeeded=True,
            exit_code=0,
            duration_sec=25.0
        )
        entry2 = UpdateHistoryEntry(
            timestamp=datetime.now() - timedelta(hours=1),
            packages=['pkg2', 'pkg3'],
            succeeded=False,
            exit_code=1,
            duration_sec=60.5
        )
        
        manager.add(entry1)
        manager.add(entry2)
        manager._executor.shutdown(wait=True)
        
        # Export to JSON
        export_file = tmp_cache_dir / "exported.json"
        manager.export(str(export_file), 'json')
        
        # Verify export
        with open(export_file) as f:
            data = json.load(f)
        
        assert len(data) == 2
        # Should be newest first
        assert data[0]['packages'] == ['pkg2', 'pkg3']
        assert data[0]['succeeded'] is False
        assert data[1]['packages'] == ['pkg1']
        assert data[1]['succeeded'] is True
    
    def test_export_csv(self, tmp_cache_dir):
        """Test CSV export functionality."""
        history_file = tmp_cache_dir / "test_history.json"
        manager = UpdateHistoryManager(str(history_file))
        
        # Add test entry
        entry = UpdateHistoryEntry(
            timestamp=datetime(2024, 1, 15, 10, 30),
            packages=['test_pkg'],
            succeeded=True,
            exit_code=0,
            duration_sec=15.5
        )
        manager.add(entry)
        manager._executor.shutdown(wait=True)
        
        # Export to CSV
        export_file = tmp_cache_dir / "exported.csv"
        manager.export(str(export_file), 'csv')
        
        # Verify export
        with open(export_file) as f:
            lines = f.readlines()
        
        assert len(lines) == 2  # Header + 1 data row
        assert 'timestamp,packages,succeeded,exit_code,duration_sec' in lines[0]
        assert '2024-01-15T10:30:00' in lines[1]
        assert 'test_pkg' in lines[1]
        assert 'Yes' in lines[1]
        assert '0' in lines[1]
        assert '15.5' in lines[1]
    
    def test_file_corruption_handling(self, tmp_cache_dir):
        """Test handling of corrupted history files."""
        history_file = tmp_cache_dir / "corrupt_history.json"
        
        # Create corrupted JSON file
        with open(history_file, 'w') as f:
            f.write('{"invalid": json content')
        
        # Manager should handle corruption gracefully
        manager = UpdateHistoryManager(str(history_file))
        entries = manager.all()
        
        assert entries == []  # Should return empty list
    
    def test_empty_file_handling(self, tmp_cache_dir):
        """Test handling of non-existent files."""
        history_file = tmp_cache_dir / "nonexistent.json"
        manager = UpdateHistoryManager(str(history_file))
        
        # Should handle missing file gracefully
        entries = manager.all()
        assert entries == []
    
    def test_file_size_limiting(self, tmp_cache_dir):
        """Test file size limiting functionality."""
        history_file = tmp_cache_dir / "test_history.json"
        manager = UpdateHistoryManager(str(history_file))
        
        # Add many entries to trigger size limit
        for i in range(150000):  # Should exceed 10MB estimate
            entry = UpdateHistoryEntry(
                timestamp=datetime.now() - timedelta(days=i),
                packages=[f'package_{i}'],
                succeeded=True,
                exit_code=0,
                duration_sec=1.0
            )
            # Directly add to avoid async complications in test
            entries = manager._load_entries()
            entries.append(entry)
            manager._save_entries(entries)
            
            # Check if trimming occurred
            final_entries = manager._load_entries()
            if len(final_entries) < i + 1:
                # Trimming occurred
                break
        
        # Verify some trimming happened
        final_entries = manager.all()
        assert len(final_entries) < 150000
    
    def test_concurrent_access(self, tmp_cache_dir):
        """Test thread safety with concurrent access."""
        history_file = tmp_cache_dir / "concurrent_test.json"
        manager = UpdateHistoryManager(str(history_file))
        
        # Add entries concurrently (simulated)
        entries_to_add = []
        for i in range(10):
            entry = UpdateHistoryEntry(
                timestamp=datetime.now() - timedelta(seconds=i),
                packages=[f'pkg_{i}'],
                succeeded=True,
                exit_code=0,
                duration_sec=float(i)
            )
            entries_to_add.append(entry)
        
        # Add all entries
        for entry in entries_to_add:
            manager.add(entry)
        
        # Wait for all operations to complete
        manager._executor.shutdown(wait=True)
        
        # Verify all entries were added
        final_entries = manager.all()
        assert len(final_entries) == 10
        
        # Verify they're in correct order (newest first)
        for i, entry in enumerate(final_entries):
            assert entry.packages == [f'pkg_{i}'] 