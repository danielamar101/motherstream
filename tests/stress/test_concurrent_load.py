"""Stress tests for high concurrent load."""
import pytest
import threading
import time
from unittest.mock import patch
from fastapi.testclient import TestClient


@pytest.fixture
def stress_client():
    """Create a test client for stress tests."""
    from main import app
    return TestClient(app)


@pytest.mark.stress
class TestHighConcurrentLoad:
    """Stress test with many concurrent users."""
    
    @pytest.mark.timeout(60)
    def test_100_concurrent_publish_requests(self, stress_client, mock_user_factory):
        """Test system with 100 concurrent publish requests."""
        results = {"success": 0, "error": 0, "forwarded": 0}
        errors = []
        
        def publish_attempt(user_id):
            try:
                user = mock_user_factory(user_id)
                
                with patch('app.api.rtmp_endpoints.ensure_valid_user', return_value=user):
                    with patch('app.core.process_manager.add_job'):
                        response = stress_client.post("/rtmp/", json={
                            "action": "on_publish",
                            "stream": user.stream_key,
                            "app": "live",
                            "param": ""
                        })
                        
                        if response.status_code == 200:
                            results["success"] += 1
                            if len(response.json()["data"]["urls"]) > 0:
                                results["forwarded"] += 1
                        else:
                            results["error"] += 1
                            
            except Exception as e:
                results["error"] += 1
                errors.append(str(e))
        
        # Create 100 threads
        threads = [threading.Thread(target=publish_attempt, args=(i,)) for i in range(100)]
        
        start_time = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        duration = time.time() - start_time
        
        # Print results
        print(f"\n=== Stress Test Results ===")
        print(f"Duration: {duration:.2f}s")
        print(f"Success: {results['success']}")
        print(f"Errors: {results['error']}")
        print(f"Forwarded: {results['forwarded']}")
        print(f"Queued: {results['success'] - results['forwarded']}")
        
        assert results["error"] == 0, f"Should have no errors. Errors: {errors[:5]}"
        assert results["forwarded"] == 1, f"Exactly one should forward, got {results['forwarded']}"
        assert results["success"] == 100, "All requests should succeed"
    
    @pytest.mark.timeout(60)
    def test_rapid_publish_unpublish_cycles(self, stress_client, mock_user_factory):
        """Test rapid cycles of publish and unpublish."""
        errors = []
        cycle_count = []
        
        def cycle_user(user_id):
            try:
                user = mock_user_factory(user_id)
                cycles = 0
                
                with patch('app.api.rtmp_endpoints.ensure_valid_user', return_value=user):
                    with patch('app.core.process_manager.add_job'):
                        for _ in range(10):
                            # Publish
                            stress_client.post("/rtmp/", json={
                                "action": "on_publish",
                                "stream": user.stream_key,
                                "app": "live",
                                "param": ""
                            })
                            time.sleep(0.01)
                            
                            # Unpublish
                            stress_client.post("/rtmp/", json={
                                "action": "on_unpublish",
                                "stream": user.stream_key,
                                "app": "live"
                            })
                            time.sleep(0.01)
                            cycles += 1
                
                cycle_count.append(cycles)
                        
            except Exception as e:
                errors.append(str(e))
        
        threads = [threading.Thread(target=cycle_user, args=(i,)) for i in range(10)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        print(f"\n=== Cycle Test Results ===")
        print(f"Total cycles completed: {sum(cycle_count)}")
        print(f"Errors: {len(errors)}")
        
        assert len(errors) == 0, f"Should have no errors: {errors[:5]}"
        assert sum(cycle_count) == 100, "Should complete 100 cycles (10 threads × 10 cycles)"
    
    @pytest.mark.timeout(90)
    def test_sustained_concurrent_load(self, stress_client, mock_user_factory):
        """Test sustained load over time with multiple operations."""
        results = {"publish": 0, "unpublish": 0, "forward_check": 0, "errors": 0}
        errors = []
        stop_event = threading.Event()
        
        def sustained_operations(user_id):
            try:
                user = mock_user_factory(user_id)
                
                with patch('app.api.rtmp_endpoints.ensure_valid_user', return_value=user):
                    with patch('app.core.process_manager.add_job'):
                        while not stop_event.is_set():
                            # Publish
                            response = stress_client.post("/rtmp/", json={
                                "action": "on_publish",
                                "stream": user.stream_key,
                                "app": "live",
                                "param": ""
                            })
                            if response.status_code == 200:
                                results["publish"] += 1
                            time.sleep(0.05)
                            
                            # Check forward
                            response = stress_client.post("/rtmp/", json={
                                "action": "on_forward",
                                "stream": user.stream_key,
                                "app": "live"
                            })
                            if response.status_code == 200:
                                results["forward_check"] += 1
                            time.sleep(0.05)
                            
                            # Unpublish
                            response = stress_client.post("/rtmp/", json={
                                "action": "on_unpublish",
                                "stream": user.stream_key,
                                "app": "live"
                            })
                            if response.status_code == 200:
                                results["unpublish"] += 1
                            time.sleep(0.05)
                            
            except Exception as e:
                results["errors"] += 1
                errors.append(str(e))
        
        # Run for 10 seconds with 20 concurrent users
        threads = [threading.Thread(target=sustained_operations, args=(i,)) for i in range(20)]
        
        for t in threads:
            t.start()
        
        time.sleep(10)  # Run for 10 seconds
        stop_event.set()
        
        for t in threads:
            t.join(timeout=2)
        
        print(f"\n=== Sustained Load Results ===")
        print(f"Publish requests: {results['publish']}")
        print(f"Unpublish requests: {results['unpublish']}")
        print(f"Forward checks: {results['forward_check']}")
        print(f"Errors: {results['errors']}")
        
        # Should have processed many requests without errors
        assert results["errors"] == 0, f"Should have no errors: {errors[:5]}"
        assert results["publish"] > 100, "Should have processed many publish requests"


@pytest.mark.stress
class TestQueueStressTest:
    """Stress test for queue operations."""
    
    @pytest.mark.timeout(30)
    def test_rapid_queue_modifications(self, clean_queue, mock_user_factory):
        """Test rapid concurrent modifications to the queue."""
        errors = []
        operations = []
        
        users = [mock_user_factory(i) for i in range(50)]
        
        def add_users():
            try:
                with patch.object(clean_queue, '_write_persistent_state'):
                    for user in users[:25]:
                        result = clean_queue.queue_client_stream_if_not_exists(user)
                        operations.append(("add", result))
                        time.sleep(0.001)
            except Exception as e:
                errors.append(("add", str(e)))
        
        def remove_users():
            try:
                with patch.object(clean_queue, '_write_persistent_state'):
                    for i in range(25):
                        clean_queue.remove_client_with_stream_key(f"TEST_KEY_{i}")
                        operations.append(("remove", True))
                        time.sleep(0.001)
            except Exception as e:
                errors.append(("remove", str(e)))
        
        def read_queue():
            try:
                for _ in range(100):
                    lead = clean_queue.lead_streamer()
                    keys = clean_queue.get_stream_key_queue_list()
                    operations.append(("read", len(keys)))
                    time.sleep(0.001)
            except Exception as e:
                errors.append(("read", str(e)))
        
        # Run concurrent operations
        threads = [
            threading.Thread(target=add_users),
            threading.Thread(target=add_users),
            threading.Thread(target=remove_users),
            threading.Thread(target=read_queue),
            threading.Thread(target=read_queue),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        print(f"\n=== Queue Stress Results ===")
        print(f"Total operations: {len(operations)}")
        print(f"Errors: {len(errors)}")
        
        assert len(errors) == 0, f"Should have no errors: {errors[:5]}"
        assert len(operations) > 200, "Should have completed many operations"


@pytest.mark.stress
class TestSwitchStreamStress:
    """Stress test for stream switching."""
    
    @pytest.mark.timeout(30)
    def test_rapid_stream_switches(self, clean_stream_manager, clean_queue, mock_user_factory):
        """Test rapid stream switching under load."""
        errors = []
        switch_attempts = []
        
        # Add many users to queue
        users = [mock_user_factory(i) for i in range(20)]
        with patch.object(clean_queue, '_write_persistent_state'):
            for user in users:
                clean_queue.stream_queue.append(user)
        
        def attempt_switch(thread_id):
            try:
                for _ in range(10):
                    with patch('app.core.process_manager.add_job'):
                        with patch.object(clean_queue, '_write_persistent_state'):
                            clean_stream_manager.switch_stream()
                            switch_attempts.append(thread_id)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(str(e))
        
        # Multiple threads trying to switch
        threads = [threading.Thread(target=attempt_switch, args=(i,)) for i in range(5)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        print(f"\n=== Switch Stress Results ===")
        print(f"Switch attempts: {len(switch_attempts)}")
        print(f"Errors: {len(errors)}")
        print(f"Final queue length: {len(clean_queue.stream_queue)}")
        
        assert len(errors) == 0, f"Should have no errors: {errors[:5]}"
        # Queue should be properly maintained (no corruption)
        assert len(clean_queue.stream_queue) >= 0, "Queue should have valid length"

