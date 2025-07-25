"""
Tests for the CLI functionality.
"""

import pytest
import json
import subprocess
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
from pathlib import Path

from src.cli.main import AsucCLI, create_parser
from src.models import PackageUpdate, NewsItem, UpdateCheckResult, UpdateStatus
from src.utils.update_history import UpdateHistoryEntry


class TestCLIParser:
    """Test command line argument parsing."""
    
    def test_default_command(self):
        """Test that no command defaults to None (triggering default check behavior)."""
        parser = create_parser()
        args = parser.parse_args([])
        assert args.command is None  # Default behavior (triggers comprehensive check)
    
    def test_check_command(self):
        """Test updates command parsing (replaces legacy check command)."""
        parser = create_parser()
        args = parser.parse_args(['updates'])
        assert args.command == 'updates'
    
    def test_updates_command(self):
        """Test updates command parsing."""
        parser = create_parser()
        args = parser.parse_args(['updates'])
        assert args.command == 'updates'
    
    def test_config_command(self):
        """Test config command parsing."""
        parser = create_parser()
        
        # Test config get action
        args = parser.parse_args(['config', 'get'])
        assert args.command == 'config'
        assert args.action == 'get'
        
        # Test config set action with key and value
        args = parser.parse_args(['config', 'set', 'cache_ttl_hours', '2'])
        assert args.command == 'config'
        assert args.action == 'set'
        assert args.key == 'cache_ttl_hours'
        assert args.value == '2'
    
    def test_history_command(self):
        """Test history command parsing."""
        parser = create_parser()
        
        # Basic history
        args = parser.parse_args(['history'])
        assert args.command == 'history'
        assert args.limit is None
        assert args.clear is False
        assert args.export is None
        
        # With options
        args = parser.parse_args(['history', '--limit', '10', '--clear', '--yes'])
        assert args.limit == 10
        assert args.clear is True
        assert args.yes is True
        
        # With export
        args = parser.parse_args(['history', '--export', 'history.csv'])
        assert args.export == 'history.csv'
    
    def test_config_command(self):
        """Test config command parsing."""
        parser = create_parser()
        
        # Get all config
        args = parser.parse_args(['config', 'get'])
        assert args.command == 'config'
        assert args.action == 'get'
        assert args.key is None
        
        # Get specific key
        args = parser.parse_args(['config', 'get', 'update_history_enabled'])
        assert args.action == 'get'
        assert args.key == 'update_history_enabled'
        
        # Set value
        args = parser.parse_args(['config', 'set', 'theme', 'dark'])
        assert args.action == 'set'
        assert args.key == 'theme'
        assert args.value == 'dark'
    
    def test_global_options(self):
        """Test global options parsing."""
        parser = create_parser()
        
        args = parser.parse_args(['--json', '--no-color', '--quiet', 'updates'])
        assert args.json is True
        assert args.no_color is True
        assert args.quiet is True
        assert args.command == 'updates'


