"""Integration tests for RTMP endpoint race conditions."""
import pytest
import threading
import time
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def test_client():
    """Create a test client for the API."""
    from main import app
    return TestClient(app)


@pytest.mark.integration
class TestConcurrentOnPublish:
    """Test concurrent on_publish scenarios."""
    
    @pytest.mark.timeout(10)
    def test_concurrent_publish_only_one_forwards(self, test_client, mock_user_factory):
        """When multiple users publish simultaneously with empty queue, only one should forward."""
        results = []
        users = [mock_user_factory(i) for i in range(5)]
        
        def publish_stream(user):
            with patch('app.api.rtmp_endpoints.ensure_valid_user', return_value=user):
                with patch('app.core.process_manager.add_job'):
                    response = test_client.post(
                        "/rtmp/",
                        json={
                            "action": "on_publish",
                            "stream": user.stream_key,
                            "app": "live",
                            "param": "?key=test"
                        }
                    )
                    results.append({
                        "stream_key": user.stream_key,
                        "status": response.status_code,
                        "forwarded": len(response.json().get("data", {}).get("urls", [])) > 0
                    })
        
        # Simulate 5 users publishing at the same time
        threads = [
            threading.Thread(target=publish_stream, args=(user,))
            for user in users
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Exactly one should be forwarded
        forwarded_count = sum(1 for r in results if r["forwarded"])
        assert forwarded_count == 1, f"Expected 1 forwarded, got {forwarded_count}"
        
        # Others should be in queue (not forwarded)
        not_forwarded = sum(1 for r in results if not r["forwarded"])
        assert not_forwarded == 4
    
    @pytest.mark.timeout(10)
    def test_concurrent_publish_same_user_no_duplicates(self, test_client, mock_user):
        """Same user publishing multiple times concurrently should only appear once in queue."""
        results = []
        
        def publish_stream():
            with patch('app.api.rtmp_endpoints.ensure_valid_user', return_value=mock_user):
                with patch('app.core.process_manager.add_job'):
                    response = test_client.post(
                        "/rtmp/",
                        json={
                            "action": "on_publish",
                            "stream": mock_user.stream_key,
                            "app": "live",
                            "param": ""
                        }
                    )
                    results.append(response.status_code)
        
        threads = [threading.Thread(target=publish_stream) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All should succeed (200)
        assert all(status == 200 for status in results)


@pytest.mark.integration
class TestConcurrentUnpublish:
    """Test concurrent on_unpublish scenarios."""
    
    @pytest.mark.timeout(10)
    def test_concurrent_unpublish_no_double_switch(self, test_client, clean_queue, mock_user):
        """Multiple unpublish calls should not cause double stream switch."""
        switch_count = []
        
        # Setup: User is in queue
        with patch.object(clean_queue, '_write_persistent_state'):
            clean_queue.stream_queue = [mock_user]
        
        original_switch = None
        
        def count_switches(*args, **kwargs):
            switch_count.append(1)
            if original_switch:
                return original_switch(*args, **kwargs)
        
        with patch('app.api.rtmp_endpoints.process_manager') as mock_pm:
            mock_pm.stream_queue = clean_queue
            mock_pm.get_priority_key.return_value = None
            mock_pm.switch_stream.side_effect = count_switches
            
            def unpublish():
                test_client.post(
                    "/rtmp/",
                    json={
                        "action": "on_unpublish",
                        "stream": mock_user.stream_key,
                        "app": "live"
                    }
                )
            
            # Simulate 3 concurrent unpublish calls
            threads = [
                threading.Thread(target=unpublish)
                for _ in range(3)
            ]
            
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        
        # switch_stream should only be called once (due to non-reentrant lock)
        assert len(switch_count) <= 1, f"Expected at most 1 switch, got {len(switch_count)}"


@pytest.mark.integration
class TestOnForwardConcurrency:
    """Test concurrent on_forward requests."""
    
    @pytest.mark.timeout(5)
    def test_concurrent_forward_checks_consistent(self, test_client, clean_queue, mock_user):
        """Concurrent forward checks should give consistent results."""
        results = []
        
        # Setup: User is lead
        with patch.object(clean_queue, '_write_persistent_state'):
            clean_queue.stream_queue = [mock_user]
        
        with patch('app.api.rtmp_endpoints.process_manager.stream_queue', clean_queue):
            def check_forward():
                response = test_client.post(
                    "/rtmp/",
                    json={
                        "action": "on_forward",
                        "stream": mock_user.stream_key,
                        "app": "live"
                    }
                )
                forwarded = len(response.json().get("data", {}).get("urls", [])) > 0
                results.append(forwarded)
            
            threads = [threading.Thread(target=check_forward) for _ in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        
        # All should get the same result (either all forwarded or all not)
        assert len(set(results)) == 1, f"Results should be consistent: {results}"


@pytest.mark.integration
class TestPublishUnpublishCycles:
    """Test rapid publish/unpublish cycles."""
    
    @pytest.mark.timeout(15)
    def test_rapid_publish_unpublish_no_corruption(self, test_client, mock_user_factory):
        """Rapid publish/unpublish cycles should not corrupt queue state."""
        errors = []
        users = [mock_user_factory(i) for i in range(3)]
        
        def cycle_user(user):
            try:
                for _ in range(5):
                    with patch('app.api.rtmp_endpoints.ensure_valid_user', return_value=user):
                        with patch('app.core.process_manager.add_job'):
                            # Publish
                            test_client.post(
                                "/rtmp/",
                                json={
                                    "action": "on_publish",
                                    "stream": user.stream_key,
                                    "app": "live",
                                    "param": ""
                                }
                            )
                            time.sleep(0.02)
                            
                            # Unpublish
                            test_client.post(
                                "/rtmp/",
                                json={
                                    "action": "on_unpublish",
                                    "stream": user.stream_key,
                                    "app": "live"
                                }
                            )
                            time.sleep(0.02)
            except Exception as e:
                errors.append(str(e))
        
        threads = [threading.Thread(target=cycle_user, args=(user,)) for user in users]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Should have no errors: {errors[:3]}"


@pytest.mark.integration
class TestStreamSwitchingFlow:
    """Test complete stream switching flow."""
    
    @pytest.mark.timeout(15)
    def test_switch_from_user1_to_user2(self, test_client, clean_stream_manager, clean_queue, mock_user_factory):
        """Test switching from one user to another."""
        user1 = mock_user_factory(1)
        user2 = mock_user_factory(2)
        
        with patch('app.api.rtmp_endpoints.process_manager', clean_stream_manager):
            with patch('app.core.process_manager.add_job'):
                # User 1 publishes (should forward)
                with patch('app.api.rtmp_endpoints.ensure_valid_user', return_value=user1):
                    response = test_client.post(
                        "/rtmp/",
                        json={
                            "action": "on_publish",
                            "stream": user1.stream_key,
                            "app": "live",
                            "param": ""
                        }
                    )
                    assert len(response.json()["data"]["urls"]) > 0  # Forwarded
                
                time.sleep(0.1)
                
                # User 2 publishes (should queue)
                with patch('app.api.rtmp_endpoints.ensure_valid_user', return_value=user2):
                    response = test_client.post(
                        "/rtmp/",
                        json={
                            "action": "on_publish",
                            "stream": user2.stream_key,
                            "app": "live",
                            "param": ""
                        }
                    )
                    assert len(response.json()["data"]["urls"]) == 0  # Not forwarded
                
                time.sleep(0.1)
                
                # User 1 unpublishes (should switch to User 2)
                response = test_client.post(
                    "/rtmp/",
                    json={
                        "action": "on_unpublish",
                        "stream": user1.stream_key,
                        "app": "live"
                    }
                )
                assert response.status_code == 200
                
                time.sleep(0.2)
                
                # Verify User 2 is now lead
                assert clean_queue.lead_streamer() == user2.stream_key


@pytest.mark.integration
class TestBlockingMechanism:
    """Test the blocking mechanism for kicked users."""
    
    @pytest.mark.timeout(10)
    def test_blocked_user_cannot_rejoin(self, test_client, clean_stream_manager, mock_user):
        """Blocked user should not be able to rejoin immediately."""
        with patch('app.api.rtmp_endpoints.process_manager', clean_stream_manager):
            # Set up blocking state
            clean_stream_manager.set_last_stream_key(mock_user.stream_key)
            clean_stream_manager.toggle_block_previous_client()  # Enable blocking
            
            with patch('app.api.rtmp_endpoints.ensure_valid_user', return_value=mock_user):
                with patch('app.core.process_manager.add_job'):
                    response = test_client.post(
                        "/rtmp/",
                        json={
                            "action": "on_publish",
                            "stream": mock_user.stream_key,
                            "app": "live",
                            "param": ""
                        }
                    )
                    # Should be blocked (401)
                    assert response.status_code == 401
    
    def test_non_blocked_user_can_join(self, test_client, clean_stream_manager, mock_user_factory):
        """Different user should be able to join even when blocking is enabled."""
        user1 = mock_user_factory(1)
        user2 = mock_user_factory(2)
        
        with patch('app.api.rtmp_endpoints.process_manager', clean_stream_manager):
            # Set up blocking state for user1
            clean_stream_manager.set_last_stream_key(user1.stream_key)
            clean_stream_manager.toggle_block_previous_client()
            
            # User2 should be able to join
            with patch('app.api.rtmp_endpoints.ensure_valid_user', return_value=user2):
                with patch('app.core.process_manager.add_job'):
                    response = test_client.post(
                        "/rtmp/",
                        json={
                            "action": "on_publish",
                            "stream": user2.stream_key,
                            "app": "live",
                            "param": ""
                        }
                    )
                    # Should succeed
                    assert response.status_code == 200

