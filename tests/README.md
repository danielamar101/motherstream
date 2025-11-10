# Motherstream Test Suite

Comprehensive test suite for the Motherstream application with focus on concurrency, race conditions, and thread safety.

## 📁 Test Structure

```
tests/
├── unit/                       # Unit tests for individual components
│   ├── test_locks.py          # Lock behavior and reentrant tests
│   ├── test_queue.py          # StreamQueue class tests
│   └── test_process_manager.py # StreamManager class tests
├── integration/                # Integration tests for combined components
│   └── test_rtmp_endpoints.py # RTMP endpoint race condition tests
├── stress/                     # High-load stress tests
│   └── test_concurrent_load.py # Concurrent load and stress tests
├── e2e/                        # End-to-end tests with real RTMP streams
│   ├── motherstream-stress-test.sh  # Main E2E stress test script
│   ├── quick-test.sh           # Fast setup verification
│   ├── scripts/                # Helper scripts
│   │   └── download-test-video.sh
│   ├── videos/                 # Test video files
│   └── logs/                   # Test results and logs
└── conftest.py                # Shared fixtures and configuration
```

## 🚀 Running Tests

### Install Dependencies

First, compile and install test dependencies:

```bash
pip-compile requirements.in
pip install -r requirements.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Stress tests only (takes longer)
pytest -m stress --timeout=120

# Run without stress tests
pytest -m "not stress"

# E2E tests (real RTMP streams)
cd e2e
./motherstream-stress-test.sh simultaneous
```

### Run Specific Test Files

```bash
# Lock tests
pytest tests/unit/test_locks.py

# Queue tests
pytest tests/unit/test_queue.py

# Process manager tests
pytest tests/unit/test_process_manager.py

# RTMP endpoints
pytest tests/integration/test_rtmp_endpoints.py

# Stress tests
pytest tests/stress/test_concurrent_load.py
```

### Run with Coverage

```bash
# Generate coverage report
pytest --cov=app --cov-report=html

# View coverage report
open htmlcov/index.html  # On macOS
xdg-open htmlcov/index.html  # On Linux
```

### Run Tests in Parallel

```bash
# Use all available cores
pytest -n auto

# Use specific number of cores
pytest -n 4
```

### Run with Verbose Output

```bash
pytest -vv
```

### Stop on First Failure

```bash
pytest -x
```

## 🎯 Test Categories

### Unit Tests (`@pytest.mark.unit`) - Python/pytest

Test individual components in isolation:
- Lock behavior (reentrant, mutual exclusion)
- StreamQueue operations (add, remove, read)
- StreamManager state management
- Atomic operations

**Expected Coverage**: 85%+

### Integration Tests (`@pytest.mark.integration`) - Python/pytest

Test components working together:
- Concurrent RTMP endpoint calls
- Publish/unpublish flows
- Stream switching scenarios
- Blocking mechanism

**Expected Coverage**: All critical race condition paths

### Stress Tests (`@pytest.mark.stress`) - Python/pytest

Test system under high load:
- 100+ concurrent requests
- Rapid publish/unpublish cycles
- Sustained load over time
- Queue stress testing

**Note**: Stress tests take longer and are marked with longer timeouts.

### E2E Tests - Bash/RTMP Streams

Test the complete system with **real RTMP video streams**:

- Simultaneous connections (all users at once)
- Orderly queue rotation (sequential 1-min streams)
- Chaos mode (random timings and reconnects)
- Rapid disconnect/reconnect cycles
- Queue drain (build up, then empty)

**Setup & Run:**

```bash
cd e2e

# Download test video (first time only)
./scripts/download-test-video.sh

# Quick test (30 seconds)
./quick-test.sh

# Full test suite (15-20 minutes)
./motherstream-stress-test.sh all
```

**See:** `e2e/README.md` for complete documentation

**Expected Coverage**: Real-world validation of all race condition fixes

## 🔍 Test Markers

Tests are marked with pytest markers for easy filtering:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.stress` - Stress tests (slow)
- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.timeout(N)` - Test timeout in seconds

## 📊 Expected Results

### Success Criteria

- ✅ All tests pass consistently
- ✅ No deadlocks (all tests complete within timeout)
- ✅ No race conditions (consistent results across runs)
- ✅ High code coverage (85%+ for critical paths)
- ✅ Stress tests complete without errors

### Key Metrics

1. **No Deadlocks**: All tests complete within timeout
2. **Consistent Results**: Same test run multiple times gives same result
3. **Error-Free**: No exceptions or crashes
4. **Performance**: Stress tests complete in reasonable time

## 🐛 Debugging Failed Tests

### Verbose Output

```bash
pytest -vv tests/unit/test_locks.py::TestQueueLockReentrancy::test_queue_lock_is_reentrant
```

### Show Print Statements

```bash
pytest -s
```

### Run with Python Debugger

```bash
pytest --pdb
```

### Show Slow Tests

```bash
pytest --durations=10
```

## 📈 Continuous Integration

Add to CI/CD pipeline:

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Run unit tests
        run: pytest -m unit --cov=app
      - name: Run integration tests
        run: pytest -m integration
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## 🔒 Testing Race Conditions

The test suite specifically targets race conditions that were fixed:

1. **File I/O inside locks** - Tests verify locks are released before I/O
2. **Duplicate queue entries** - Tests verify atomic add-if-not-exists
3. **Concurrent switch_stream** - Tests verify non-reentrant switching
4. **Stale reads** - Tests verify consistent queue state during modifications
5. **Double-start race** - Tests verify only one user starts when queue empty

## 📝 Writing New Tests

### Test Template

```python
import pytest
from unittest.mock import Mock, patch

@pytest.mark.unit
class TestNewFeature:
    \"\"\"Test description.\"\"\"
    
    def test_basic_functionality(self, clean_queue, mock_user):
        \"\"\"Test basic case.\"\"\"
        # Arrange
        # Act
        # Assert
        pass
    
    @pytest.mark.timeout(5)
    def test_concurrent_access(self, clean_queue, mock_user_factory):
        \"\"\"Test concurrent access.\"\"\"
        # Test with multiple threads
        pass
```

### Use Fixtures

- `clean_queue` - Fresh StreamQueue instance
- `clean_stream_manager` - Fresh StreamManager instance
- `mock_user` - Single mock user
- `mock_user_factory` - Factory for creating multiple users
- `test_client` - FastAPI test client

## 🎓 Best Practices

1. **Isolate tests** - Each test should be independent
2. **Use timeouts** - Prevent hanging tests
3. **Mock I/O** - Mock file I/O and network calls
4. **Test concurrency** - Use threading for race condition tests
5. **Clean up** - Use fixtures for setup/teardown
6. **Be specific** - Test one thing per test
7. **Use descriptive names** - Test name should describe what it tests

## 🚨 Common Issues

### Tests Hang

- Check for deadlocks in code
- Verify `@pytest.mark.timeout()` is set
- Use `pytest --timeout=10` globally

### Flaky Tests

- Usually indicates a race condition
- Add more synchronization
- Increase sleep times in tests

### Import Errors

- Ensure `sys.path` is set correctly in `conftest.py`
- Check that all dependencies are installed

## 📚 Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [Python threading](https://docs.python.org/3/library/threading.html)

