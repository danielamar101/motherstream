import threading
import logging


logger = logging.getLogger(__name__)

def register_app(app,process_manager):

    from main import process_manager
    # Start the process queueing thread
    logger.info("Starting process queueing thread")
    queue_thread = threading.Thread(target=process_manager.process_queue, daemon=True)
    queue_thread.start()

    from app.api.rtmp_endpoints import rtmp_blueprint
    from app.api.http_endpoints import http_blueprint

    # this initializes the database connection. TODO: Load this earlier
    from app.db.main import db_blueprint

    app.include_router(rtmp_blueprint)
    app.include_router(http_blueprint)
    app.include_router(db_blueprint)

    # Reload the queue object in the event of server shutdown during stream
    process_manager.stream_queue.persist_queue()




