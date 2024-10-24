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


    origins = [
        "http://192.168.1.100:5173", 
        "http://localhost:5173",     
        "http://localhost", 
        "https://always12.duckdns.org/", 
        "http://always12.duckdns.org/"    
    ]

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        # allow_origins=origins,           # Origins that are allowed to make requests
        allow_credentials=True,         # Allow cookies and authorization headers
        allow_methods=["*"],            # Allowed HTTP methods (GET, POST, etc.)
        allow_headers=["*"],            # Allowed HTTP headers
        allow_origins=origins
    )

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

    # Reload the queue object in the event of server shutdown during stream
    process_manager.stream_queue.persist_queue()




