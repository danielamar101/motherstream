
import logging

class HealthCheckFilter(logging.Filter):
    def filter(self, record):
        return '/queue-list' not in record.getMessage()
    

class FFmpegLogFilter(logging.Filter):
    def filter(self, record):
        # Check if the log message contains '/ffmpeg.log'
        return '/ffmpeg.log' not in record.getMessage()