class TestAsucCLI:
    """Test CLI application functionality."""
    
    def test_init(self, tmp_cache_dir):
        """Test CLI initialization."""
        with patch('src.cli.main.Config') as mock_config_class:
            mock_config = Mock()
            # Mock the get method to return proper values
            mock_config.get.return_value = 365  # Return int for retention days
            mock_config_class.return_value = mock_config
            
            cli = AsucCLI()
            
            assert cli.config == mock_config
            assert cli.formatter is None  # Not set until run()
    
    def test_cmd_check_no_updates(self, history_enabled_config, tmp_cache_dir):
        """Test check command with no updates available."""
        cli = AsucCLI()
        cli.config = history_enabled_config
        
        # Mock the checker to return no updates
        mock_result = UpdateCheckResult(
            status=UpdateStatus.SUCCESS,
            updates=[],
            news_items=[],
            error_message=None
        )
        
        with patch.object(cli.checker, 'check_updates', return_value=mock_result):
            args = Mock()
            args.command = None  # Default behavior triggers check
            args.json = False
            args.quiet = False
            args.no_color = False
            
            exit_code = cli.run(args)
            
            assert exit_code == 0
    
    def test_cmd_check_with_updates(self, history_enabled_config, tmp_cache_dir):
        """Test check command with updates available."""
        cli = AsucCLI()
        cli.config = history_enabled_config
        
        # Mock updates
        mock_updates = [
            PackageUpdate('python', '3.11.0', '3.11.1'),
            PackageUpdate('firefox', '100.0', '101.0')
        ]
        
        mock_result = UpdateCheckResult(
            status=UpdateStatus.SUCCESS,
            updates=mock_updates,
            news_items=[],
            error_message=None
        )
        
        with patch.object(cli.checker, 'check_updates', return_value=mock_result):
            args = Mock()
            args.command = None  # Default behavior triggers check
            args.json = False
            args.quiet = True  # Avoid interactive prompt during testing
            args.no_color = False
            
            exit_code = cli.run(args)
            
            assert exit_code == 10  # Updates available
    
    def test_cmd_check_json_output(self, history_enabled_config, tmp_cache_dir):
        """Test check command with JSON output."""
        cli = AsucCLI()
        cli.config = history_enabled_config
        
        mock_updates = [PackageUpdate('vim', '8.0', '8.1')]
        mock_news = [Mock()]
        mock_news[0].title = "Test News"
        mock_news[0].url = "http://example.com"
        mock_news[0].published = "2024-01-15"
        mock_news[0].affected_packages = {'vim'}
        
        mock_result = UpdateCheckResult(
            status=UpdateStatus.SUCCESS,
            updates=mock_updates,
            news_items=mock_news,
            error_message=None
        )
        
        with patch.object(cli.checker, 'check_updates', return_value=mock_result), \
             patch('builtins.print') as mock_print:

            args = Mock()
            args.command = None  # Default behavior triggers check
            args.json = True
            args.quiet = False
            args.no_color = False

            exit_code = cli.run(args)
            
            # Should print JSON output
            assert mock_print.called
            printed_output = mock_print.call_args[0][0]
            data = json.loads(printed_output)
            
            assert data['update_count'] == 1
            assert data['news_count'] == 1
            assert len(data['updates']) == 1
            assert data['updates'][0]['name'] == 'vim'
    
    def test_cmd_updates(self, history_enabled_config, tmp_cache_dir):
        """Test updates command."""
        cli = AsucCLI()
        cli.config = history_enabled_config
        
        mock_updates = [
            PackageUpdate('git', '2.40.0', '2.41.0'),
            PackageUpdate('curl', '8.0.0', '8.1.0')
        ]
        
        with patch.object(cli.package_manager, 'check_for_updates', return_value=mock_updates):
            args = Mock()
            args.command = 'updates'
            args.json = False
            args.no_color = False
            
            exit_code = cli.run(args)
            
            assert exit_code == 0
    
    def test_cmd_history_display(self, history_enabled_config, tmp_cache_dir):
        """Test history command - display entries."""
        cli = AsucCLI()
        cli.config = history_enabled_config
        
        # Mock history entries
        mock_entries = [
            UpdateHistoryEntry(
                timestamp=datetime.now(),
                packages=['pkg1'],
                succeeded=True,
                exit_code=0,
                duration_sec=25.0
            ),
            UpdateHistoryEntry(
                timestamp=datetime.now() - timedelta(hours=1),
                packages=['pkg2', 'pkg3'],
                succeeded=False,
                exit_code=1,
                duration_sec=45.5
            )
        ]
        
        with patch.object(cli.update_history, 'all', return_value=mock_entries):
            args = Mock()
            args.command = 'history'
            args.clear = False
            args.export = None
            args.limit = None
            args.json = False
            args.no_color = False
            
            exit_code = cli.run(args)
            
            assert exit_code == 0
    
    def test_cmd_history_clear(self, history_enabled_config, tmp_cache_dir):
        """Test history command - clear entries."""
        cli = AsucCLI()
        cli.config = history_enabled_config
        
        with patch.object(cli.update_history, 'clear') as mock_clear:
            args = Mock()
            args.command = 'history'
            args.clear = True
            args.yes = True
            args.export = None
            args.json = False
            args.no_color = False
            
            exit_code = cli.run(args)
            
            assert exit_code == 0
            mock_clear.assert_called_once()
    
    def test_cmd_history_export(self, history_enabled_config, tmp_cache_dir):
        """Test history command - export entries."""
        cli = AsucCLI()
        cli.config = history_enabled_config
        
        export_file = str(tmp_cache_dir / "export.json")
        
        with patch.object(cli.update_history, 'export') as mock_export:
            args = Mock()
            args.command = 'history'
            args.clear = False
            args.export = export_file
            args.json = False
            args.no_color = False
            
            exit_code = cli.run(args)
            
            assert exit_code == 0
            mock_export.assert_called_once_with(export_file, 'json')
    
    def test_cmd_config_get_all(self, history_enabled_config, tmp_cache_dir):
        """Test config command - get all settings."""
        cli = AsucCLI()
        cli.config = history_enabled_config
        
        with patch('builtins.print') as mock_print:
            args = Mock()
            args.command = 'config'
            args.action = 'get'
            args.key = None
            args.json = False
            args.no_color = False
            
            exit_code = cli.run(args)
            
            assert exit_code == 0
            # Should print config items
            assert mock_print.called
    
    def test_cmd_config_get_specific(self, history_enabled_config, tmp_cache_dir):
        """Test config command - get specific key."""
        cli = AsucCLI()
        cli.config = history_enabled_config
        
        with patch('builtins.print') as mock_print:
            args = Mock()
            args.command = 'config'
            args.action = 'get'
            args.key = 'update_history_enabled'
            args.json = False
            args.no_color = False
            
            exit_code = cli.run(args)
            
            assert exit_code == 0
            mock_print.assert_called_once_with(True)
    
    def test_cmd_config_set(self, history_enabled_config, tmp_cache_dir):
        """Test config command - set value."""
        cli = AsucCLI()
        cli.config = history_enabled_config
        
        with patch.object(cli.config, 'set') as mock_set, \
             patch.object(cli.config, 'save_config') as mock_save:
            
            args = Mock()
            args.command = 'config'
            args.action = 'set'
            args.key = 'theme'
            args.value = 'dark'
            args.json = False
            args.no_color = False
            
            exit_code = cli.run(args)
            
            assert exit_code == 0
            mock_set.assert_called_once_with('theme', 'dark')
            mock_save.assert_called_once()
    
    def test_cmd_config_set_boolean(self, history_enabled_config, tmp_cache_dir):
        """Test config command - set boolean value."""
        cli = AsucCLI()
        cli.config = history_enabled_config
        
        with patch.object(cli.config, 'set') as mock_set, \
             patch.object(cli.config, 'save_config') as mock_save:
            
            args = Mock()
            args.command = 'config'
            args.action = 'set'
            args.key = 'update_history_enabled'
            args.value = 'false'
            args.json = False
            args.no_color = False
            
            exit_code = cli.run(args)
            
            assert exit_code == 0
            # Should convert string 'false' to boolean False
            mock_set.assert_called_once_with('update_history_enabled', False)
    
    def test_cmd_config_set_integer(self, history_enabled_config, tmp_cache_dir):
        """Test config command - set integer value."""
        cli = AsucCLI()
        cli.config = history_enabled_config
        
        with patch.object(cli.config, 'set') as mock_set, \
             patch.object(cli.config, 'save_config') as mock_save:
            
            args = Mock()
            args.command = 'config'
            args.action = 'set'
            args.key = 'update_history_retention_days'
            args.value = '30'
            args.json = False
            args.no_color = False
            
            exit_code = cli.run(args)
            
            assert exit_code == 0
            # Should convert string '30' to integer 30
            mock_set.assert_called_once_with('update_history_retention_days', 30)
    
    def test_cmd_clear_cache(self, history_enabled_config, tmp_cache_dir):
        """Test clear-cache command."""
        cli = AsucCLI()
        cli.config = history_enabled_config
        
        # Create dummy cache directory
        feed_cache = tmp_cache_dir / "feeds"
        feed_cache.mkdir()
        
        with patch('src.utils.subprocess_wrapper.SecureSubprocess.run') as mock_run:
            from subprocess import CompletedProcess
            mock_run.return_value = CompletedProcess(['sudo', 'paccache', '-r'], 0, '', '')
            
            args = Mock()
            args.command = 'clear-cache'
            args.json = False
            args.no_color = False
            
            exit_code = cli.run(args)
            
            assert exit_code == 0
            # Should have tried to clear pacman cache
            mock_run.assert_called_once()
    
    def test_news_filtering(self, history_enabled_config, tmp_cache_dir):
        """Test news command filtering."""
        cli = AsucCLI()
        cli.config = history_enabled_config
        
        # Mock available updates
        mock_updates = [PackageUpdate('kernel', '6.1.0', '6.2.0')]
        
        # Mock news items
        mock_news = [Mock()]
        mock_news[0].feed_type = 'news'
        mock_news[0].affected_packages = {'kernel'}
        mock_news[0].title = "Kernel Security Update"
        mock_news[0].url = "http://example.com"
        mock_news[0].published = "2024-01-15"
        mock_news[0].content = "Important kernel update"
        
        with patch.object(cli.package_manager, 'check_for_updates', return_value=mock_updates), \
             patch.object(cli.checker.news_fetcher, 'fetch_all_feeds', return_value=mock_news):
            
            args = Mock()
            args.command = 'news'
            args.json = False
            args.no_color = False
            
            exit_code = cli.run(args)
            
            assert exit_code == 0


