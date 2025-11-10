"""Unit tests for StreamQueue class."""
import pytest
import threading
import time
from unittest.mock import Mock, patch
from app.core.queue import StreamQueue


@pytest.mark.unit
class TestQueueClientStreamIfNotExists:
    """Test the atomic add-if-not-exists operation."""
    
    def test_adds_new_user(self, clean_queue, mock_user):
        """Should add user if not in queue."""
        with patch.object(clean_queue, '_write_persistent_state'):
            result = clean_queue.queue_client_stream_if_not_exists(mock_user)
        
        assert result is True
        assert len(clean_queue.stream_queue) == 1
        assert clean_queue.stream_queue[0] == mock_user
    
    def test_rejects_duplicate_user(self, clean_queue, mock_user):
        """Should reject user if already in queue."""
        with patch.object(clean_queue, '_write_persistent_state'):
            clean_queue.queue_client_stream_if_not_exists(mock_user)
            result = clean_queue.queue_client_stream_if_not_exists(mock_user)
        
        assert result is False
        assert len(clean_queue.stream_queue) == 1
    
    @pytest.mark.timeout(5)
    def test_concurrent_adds_no_duplicates(self, clean_queue, mock_user):
        """Multiple threads trying to add same user should result in one entry."""
        results = []
        
        def add_user():
            with patch.object(clean_queue, '_write_persistent_state'):
                result = clean_queue.queue_client_stream_if_not_exists(mock_user)
                results.append(result)
        
        threads = [threading.Thread(target=add_user) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Exactly one thread should succeed
        assert sum(results) == 1, f"Expected 1 success, got {sum(results)}"
        assert len(clean_queue.stream_queue) == 1
    
    @pytest.mark.timeout(5)
    def test_concurrent_different_users(self, clean_queue, mock_user_factory):
        """Multiple threads adding different users should all succeed."""
        results = []
        users = [mock_user_factory(i) for i in range(5)]
        
        def add_user(user):
            with patch.object(clean_queue, '_write_persistent_state'):
                result = clean_queue.queue_client_stream_if_not_exists(user)
                results.append(result)
        
        threads = [threading.Thread(target=add_user, args=(user,)) for user in users]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert sum(results) == 5, "All 5 users should be added"
        assert len(clean_queue.stream_queue) == 5


@pytest.mark.unit
class TestRemoveClientWithStreamKey:
    """Test thread-safe removal."""
    
    def test_removes_existing_user(self, clean_queue, mock_user):
        """Should remove user from queue."""
        with patch.object(clean_queue, '_write_persistent_state'):
            clean_queue.stream_queue.append(mock_user)
            clean_queue.remove_client_with_stream_key("TEST_KEY_123")
        
        assert len(clean_queue.stream_queue) == 0
    
    def test_handles_nonexistent_user(self, clean_queue):
        """Should handle removal of non-existent user gracefully."""
        with patch.object(clean_queue, '_write_persistent_state'):
            clean_queue.remove_client_with_stream_key("NONEXISTENT")
        
        assert len(clean_queue.stream_queue) == 0
    
    @pytest.mark.timeout(5)
    def test_concurrent_removal_no_error(self, clean_queue, mock_user):
        """Multiple threads removing same user should not cause errors."""
        with patch.object(clean_queue, '_write_persistent_state'):
            clean_queue.stream_queue.append(mock_user)
        
        errors = []
        
        def remove_user():
            try:
                with patch.object(clean_queue, '_write_persistent_state'):
                    clean_queue.remove_client_with_stream_key("TEST_KEY_123")
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=remove_user) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert len(clean_queue.stream_queue) == 0
    
    @pytest.mark.timeout(5)
    def test_remove_from_middle_of_queue(self, clean_queue, mock_user_factory):
        """Should correctly remove user from middle of queue."""
        users = [mock_user_factory(i) for i in range(5)]
        
        with patch.object(clean_queue, '_write_persistent_state'):
            for user in users:
                clean_queue.stream_queue.append(user)
            
            # Remove middle user
            clean_queue.remove_client_with_stream_key("TEST_KEY_2")
        
        assert len(clean_queue.stream_queue) == 4
        remaining_keys = [u.stream_key for u in clean_queue.stream_queue]
        assert "TEST_KEY_2" not in remaining_keys
        assert remaining_keys == ["TEST_KEY_0", "TEST_KEY_1", "TEST_KEY_3", "TEST_KEY_4"]


