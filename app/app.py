import threading
import logging
from fastapi.middleware.cors import CORSMiddleware 



logger = logging.getLogger(__name__)

def register_app(app,process_manager):

    from main import process_manager
    # Start the process queueing thread
    logger.info("Starting process queueing thread")
    queue_thread = threading.Thread(target=process_manager.process_queue, daemon=True)
    queue_thread.start()

    from app.api.shazam import recognize_song_full
    logger.info("Starting song recognition thread")
    recognize_song_full()

    from app.api.rtmp_endpoints import rtmp_blueprint
    from app.api.http_endpoints import http_blueprint

    # this initializes the database connection. TODO: Load this earlier
    from app.db.routes.login import login_router
    from app.db.routes.users import user_router
    from app.db.routes.utils import util_router


    app.include_router(rtmp_blueprint)
    app.include_router(http_blueprint)

    app.include_router(login_router)
    app.include_router(user_router)
    app.include_router(util_router)






