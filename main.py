from fastapi import FastAPI
from contextlib import asynccontextmanager

import subprocess
import logging
import os

from app.api.exceptions import register_exception
from app.app import register_app
from app.queue import StreamQueue
from app.api.process_manager import ProcessManager

logger = logging.getLogger(__name__)

try:
    import debugpy
    debug_port: int = os.environ.get('DEBUG_PORT',5555)
    debugpy.listen(("localhost", int(debug_port)))
    logger.debug(f"Debugger listening on port {debug_port}")
except Exception as e:
    logger.exception(e)



@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("SERVER STARTUP.")

    yield

    logger.info("SERVER SHUTDOWN")
    ffmpeg_out_log.write("SERVER IS SHUTTING DOWN. KILLING FFMPEG PROCESS...")

    try:
        logger.debug("Killing ffmpeg...")
        if stream_queue.get_stream_queue_as_list():
            process_manager.current_stream_process.wait(timeout=2)
        logger.debug("...done.")
    except Exception as e:
        logger.exception(e)
        if stream_queue.get_stream_queue_as_list():
            process_manager.current_stream_process.kill()

    ffmpeg_out_log.write("FFMPEG PROCESS KILLED. GOODBYE!")
    ffmpeg_out_log.close()

    logger.info("For safe measure, killing all running ffmpeg processes...")
    try:
        subprocess.run(["killall", "ffmpeg"], check=True)
        logger.info("Done killing all running ffmpeg processes.")
    except Exception as e:
        logger.info(f"Error trying to kill all ffmpeg processes: {e}")

app = FastAPI(lifespan=lifespan)


stream_queue = StreamQueue()
ffmpeg_out_log = open('ffmpeg.log','w', encoding='utf-8')

logger.info("Starting process manager...")
process_manager = ProcessManager(stream_queue,ffmpeg_out_log) 

register_exception(app)
register_app(app, process_manager)



