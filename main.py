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
from app.core.process_manager import ProcessManager

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

    yield

    logger.info("SERVER SHUTDOWN")
    ffmpeg_out_log.write("SERVER IS SHUTTING DOWN. KILLING FFMPEG PROCESS...")

    try:
        logger.debug("Killing ffmpeg...")
        if stream_queue.get_dj_name_queue_list():
            process_manager.current_stream_process.wait(timeout=2)
            process_manager.current_stream_process.kill()
        logger.debug("...done.")
    except Exception as e:
        logger.exception(e)
        # if stream_queue.get_dj_name_queue_list():

    ffmpeg_out_log.write("FFMPEG PROCESS KILLED. GOODBYE!")
    ffmpeg_out_log.close()

    logger.info("For safe measure, killing all running ffmpeg processes...")
    try:
        subprocess.run(["killall", "ffmpeg"], check=True)
        logger.info("Done killing all running ffmpeg processes.")
    except Exception as e:
        logger.info(f"Error trying to kill all ffmpeg processes: {e}")

    process_manager.obs_socket_manager.disconnect()
middleware = [
Middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)
]


app = FastAPI(lifespan=lifespan, middleware=middleware)

stream_queue = StreamQueue()


ffmpeg_out_log = open('ffmpeg.log','w', encoding='utf-8')
logger.info("Starting process manager...")

process_manager = ProcessManager(stream_queue,ffmpeg_out_log) 

register_exception(app)
register_app(app, process_manager)



