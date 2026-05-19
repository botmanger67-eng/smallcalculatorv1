"""
Tests package initialization module.

This module provides common test utilities, fixtures, and configuration
for the test suite. It ensures proper test discovery and shared resources.
"""

import os
import sys
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from dotenv import load_dotenv

# Configure test logging
logging.basicConfig(
    level=logging.DEBUG if os.getenv("TEST_DEBUG") else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

# Load test environment variables
_test_env_path: Optional[Path] = None
try:
    _test_env_path = Path(__file__).parent.parent / ".env.test"
    if _test_env_path.exists():
        load_dotenv(dotenv_path=_test_env_path, override=True)
        logger.info(f"Loaded test environment from {_test_env_path}")
    else:
        logger.warning(f"Test environment file not found at {_test_env_path}")
except Exception as e:
    logger.error(f"Failed to load test environment: {e}")

# Add project root to Python path for imports
_project_root: Path = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
    logger.debug(f"Added project root to sys.path: {_project_root}")

# Test configuration constants
TEST_CONFIG: Dict[str, Any] = {
    "timeout": int(os.getenv("TEST_TIMEOUT", "30")),
    "retry_count": int(os.getenv("TEST_RETRY_COUNT", "3")),
    "parallel_execution": os.getenv("TEST_PARALLEL", "false").lower() == "true",
    "coverage_enabled": os.getenv("TEST_COVERAGE", "true").lower() == "true",
    "log_level": os.getenv("TEST_LOG_LEVEL", "INFO"),
    "data_dir": str(_project_root / "tests" / "test_data"),
    "fixtures_dir": str(_project_root / "tests" / "fixtures"),
}

# Validate test directories
_test_data_dir: Path = Path(TEST_CONFIG["data_dir"])
_fixtures_dir: Path = Path(TEST_CONFIG["fixtures_dir"])

for _dir in [_test_data_dir, _fixtures_dir]:
    if not _dir.exists():
        try:
            _dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created test directory: {_dir}")
        except Exception as e:
            logger.error(f"Failed to create test directory {_dir}: {e}")

# Common test markers
TEST_MARKERS: Dict[str, str] = {
    "unit": "Unit tests for individual components",
    "integration": "Integration tests for component interactions",
    "e2e": "End-to-end tests for complete workflows",
    "slow": "Tests that take longer than average to execute",
    "network": "Tests that require network access",
    "database": "Tests that require database access",
    "smoke": "Quick smoke tests for basic functionality",
    "regression": "Regression tests for bug fixes",
}

# Test data generators
class TestDataGenerator:
    """Utility class for generating test data."""

    @staticmethod
    def generate_unique_id(prefix: str = "test") -> str:
        """Generate a unique test identifier."""
        import uuid
        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    @staticmethod
    def generate_test_file(
        directory: Path,
        filename: str,
        content: str = "",
        extension: str = ".txt"
    ) -> Path:
        """Generate a test file with specified content."""
        file_path: Path = directory / f"{filename}{extension}"
        try:
            file_path.write_text(content, encoding="utf-8")
            logger.debug(f"Generated test file: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Failed to generate test file {file_path}: {e}")
            raise

# Test resource manager
class TestResourceManager:
    """Manages test resources and cleanup."""

    _resources: List[Path] = []

    @classmethod
    def register_resource(cls, path: Path) -> None:
        """Register a resource for cleanup."""
        cls._resources.append(path)
        logger.debug(f"Registered test resource: {path}")

    @classmethod
    def cleanup_resources(cls) -> None:
        """Clean up all registered resources."""
        for resource in cls._resources:
            try:
                if resource.exists():
                    if resource.is_file():
                        resource.unlink()
                    elif resource.is_dir():
                        import shutil
                        shutil.rmtree(resource)
                    logger.debug(f"Cleaned up test resource: {resource}")
            except Exception as e:
                logger.error(f"Failed to clean up resource {resource}: {e}")
        cls._resources.clear()

    @classmethod
    def get_resource_count(cls) -> int:
        """Get the number of registered resources."""
        return len(cls._resources)

# Export commonly used items
__all__: List[str] = [
    "TEST_CONFIG",
    "TEST_MARKERS",
    "TestDataGenerator",
    "TestResourceManager",
    "logger",
]

# Initialize test environment
def initialize_test_environment() -> bool:
    """
    Initialize the test environment.

    Returns:
        bool: True if initialization was successful, False otherwise.
    """
    try:
        logger.info("Initializing test environment...")
        logger.debug(f"Test configuration: {TEST_CONFIG}")
        logger.debug(f"Test markers available: {list(TEST_MARKERS.keys())}")
        logger.info("Test environment initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize test environment: {e}")
        return False

# Perform initialization on import
_initialization_success: bool = initialize_test_environment()
if not _initialization_success:
    logger.warning("Test environment initialization had issues")

# Cleanup handler for test resources
import atexit
atexit.register(TestResourceManager.cleanup_resources)