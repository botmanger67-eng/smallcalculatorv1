"""
Main application tests.

This module contains comprehensive tests for the main application entry point,
including CLI argument parsing, configuration loading, and application startup.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from pytest import MonkeyPatch, FixtureRequest

from src.main import (
    create_app,
    parse_arguments,
    load_configuration,
    validate_configuration,
    main,
    ApplicationError,
    ConfigurationError,
    ArgumentError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_config_file() -> Generator[Path, None, None]:
    """Create a temporary configuration file for testing."""
    config_data: Dict[str, Any] = {
        "app": {
            "name": "test-app",
            "version": "1.0.0",
            "debug": False,
            "host": "localhost",
            "port": 8080,
        },
        "database": {
            "url": "sqlite:///test.db",
            "pool_size": 5,
            "max_overflow": 10,
        },
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
    }
    
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
    ) as f:
        json.dump(config_data, f)
        temp_path: Path = Path(f.name)
    
    yield temp_path
    
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def invalid_config_file() -> Generator[Path, None, None]:
    """Create an invalid configuration file for testing."""
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
    ) as f:
        f.write("invalid json content")
        temp_path: Path = Path(f.name)
    
    yield temp_path
    
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def mock_env_vars(monkeypatch: MonkeyPatch) -> Dict[str, str]:
    """Set up mock environment variables for testing."""
    env_vars: Dict[str, str] = {
        "APP_NAME": "test-app-env",
        "APP_DEBUG": "true",
        "DB_URL": "postgresql://user:pass@localhost/test",
        "LOG_LEVEL": "DEBUG",
    }
    
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    
    return env_vars


@pytest.fixture
def mock_application() -> MagicMock:
    """Create a mock application instance."""
    app: MagicMock = MagicMock()
    app.name = "test-app"
    app.version = "1.0.0"
    app.debug = False
    app.host = "localhost"
    app.port = 8080
    app.is_running = False
    
    return app


# ---------------------------------------------------------------------------
# Test: parse_arguments
# ---------------------------------------------------------------------------

class TestParseArguments:
    """Tests for the parse_arguments function."""

    def test_default_arguments(self) -> None:
        """Test parsing with default arguments."""
        test_args: List[str] = ["main.py"]
        with patch.object(sys, "argv", test_args):
            args: Any = parse_arguments()
            
            assert args.config is None
            assert args.verbose is False
            assert args.port is None
            assert args.host is None
            assert args.debug is False

    def test_custom_config_path(self) -> None:
        """Test parsing with custom config path."""
        test_args: List[str] = ["main.py", "--config", "/path/to/config.json"]
        with patch.object(sys, "argv", test_args):
            args: Any = parse_arguments()
            
            assert args.config == "/path/to/config.json"
            assert args.verbose is False

    def test_verbose_flag(self) -> None:
        """Test parsing with verbose flag."""
        test_args: List[str] = ["main.py", "--verbose"]
        with patch.object(sys, "argv", test_args):
            args: Any = parse_arguments()
            
            assert args.verbose is True

    def test_custom_port(self) -> None:
        """Test parsing with custom port."""
        test_args: List[str] = ["main.py", "--port", "9090"]
        with patch.object(sys, "argv", test_args):
            args: Any = parse_arguments()
            
            assert args.port == 9090

    def test_custom_host(self) -> None:
        """Test parsing with custom host."""
        test_args: List[str] = ["main.py", "--host", "0.0.0.0"]
        with patch.object(sys, "argv", test_args):
            args: Any = parse_arguments()
            
            assert args.host == "0.0.0.0"

    def test_debug_flag(self) -> None:
        """Test parsing with debug flag."""
        test_args: List[str] = ["main.py", "--debug"]
        with patch.object(sys, "argv", test_args):
            args: Any = parse_arguments()
            
            assert args.debug is True

    def test_all_arguments(self) -> None:
        """Test parsing with all arguments."""
        test_args: List[str] = [
            "main.py",
            "--config", "/path/to/config.json",
            "--verbose",
            "--port", "9090",
            "--host", "0.0.0.0",
            "--debug",
        ]
        with patch.object(sys, "argv", test_args):
            args: Any = parse_arguments()
            
            assert args.config == "/path/to/config.json"
            assert args.verbose is True
            assert args.port == 9090
            assert args.host == "0.0.0.0"
            assert args.debug is True

    def test_invalid_port(self) -> None:
        """Test parsing with invalid port raises error."""
        test_args: List[str] = ["main.py", "--port", "invalid"]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(ArgumentError) as exc_info:
                parse_arguments()
            
            assert "port" in str(exc_info.value).lower()

    def test_negative_port(self) -> None:
        """Test parsing with negative port raises error."""
        test_args: List[str] = ["main.py", "--port", "-1"]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(ArgumentError) as exc_info:
                parse_arguments()
            
            assert "port" in str(exc_info.value).lower()

    def test_port_out_of_range(self) -> None:
        """Test parsing with port out of range raises error."""
        test_args: List[str] = ["main.py", "--port", "70000"]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(ArgumentError) as exc_info:
                parse_arguments()
            
            assert "port" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Test: load_configuration
# ---------------------------------------------------------------------------

class TestLoadConfiguration:
    """Tests for the load_configuration function."""

    def test_load_valid_config(self, temp_config_file: Path) -> None:
        """Test loading a valid configuration file."""
        config: Dict[str, Any] = load_configuration(str(temp_config_file))
        
        assert config["app"]["name"] == "test-app"
        assert config["app"]["version"] == "1.0.0"
        assert config["app"]["debug"] is False
        assert config["database"]["url"] == "sqlite:///test.db"
        assert config["logging"]["level"] == "INFO"

    def test_load_config_with_env_overrides(
        self,
        temp_config_file: Path,
        mock_env_vars: Dict[str, str],
    ) -> None:
        """Test loading configuration with environment variable overrides."""
        config: Dict[str, Any] = load_configuration(
            str(temp_config_file),
            env_prefix="APP_",
        )
        
        # Environment variables should override file values
        assert config["app"]["name"] == "test-app-env"
        assert config["app"]["debug"] is True

    def test_load_nonexistent_config(self) -> None:
        """Test loading a nonexistent configuration file raises error."""
        with pytest.raises(ConfigurationError) as exc_info:
            load_configuration("/nonexistent/path/config.json")
        
        assert "not found" in str(exc_info.value).lower()

    def test_load_invalid_json(self, invalid_config_file: Path) -> None:
        """Test loading an invalid JSON configuration raises error."""
        with pytest.raises(ConfigurationError) as exc_info:
            load_configuration(str(invalid_config_file))
        
        assert "invalid" in str(exc_info.value).lower()

    def test_load_empty_config(self) -> None:
        """Test loading an empty configuration file."""
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
        ) as f:
            f.write("{}")
            temp_path: Path = Path(f.name)
        
        try:
            config: Dict[str, Any] = load_configuration(str(temp_path))
            assert config == {}
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_load_config_with_defaults(self) -> None:
        """Test loading configuration with default values."""
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
        ) as f:
            json.dump({"app": {"name": "test"}}, f)
            temp_path: Path = Path(f.name)
        
        try:
            config: Dict[str, Any] = load_configuration(
                str(temp_path),
                defaults={"app": {"port": 8080, "host": "localhost"}},
            )
            
            assert config["app"]["name"] == "test"
            assert config["app"]["port"] == 8080
            assert config["app"]["host"] == "localhost"
        finally:
            if temp_path.exists():
                temp_path.unlink()


# ---------------------------------------------------------------------------
# Test: validate_configuration
# ---------------------------------------------------------------------------

class TestValidateConfiguration:
    """Tests for the validate_configuration function."""

    def test_valid_configuration(self) -> None:
        """Test validating a valid configuration."""
        config: Dict[str, Any] = {
            "app": {
                "name": "test-app",
                "version": "1.0.0",
                "debug": False,
                "host": "localhost",
                "port": 8080,
            },
            "database": {
                "url": "sqlite:///test.db",
            },
        }
        
        # Should not raise any exception
        validate_configuration(config)

    def test_missing_required_field(self) -> None:
        """Test validation with missing required field."""
        config: Dict[str, Any] = {
            "app": {
                "name": "test-app",
            },
        }
        
        with pytest.raises(ConfigurationError) as exc_info:
            validate_configuration(config)
        
        assert "missing" in str(exc_info.value).lower()

    def test_invalid_field_type(self) -> None:
        """Test validation with invalid field type."""
        config: Dict[str, Any] = {
            "app": {
                "name": "test-app",
                "version": "1.0.0",
                "debug": "not-a-boolean",
                "host": "localhost",
                "port": 8080,
            },
        }
        
        with pytest.raises(ConfigurationError) as exc_info:
            validate_configuration(config)
        
        assert "invalid" in str(exc_info.value).lower()

    def test_empty_configuration(self) -> None:
        """Test validation with empty configuration."""
        with pytest.raises(ConfigurationError) as exc_info:
            validate_configuration({})
        
        assert "empty" in str(exc_info.value).lower()

    def test_configuration_with_extra_fields(self) -> None:
        """Test validation with extra fields (should be allowed)."""
        config: Dict[str, Any] = {
            "app": {
                "name": "test-app",
                "version": "1.0.0",
                "debug": False,
                "host": "localhost",
                "port": 8080,
            },
            "extra_field": "should be allowed",
        }
        
        # Should not raise any exception
        validate_configuration(config)


# ---------------------------------------------------------------------------
# Test: create_app
# ---------------------------------------------------------------------------

class TestCreateApp:
    """Tests for the create_app function."""

    def test_create_app_with_valid_config(self) -> None:
        """Test creating an app with valid configuration."""
        config: Dict[str, Any] = {
            "app": {
                "name": "test-app",
                "version": "1.0.0",
                "debug": False,
                "host": "localhost",
                "port": 8080,
            },
        }
        
        app: Any = create_app(config)
        
        assert app.name == "test-app"
        assert app.version == "1.0.0"
        assert app.debug is False
        assert app.host == "localhost"
        assert app.port == 8080

    def test_create_app_with_overrides(self) -> None:
        """Test creating an app with parameter overrides."""
        config: Dict[str, Any] = {
            "app": {
                "name": "test-app",
                "version": "1.0.0",
                "debug": False,
                "host": "localhost",
                "port": 8080,
            },
        }
        
        app: Any = create_app(
            config,
            host="0.0.0.0",
            port=9090,
            debug=True,
        )
        
        assert app.host == "0.0.0.0"
        assert app.port == 9090
        assert app.debug is True

    def test_create_app_with_invalid_config(self) -> None:
        """Test creating an app with invalid configuration raises error."""
        with pytest.raises(ApplicationError) as exc_info:
            create_app({})
        
        assert "invalid" in str(exc_info.value).lower()

    def test_create_app_initializes_components(self) -> None:
        """Test that create_app initializes all required components."""
        config: Dict[str, Any] = {
            "app": {
                "name": "test-app",
                "version": "1.0.0",
                "debug": False,
                "host": "localhost",
                "port": 8080,
            },
            "database": {
                "url": "sqlite:///test.db",
            },
        }
        
        with patch("src.main.initialize_database") as mock_db_init:
            with patch("src.main.setup_logging") as mock_logging:
                app: Any = create_app(config)
                
                mock_db_init.assert_called_once_with(config["database"])
                mock_logging.assert_called_once_with(config.get("logging", {}))


# ---------------------------------------------------------------------------
# Test: main
# ---------------------------------------------------------------------------

class TestMain:
    """Tests for the main entry point function."""

    def test_main_successful_startup(
        self,
        temp_config_file: Path,
        mock_application: MagicMock,
    ) -> None:
        """Test successful application startup."""
        test_args: List[str] = [
            "main.py",
            "--config", str(temp_config_file),
        ]
        
        with patch.object(sys, "argv", test_args):
            with patch("src.main.parse_arguments") as mock_parse:
                with patch("src.main.load_configuration") as mock_load:
                    with patch("src.main.validate_configuration") as mock_validate:
                        with patch("src.main.create_app", return_value=mock_application):
                            with patch.object(mock_application, "run") as mock_run:
                                mock_parse.return_value = MagicMock(
                                    config=str(temp_config_file),
                                    verbose=False,
                                    port=None,
                                    host=None,
                                    debug=False,
                                )
                                mock_load.return_value = {
                                    "app": {
                                        "name": "test-app",
                                        "version": "1.0.0",
                                        "debug": False,
                                        "host": "localhost",
                                        "port": 8080,
                                    },
                                }
                                
                                main()
                                
                                mock_parse.assert_called_once()
                                mock_load.assert_called_once_with(str(temp_config_file))
                                mock_validate.assert_called_once()
                                mock_run.assert_called_once()

    def test_main_with_command_line_overrides(
        self,
        temp_config_file: Path,
        mock_application: MagicMock,
    ) -> None:
        """Test main with command line argument overrides."""
        test_args: List[str] = [
            "main.py",
            "--config", str(temp_config_file),
            "--port", "9090",
            "--host", "0.0.0.0",
            "--debug",
            "--verbose",
        ]
        
        with patch.object(sys, "argv", test_args):
            with patch("src.main.parse_arguments") as mock_parse:
                with patch("src.main.load_configuration") as mock_load:
                    with patch("src.main.validate_configuration"):
                        with patch("src.main.create_app", return_value=mock_application):
                            with patch.object(mock_application, "run"):
                                mock_parse.return_value = MagicMock(
                                    config=str(temp_config_file),
                                    verbose=True,
                                    port=9090,
                                    host="0.0.0.0",
                                    debug=True,
                                )
                                mock_load.return_value = {
                                    "app": {
                                        "name": "test-app",
                                        "version": "1.0.0",
                                        "debug": False,
                                        "host": "localhost",
                                        "port": 8080,
                                    },
                                }
                                
                                main()
                                
                                # Verify create_app was called with overrides
                                mock_create_app.assert_called_once()
                                call_kwargs = mock_create_app.call_args[1]
                                assert call_kwargs["port"] == 9090
                                assert call_kwargs["host"] == "0.0.0.0"
                                assert call_kwargs["debug"] is True

    def test_main_configuration_error(self, temp_config_file: Path) -> None:
        """Test main handles configuration errors gracefully."""
        test_args: List[str] = [
            "main.py",
            "--config", str(temp_config_file),
        ]
        
        with patch.object(sys, "argv", test_args):
            with patch(
                "src.main.load_configuration",
                side_effect=ConfigurationError("Invalid configuration"),
            ):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code != 0

    def test_main_argument_error(self) -> None:
        """Test main handles argument errors gracefully."""
        test_args: List[str] = ["main.py", "--port", "invalid"]
        
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            assert exc_info.value.code != 0

    def test_main_application_error(
        self,
        temp_config_file: Path,
    ) -> None:
        """Test main handles application errors gracefully."""
        test_args: List[str] = [
            "main.py",
            "--config", str(temp_config_file),
        ]
        
        with patch.object(sys, "argv", test_args):
            with patch("src.main.parse_arguments") as mock_parse:
                with patch("src.main.load_configuration") as mock_load:
                    with patch("src.main.validate_configuration"):
                        with patch(
                            "src.main.create_app",
                            side_effect=ApplicationError("App creation failed"),
                        ):
                            mock_parse.return_value = MagicMock(
                                config=str(temp_config_file),
                                verbose=False,
                                port=None,
                                host=None,
                                debug=False,
                            )
                            mock_load.return_value = {
                                "app": {
                                    "name": "test-app",
                                    "version": "1.0.0",
                                    "debug": False,
                                    "host": "localhost",
                                    "port": 8080,
                                },
                            }
                            
                            with pytest.raises(SystemExit) as exc_info:
                                main()
                            
                            assert exc_info.value.code != 0

    def test_main_without_config_file(self, mock_application: MagicMock) -> None:
        """Test main without a configuration file (uses defaults)."""
        test_args: List[str] = ["main.py"]
        
        with patch.object(sys, "argv", test_args):
            with patch("src.main.parse_arguments") as mock_parse:
                with patch("src.main.load_configuration") as mock_load:
                    with patch("src.main.validate_configuration"):
                        with patch("src.main.create_app", return_value=mock_application):
                            with patch.object(mock_application, "run"):
                                mock_parse.return_value = MagicMock(
                                    config=None,
                                    verbose=False,
                                    port=None,
                                    host=None,
                                    debug=False,
                                )
                                mock_load.return_value = {
                                    "app": {
                                        "name": "default-app",
                                        "version": "1.0.0",
                                        "debug": False,
                                        "host": "localhost",
                                        "port": 8080,
                                    },
                                }
                                
                                main()
                                
                                # Should load default configuration
                                mock_load.assert_called_once_with(None)


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestMainIntegration:
    """Integration tests for the main application."""

    def test_full_startup_flow(self, temp_config_file: Path) -> None:
        """Test the full startup flow end-to-end."""
        test_args: List[str] = [
            "main.py",
            "--config", str(temp_config_file),
        ]
        
        with patch.object(sys, "argv", test_args):
            with patch("src.main.create_app") as mock_create_app:
                mock_app: MagicMock = MagicMock()
                mock_create_app.return_value = mock_app
                
                main()
                
                # Verify the complete flow
                mock_create_app.assert_called_once()
                mock_app.run.assert_called_once()

    def test_startup_with_environment_overrides(
        self,
        temp_config_file: Path,
        mock_env_vars: Dict[str, str],
    ) -> None:
        """Test startup with environment variable overrides."""
        test_args: List[str] = [
            "main.py",
            "--config", str(temp_config_file),
        ]
        
        with patch.object(sys, "argv", test_args):
            with patch("src.main.create_app") as mock_create_app:
                mock_app: MagicMock = MagicMock()
                mock_create_app.return_value = mock_app
                
                main()
                
                # Verify environment variables were considered
                call_args, call_kwargs = mock_create_app.call_args
                config: Dict[str, Any] = call_args[0]
                assert config["app"]["name"] == "test-app-env"

    def test_startup_with_invalid_config_exits(self) -> None:
        """Test that invalid configuration causes exit."""
        test_args: List[str] = ["main.py", "--config", "/nonexistent/config.json"]
        
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            assert exc_info.value.code != 0

    def test_startup_sets_up_logging(self, temp_config_file: Path) -> None:
        """Test that startup sets up logging correctly."""
        test_args: List[str] = [
            "main.py",
            "--config", str(temp_config_file),
            "--verbose",
        ]
        
        with patch.object(sys, "argv", test_args):
            with patch("src.main.setup_logging") as mock_setup_logging:
                with patch("src.main.create_app") as mock_create_app:
                    mock_app: MagicMock = MagicMock()
                    mock_create_app.return_value = mock_app
                    
                    main()
                    
                    # Verify logging was set up with verbose level
                    mock_setup_logging.assert_called_once()
                    call_args = mock_setup_logging.call_args[0][0]
                    assert call_args.get("level") == "DEBUG"  # verbose overrides

    def test_startup_initializes_database(self, temp_config_file: Path) -> None:
        """Test that startup initializes the database."""
        test_args: List[str] = [
            "main.py",
            "--config", str(temp_config_file),
        ]
        
        with patch.object(sys, "argv", test_args):
            with patch("src.main.initialize_database") as mock_init_db:
                with patch("src.main.create_app") as mock_create_app:
                    mock_app: MagicMock = MagicMock()
                    mock_create_app.return_value = mock_app
                    
                    main()
                    
                    # Verify database initialization was called
                    mock_init_db.assert_called_once()


# ---------------------------------------------------------------------------
# Edge Cases and Error Handling
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_main_with_empty_args(self) -> None:
        """Test main with empty arguments list."""
        with patch.object(sys, "argv", ["main.py"]):
            with patch("src.main.create_app") as mock_create_app:
                mock_app: MagicMock = MagicMock()
                mock_create_app.return_value = mock_app
                
                # Should use defaults and not crash
                main()
                
                mock_create_app.assert_called_once()

    def test_main_with_unicode_config_path(self) -> None:
        """Test main with unicode characters in config path."""
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            prefix="测试",
            delete=False,
        ) as f:
            json.dump({"app": {"name": "test"}}, f)
            temp_path: Path = Path(f.name)
        
        try:
            test_args: List[str] = ["main.py", "--config", str(temp_path)]
            
            with patch.object(sys, "argv", test_args):
                with patch("src.main.create_app") as mock_create_app:
                    mock_app: MagicMock = MagicMock()
                    mock_create_app.return_value = mock_app
                    
                    main()
                    
                    mock_create_app.assert_called_once()
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_main_with_very_large_config(self) -> None:
        """Test main with a very large configuration file."""
        large_config: Dict[str, Any] = {
            "app": {
                "name": "test-app",
                "version": "1.0.0",
                "debug": False,
                "host": "localhost",
                "port": 8080,
            },
            "data": {str(i): f"value-{i}" for i in range(10000)},
        }
        
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
        ) as f:
            json.dump(large_config, f)
            temp_path: Path = Path(f.name)
        
        try:
            test_args: List[str] = ["main.py", "--config", str(temp_path)]
            
            with patch.object(sys, "argv", test_args):
                with patch("src.main.create_app") as mock_create_app:
                    mock_app: MagicMock = MagicMock()
                    mock_create_app.return_value = mock_app
                    
                    main()
                    
                    mock_create_app.assert_called_once()
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_main_handles_keyboard_interrupt(self, temp_config_file: Path) -> None:
        """Test main handles keyboard interrupt gracefully."""
        test_args: List[str] = [
            "main.py",
            "--config", str(temp_config_file),
        ]
        
        with patch.object(sys, "argv", test_args):
            with patch("src.main.create_app") as mock_create_app:
                mock_app: MagicMock = MagicMock()
                mock_app.run.side_effect = KeyboardInterrupt()
                mock_create_app.return_value = mock_app
                
                # Should exit gracefully
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code == 0

    def test_main_handles_system_exit(self, temp_config_file: Path) -> None:
        """Test main handles SystemExit from components."""
        test_args: List[str] = [
            "main.py",
            "--config", str(temp_config_file),
        ]
        
        with patch.object(sys, "argv", test_args):
            with patch("src.main.create_app") as mock_create_app:
                mock_app: MagicMock = MagicMock()
                mock_app.run.side_effect = SystemExit(42)
                mock_create_app.return_value = mock_app
                
                # Should propagate the exit code
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code == 42