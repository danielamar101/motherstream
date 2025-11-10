"""Shared test fixtures and configuration."""
import pytest
import sys
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock database before any imports
sys.modules['app.db.main'] = MagicMock()
sys.modules['app.db.crud'] = MagicMock()
sys.modules['app.db.security'] = MagicMock()
sys.modules['app.db.database'] = MagicMock()


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "stress: Stress tests (slow)")


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances before each test."""
    from app.core.process_manager import StreamManager
    from app.core.queue import StreamQueue
    
    # Store original instances
    original_instances = {}
    for cls in [StreamManager, StreamQueue]:
        if hasattr(cls, '_instances'):
            original_instances[cls] = cls._instances.copy()
    
    yield
    
    # Cleanup after test - restore or clear
    for cls in [StreamManager, StreamQueue]:
        if hasattr(cls, '_instances'):
            if cls in original_instances:
                cls._instances = original_instances[cls]
            else:
                cls._instances.clear()


@pytest.fixture
def mock_db():
    """Mock database for tests."""
    db = Mock()
    yield db


@pytest.fixture
def mock_user():
    """Create a mock user."""
    from app.db.schemas import User
    user = Mock(spec=User)
    user.id = 1
    user.stream_key = "TEST_KEY_123"
    user.dj_name = "Test DJ"
    user.timezone = "UTC"
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_user_factory():
    """Factory for creating multiple mock users."""
    from app.db.schemas import User
    
    def _create_user(user_id: int):
        user = Mock(spec=User)
        user.id = user_id
        user.stream_key = f"TEST_KEY_{user_id}"
        user.dj_name = f"Test DJ {user_id}"
        user.timezone = "UTC"
        user.email = f"test{user_id}@example.com"
        return user
    
    return _create_user


@pytest.fixture
def clean_queue():
    """Create a fresh StreamQueue instance."""
    from app.core.queue import StreamQueue
    
    # Clear singleton instance
    if StreamQueue in StreamQueue._instances:
        del StreamQueue._instances[StreamQueue]
    
    with patch.object(StreamQueue, 'persist_queue'):
        q = StreamQueue()
        q.stream_queue = []
        yield q
        q.clear_queue()


@pytest.fixture
def clean_stream_manager(clean_queue):
    """Create a fresh StreamManager instance with mocked dependencies."""
    from app.core.process_manager import StreamManager
    
    # Clear singleton
    if StreamManager in StreamManager._instances:
        del StreamManager._instances[StreamManager]
    
    with patch('app.core.process_manager.obs_socket_manager_instance'):
        with patch('app.core.process_manager.StreamHealthChecker'):
            manager = StreamManager(clean_queue)
            yield manager