class TestCLIIntegration:
    """Integration tests using the CLI runner fixture."""
    
    def test_cli_runner_check_command(self, cli_runner, tmp_cache_dir):
        """Test running check command via CLI runner."""
        # Create a mock config file
        config_file = tmp_cache_dir / "config.json"
        with open(config_file, 'w') as f:
            json.dump({
                "update_history_enabled": False,
                "cache_ttl_hours": 1
            }, f)
        
        # Integration test - this actually runs the CLI, so mocks don't work
        # We just test that the CLI runs without crashing (no command triggers default check behavior)
        result = cli_runner('--config', str(config_file), '--json')
        
        # CLI should not crash - exit codes 0 (no updates) or 10 (updates available) are both valid
        assert result.returncode in [0, 10]
        
        # If JSON output, it should be valid JSON
        if result.stdout:
            try:
                data = json.loads(result.stdout)
                assert 'update_count' in data
                assert 'news_count' in data
                assert isinstance(data['updates'], list)
                assert isinstance(data['news'], list)
            except json.JSONDecodeError:
                pytest.fail("CLI did not produce valid JSON output")
    
    def test_cli_runner_help(self, cli_runner):
        """Test CLI help output."""
        result = cli_runner('--help')
        
        assert result.returncode == 0
        assert 'asuc-cli' in result.stdout
        assert 'updates' in result.stdout
        assert 'news' in result.stdout
        assert 'history' in result.stdout
        assert 'config' in result.stdout
    
    def test_cli_runner_invalid_command(self, cli_runner):
        """Test CLI with invalid command."""
        result = cli_runner('invalid-command')
        
        assert result.returncode != 0 