@pytest.mark.unit
class TestLeadStreamerConcurrency:
    """Test lead_streamer reads during modifications."""
    
    def test_lead_streamer_with_empty_queue(self, clean_queue):
        """lead_streamer should return None for empty queue."""
        result = clean_queue.lead_streamer()
        assert result is None
    
    def test_lead_streamer_with_users(self, clean_queue, mock_user):
        """lead_streamer should return first user's stream key."""
        with patch.object(clean_queue, '_write_persistent_state'):
            clean_queue.stream_queue.append(mock_user)
        
        result = clean_queue.lead_streamer()
        assert result == "TEST_KEY_123"
    
    @pytest.mark.timeout(5)
    def test_lead_streamer_during_modifications(self, clean_queue, mock_user_factory):
        """Reading lead_streamer while queue is being modified should not error."""
        results = []
        errors = []
        
        users = [mock_user_factory(i) for i in range(3)]
        
        with patch.object(clean_queue, '_write_persistent_state'):
            clean_queue.stream_queue.append(users[0])
        
        def read_lead():
            try:
                for _ in range(100):
                    lead = clean_queue.lead_streamer()
                    results.append(lead)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        def modify_queue():
            try:
                with patch.object(clean_queue, '_write_persistent_state'):
                    for i in range(50):
                        clean_queue.queue_client_stream_if_not_exists(users[1])
                        time.sleep(0.001)
                        clean_queue.remove_client_with_stream_key("TEST_KEY_1")
                        time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        t1 = threading.Thread(target=read_lead)
        t2 = threading.Thread(target=modify_queue)
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        assert len(errors) == 0, f"Should not have errors: {errors}"
        assert len(results) == 100
        # All results should be valid (either a stream key or None)
        for r in results:
            assert r is None or isinstance(r, str)


@pytest.mark.unit
class TestCurrentStreamer:
    """Test current_streamer method."""
    
    def test_current_streamer_empty_queue(self, clean_queue):
        """Should return None for empty queue."""
        assert clean_queue.current_streamer() is None
    
    def test_current_streamer_returns_user_object(self, clean_queue, mock_user):
        """Should return the full user object, not just stream key."""
        with patch.object(clean_queue, '_write_persistent_state'):
            clean_queue.stream_queue.append(mock_user)
        
        result = clean_queue.current_streamer()
        assert result == mock_user
        assert result.stream_key == "TEST_KEY_123"


@pytest.mark.unit
class TestUnqueueClientStream:
    """Test unqueue_client_stream method."""
    
    def test_unqueue_removes_and_returns_first_user(self, clean_queue, mock_user_factory):
        """Should remove and return first user in queue."""
        users = [mock_user_factory(i) for i in range(3)]
        
        with patch.object(clean_queue, '_write_persistent_state'):
            for user in users:
                clean_queue.stream_queue.append(user)
            
            result = clean_queue.unqueue_client_stream()
        
        assert result == users[0]
        assert len(clean_queue.stream_queue) == 2
        assert clean_queue.stream_queue[0] == users[1]
    
    @pytest.mark.timeout(5)
    def test_concurrent_unqueue(self, clean_queue, mock_user_factory):
        """Concurrent unqueue calls should safely remove users."""
        users = [mock_user_factory(i) for i in range(10)]
        results = []
        errors = []
        
        with patch.object(clean_queue, '_write_persistent_state'):
            for user in users:
                clean_queue.stream_queue.append(user)
        
        def unqueue():
            try:
                with patch.object(clean_queue, '_write_persistent_state'):
                    if clean_queue.stream_queue:
                        user = clean_queue.unqueue_client_stream()
                        results.append(user)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=unqueue) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        # Should have dequeued all users
        assert len(results) <= 10  # May be less if some threads found empty queue
        assert len(clean_queue.stream_queue) == 0


@pytest.mark.unit
class TestGetStreamKeyQueueList:
    """Test get_stream_key_queue_list method."""
    
    def test_returns_list_of_stream_keys(self, clean_queue, mock_user_factory):
        """Should return list of all stream keys in order."""
        users = [mock_user_factory(i) for i in range(3)]
        
        with patch.object(clean_queue, '_write_persistent_state'):
            for user in users:
                clean_queue.stream_queue.append(user)
        
        result = clean_queue.get_stream_key_queue_list()
        assert result == ["TEST_KEY_0", "TEST_KEY_1", "TEST_KEY_2"]
    
    @pytest.mark.timeout(5)
    def test_concurrent_reads_are_safe(self, clean_queue, mock_user_factory):
        """Multiple concurrent reads should not cause errors."""
        users = [mock_user_factory(i) for i in range(5)]
        results = []
        errors = []
        
        with patch.object(clean_queue, '_write_persistent_state'):
            for user in users:
                clean_queue.stream_queue.append(user)
        
        def read_list():
            try:
                for _ in range(50):
                    result = clean_queue.get_stream_key_queue_list()
                    results.append(len(result))
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=read_list) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert len(results) == 250  # 5 threads * 50 reads each

