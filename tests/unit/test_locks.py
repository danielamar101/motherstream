"""Test lock behavior and reentrant properties."""
import pytest
import threading
import time
from app.lock_manager import lock as queue_lock, obs_lock


@pytest.mark.unit
class TestQueueLockReentrancy:
    """Test that queue_lock is properly reentrant."""
    
    def test_queue_lock_is_reentrant(self):
        """Verify queue_lock can be acquired multiple times by same thread."""
        acquired_count = 0
        
        with queue_lock:
            acquired_count += 1
            with queue_lock:  # Should not deadlock
                acquired_count += 1
                with queue_lock:
                    acquired_count += 1
        
        assert acquired_count == 3, "Should acquire lock 3 times"
    
    @pytest.mark.timeout(3)
    def test_queue_lock_blocks_other_threads(self):
        """Verify queue_lock blocks other threads."""
        results = []
        
        def thread_func():
            with queue_lock:
                results.append("thread")
                time.sleep(0.1)
        
        with queue_lock:
            t = threading.Thread(target=thread_func)
            t.start()
            time.sleep(0.05)
            results.append("main")
        
        t.join()
        assert results == ["main", "thread"], "Main should complete before thread"
    
    @pytest.mark.timeout(5)
    def test_nested_acquisition_same_thread(self):
        """Test multiple nested acquisitions in same thread work correctly."""
        results = []
        
        def nested_function():
            with queue_lock:
                results.append("nested")
                return "nested_result"
        
        with queue_lock:
            results.append("outer")
            result = nested_function()
            results.append("after_nested")
        
        assert results == ["outer", "nested", "after_nested"]
        assert result == "nested_result"


@pytest.mark.unit
class TestObsLock:
    """Test OBS lock behavior."""
    
    def test_obs_lock_single_acquisition(self):
        """Verify obs_lock can be acquired."""
        acquired = False
        with obs_lock:
            acquired = True
        assert acquired
    
    @pytest.mark.timeout(2)
    def test_obs_lock_mutual_exclusion(self):
        """Verify obs_lock provides mutual exclusion."""
        counter = {"value": 0}
        
        def increment():
            with obs_lock:
                temp = counter["value"]
                time.sleep(0.01)  # Simulate work
                counter["value"] = temp + 1
        
        threads = [threading.Thread(target=increment) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert counter["value"] == 10, "Counter should be incremented exactly 10 times"


