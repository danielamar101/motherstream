from fastapi import FastAPI
import sentry_sdk

from contextlib import asynccontextmanager
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
import subprocess
import logging
import os

from app.api.exceptions import register_exception
from app.app import register_app
from app.core.queue import StreamQueue
from app.core.process_manager import StreamManager

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    import debugpy
    debug_port: int = os.environ.get('DEBUG_PORT',5555)
    debugpy.listen(("localhost", int(debug_port)))
    logger.debug(f"Debugger listening on port {debug_port}")
except Exception as e:
    logger.exception(e)

SENTRY_DSN = os.environ.get("SENTRY_DSN")
# sentry_sdk.init(
#     dsn=SENTRY_DSN,
#     # Set traces_sample_rate to 1.0 to capture 100%
#     # of transactions for tracing.
#     traces_sample_rate=1.0,
#     # Set profiles_sample_rate to 1.0 to profile 100%
#     # of sampled transactions.
#     # We recommend adjusting this value in production.
#     profiles_sample_rate=1.0,
# )

@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("SERVER STARTUP.")
    # Update stream queue vars upon startup
    yield

    logger.info("SERVER SHUTDOWN")
    process_manager.obs_socket_manager.disconnect()
    
origins = [
    "http://192.168.1.100:5173", 
    "http://localhost:5173",     
    "http://localhost", 
    "https://always12.live/", 
    "https://staging.always12.live/",
    "http://always12.live/",
    "http://staging.always12.live/",
    "http://raspberry:5173/",
    "http://motherstream.xyz",    
    "https://motherstream.xyz",    
    "https://motherstream.live",
    "https://staging.motherstream.live",
    "http://motherstream.live",
    "http://staging.motherstream.live",
    "http://54.164.3.167",
    "http://54.164.3.167:5173",
]
middleware = [ Middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)
]


app = FastAPI(lifespan=lifespan, middleware=middleware)

stream_queue = StreamQueue()

logger.info("Starting process manager...")

process_manager = StreamManager(stream_queue) 

register_exception(app)
register_app(app, process_manager)



