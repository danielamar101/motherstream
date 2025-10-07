
import logging

class HealthCheckFilter(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        # Filter out health check and frequent polling endpoints
        excluded_routes = ['/queue-list', '/timer-data', '/queue-json']
        return not any(route in message for route in excluded_routes)
    

class FFmpegLogFilter(logging.Filter):
    def filter(self, record):
        # Check if the log message contains '/ffmpeg.log'
        return '/ffmpeg.log' not in record.getMessage()