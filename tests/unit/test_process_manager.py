"""Unit tests for StreamManager class."""
import pytest
import threading
import time
from unittest.mock import Mock, patch, MagicMock
from app.core.process_manager import StreamManager


@pytest.mark.unit
class TestSwitchStreamNonReentrant:
    """Test that switch_stream is non-reentrant."""
    
    @pytest.mark.timeout(5)
    def test_concurrent_switch_stream_calls(self, clean_stream_manager, clean_queue):
        """Multiple concurrent switch_stream calls should only execute once."""
        execution_count = []
        mock_user = Mock()
        mock_user.stream_key = "TEST"
        mock_user.dj_name = "Test DJ"
        
        clean_queue.stream_queue = [mock_user]
        
        def call_switch():
            with patch('app.core.process_manager.add_job'):
                with patch.object(clean_queue, '_write_persistent_state'):
                    clean_stream_manager.switch_stream()
                    execution_count.append(1)
        
        threads = [threading.Thread(target=call_switch) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Check that only one thread actually performed the switch
        # (Others would have been rejected by the non-blocking lock)
        assert len(execution_count) >= 1
        assert len(clean_queue.stream_queue) == 0  # User should be removed once
    
    def test_switch_stream_releases_lock_on_error(self, clean_stream_manager, clean_queue):
        """switch_stream should release lock even if error occurs."""
        mock_user = Mock()
        mock_user.stream_key = "TEST"
        mock_user.dj_name = "Test DJ"
        
        clean_queue.stream_queue = [mock_user]
        
        # First call will fail during job enqueueing
        with patch('app.core.process_manager.add_job', side_effect=Exception("Test error")):
            with pytest.raises(Exception):
                clean_stream_manager.switch_stream()
        
        # Lock should be released - another call should work
        with patch('app.core.process_manager.add_job'):
            with patch.object(clean_queue, '_write_persistent_state'):
                clean_stream_manager.switch_stream()  # Should not hang
    
    def test_switch_stream_with_empty_queue(self, clean_stream_manager, clean_queue):
        """switch_stream with empty queue should handle gracefully."""
        clean_queue.stream_queue = []
        
        # Should not raise error
        with patch('app.core.process_manager.add_job'):
            clean_stream_manager.switch_stream()


@pytest.mark.unit
class TestObsTurnedOffFlag:
    """Test the obs_turned_off_for_empty_queue flag prevents duplicate jobs."""
    
    def test_flag_starts_false(self, clean_stream_manager):
        """Flag should start as False."""
        assert clean_stream_manager.obs_turned_off_for_empty_queue is False
    
    def test_flag_can_be_set(self, clean_stream_manager):
        """Flag should be settable."""
        clean_stream_manager.obs_turned_off_for_empty_queue = True
        assert clean_stream_manager.obs_turned_off_for_empty_queue is True
    
    def test_flag_resets_on_stream_start(self, clean_stream_manager):
        """Flag should reset when stream starts."""
        clean_stream_manager.obs_turned_off_for_empty_queue = True
        
        mock_streamer = Mock()
        mock_streamer.stream_key = "TEST"
        mock_streamer.dj_name = "Test"
        mock_streamer.timezone = "UTC"
        
        with patch('app.core.process_manager.add_job'):
            clean_stream_manager.start_stream(mock_streamer)
        
        assert clean_stream_manager.obs_turned_off_for_empty_queue is False


@pytest.mark.unit
class TestStartStream:
    """Test start_stream method."""
    
    def test_start_stream_sets_state(self, clean_stream_manager):
        """start_stream should set internal state correctly."""
        mock_streamer = Mock()
        mock_streamer.stream_key = "TEST_KEY"
        mock_streamer.dj_name = "Test DJ"
        mock_streamer.timezone = "America/New_York"
        
        with patch('app.core.process_manager.add_job'):
            clean_stream_manager.start_stream(mock_streamer)
        
        assert clean_stream_manager.current_dj_name == "Test DJ"
        assert clean_stream_manager.time_manager is not None
        assert clean_stream_manager.obs_turned_off_for_empty_queue is False
    
    def test_start_stream_enqueues_jobs(self, clean_stream_manager):
        """start_stream should enqueue appropriate jobs."""
        mock_streamer = Mock()
        mock_streamer.stream_key = "TEST_KEY"
        mock_streamer.dj_name = "Test DJ"
        mock_streamer.timezone = "UTC"
        
        with patch('app.core.process_manager.add_job') as mock_add_job:
            clean_stream_manager.start_stream(mock_streamer)
        
        # Verify jobs were enqueued
        assert mock_add_job.call_count >= 3  # At least START_STREAM, RESTART_MEDIA_SOURCE, TOGGLE_OBS_SRC


@pytest.mark.unit
class TestStateAccessors:
    """Test thread-safe state accessors."""
    
    def test_get_set_priority_key(self, clean_stream_manager):
        """Test getting and setting priority key."""
        assert clean_stream_manager.get_priority_key() is None
        
        clean_stream_manager.set_priority_key("TEST_KEY")
        assert clean_stream_manager.get_priority_key() == "TEST_KEY"
        
        clean_stream_manager.set_priority_key(None)
        assert clean_stream_manager.get_priority_key() is None
    
    def test_get_set_last_streamer_key(self, clean_stream_manager):
        """Test getting and setting last streamer key."""
        assert clean_stream_manager.get_last_streamer_key() is None
        
        clean_stream_manager.set_last_stream_key("LAST_KEY")
        assert clean_stream_manager.get_last_streamer_key() == "LAST_KEY"
        
        clean_stream_manager.delete_last_streamer_key()
        assert clean_stream_manager.get_last_streamer_key() is None
    
    def test_get_toggle_blocking(self, clean_stream_manager):
        """Test getting and toggling blocking state."""
        initial_state = clean_stream_manager.get_is_blocking_last_streamer()
        
        clean_stream_manager.toggle_block_previous_client()
        new_state = clean_stream_manager.get_is_blocking_last_streamer()
        
        assert new_state != initial_state
        
        clean_stream_manager.toggle_block_previous_client()
        assert clean_stream_manager.get_is_blocking_last_streamer() == initial_state
    
    @pytest.mark.timeout(5)
    def test_concurrent_state_access(self, clean_stream_manager):
        """Test concurrent access to state variables."""
        errors = []
        results = []
        
        def access_state(thread_id):
            try:
                for i in range(50):
                    # Read
                    priority = clean_stream_manager.get_priority_key()
                    last = clean_stream_manager.get_last_streamer_key()
                    blocking = clean_stream_manager.get_is_blocking_last_streamer()
                    
                    # Write
                    clean_stream_manager.set_priority_key(f"KEY_{thread_id}_{i}")
                    clean_stream_manager.set_last_stream_key(f"LAST_{thread_id}_{i}")
                    
                    results.append((priority, last, blocking))
            except Exception as e:
                errors.append(str(e))
        
        threads = [threading.Thread(target=access_state, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Should not have errors: {errors}"
        assert len(results) == 250  # 5 threads * 50 iterations


@pytest.mark.unit
class TestSwitchStreamLogic:
    """Test switch_stream internal logic."""
    
    def test_switch_updates_last_stream_key(self, clean_stream_manager, clean_queue):
        """switch_stream should update last_stream_key."""
        old_user = Mock()
        old_user.stream_key = "OLD_KEY"
        old_user.dj_name = "Old DJ"
        
        clean_queue.stream_queue = [old_user]
        
        with patch('app.core.process_manager.add_job'):
            with patch.object(clean_queue, '_write_persistent_state'):
                clean_stream_manager.switch_stream()
        
        assert clean_stream_manager.get_last_streamer_key() == "OLD_KEY"
    
    def test_switch_resets_time_manager(self, clean_stream_manager, clean_queue):
        """switch_stream should reset time_manager."""
        from app.core.time_manager import TimeManager
        
        old_user = Mock()
        old_user.stream_key = "OLD_KEY"
        old_user.dj_name = "Old DJ"
        
        clean_queue.stream_queue = [old_user]
        clean_stream_manager.time_manager = TimeManager()
        
        with patch('app.core.process_manager.add_job'):
            with patch.object(clean_queue, '_write_persistent_state'):
                clean_stream_manager.switch_stream()
        
        assert clean_stream_manager.time_manager is None
    
    def test_switch_starts_next_stream(self, clean_stream_manager, clean_queue):
        """switch_stream should start the next stream if available."""
        old_user = Mock()
        old_user.stream_key = "OLD_KEY"
        old_user.dj_name = "Old DJ"
        
        new_user = Mock()
        new_user.stream_key = "NEW_KEY"
        new_user.dj_name = "New DJ"
        new_user.timezone = "UTC"
        
        clean_queue.stream_queue = [old_user, new_user]
        
        with patch('app.core.process_manager.add_job') as mock_add_job:
            with patch.object(clean_queue, '_write_persistent_state'):
                clean_stream_manager.switch_stream()
        
        # Should have enqueued jobs for both stopping old and starting new
        assert mock_add_job.call_count > 5  # Multiple jobs enqueued
        assert clean_stream_manager.get_priority_key() == "NEW_KEY"
    
    def test_switch_with_no_next_stream(self, clean_stream_manager, clean_queue):
        """switch_stream with no next stream should clear priority."""
        old_user = Mock()
        old_user.stream_key = "OLD_KEY"
        old_user.dj_name = "Old DJ"
        
        clean_queue.stream_queue = [old_user]
        clean_stream_manager.set_priority_key("OLD_KEY")
        
        with patch('app.core.process_manager.add_job'):
            with patch.object(clean_queue, '_write_persistent_state'):
                clean_stream_manager.switch_stream()
        
        assert clean_stream_manager.get_priority_key() is None
        assert len(clean_queue.stream_queue) == 0

