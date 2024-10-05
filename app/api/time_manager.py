
import time
import logging

logger = logging.getLogger(__name__)


class TimeManager():

    stream_start_time = None
    swap_interval = 15

    def __init__(self):
        self.stream_start_time = time.time() 

    def get_swap_interval(self):
        return self.swap_interval

    # Helper function to check if the swap interval has elapsed
    def has_swap_interval_elapsed(self):
        if self.stream_start_time is None:
            return False
        return (time.time() - self.stream_start_time) >= self.swap_interval
    
    def modify_swap_interval(self, swap_interval):
        try:
            # Attempt to convert to an integer if it's a string
            if isinstance(swap_interval, str):
                swap_interval = int(swap_interval)
            
            if isinstance(swap_interval, int):
                self.swap_interval = swap_interval
                logger.info(f"Changed swap interval to {swap_interval}.")
            else:
                raise ValueError
        except (ValueError, TypeError) as e:
            logger.info(f"Failed to change swap interval. Invalid value given: {swap_interval}. Error: {str(e)}")
            
    def get_remaining_time(self):
        if self.stream_start_time is None:
            return self.swap_interval
        elapsed_time = time.time() - self.stream_start_time
        remaining_time = self.swap_interval - elapsed_time
        return max(0, remaining_time)  # Ensure no negative time