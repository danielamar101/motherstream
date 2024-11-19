
import time
import logging

logger = logging.getLogger(__name__)

swap_interval = 12000

class TimeManager():
    

    stream_start_time = None

    def __init__(self):
        self.stream_start_time = time.time() 

    def get_swap_interval(self):
        global swap_interval
        return swap_interval
    
    # Helper function to check if the swap interval has elapsed
    def has_swap_interval_elapsed(self):
        if self.stream_start_time is None:
            return False
        return (time.time() - self.stream_start_time) >= swap_interval
    
    def modify_swap_interval(self, interval, reset_time=False):
        try:
            global swap_interval
            swap_interval = int(interval)
            if reset_time:
                self.stream_start_time = time.time()
            logger.info(f"Changed swap interval to {interval}.")
        except (ValueError, TypeError) as e:
            logger.info(f"Failed to change swap interval. Invalid value given: {interval}. Error: {str(e)}")
            
    def get_remaining_time(self):
        global swap_interval
        if self.stream_start_time is None:
            return swap_interval
        elapsed_time = time.time() - self.stream_start_time
        remaining_time = swap_interval - elapsed_time
        return max(0, remaining_time)  # Ensure no negative time