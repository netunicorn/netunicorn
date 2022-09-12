import os
import uvicorn
from fastapi import FastAPI, BackgroundTasks

from netunicorn.director.base.resources import get_logger, redis_connection

from .engine import watch_experiment_task

logger = get_logger('netunicorn.director.processor')

app = FastAPI()


@app.get('/health')
async def health_check() -> str:
    await redis_connection.ping()
    return 'OK'


@app.on_event("startup")
async def on_startup():
    await redis_connection.ping()
    logger.info("Processor started, connection to Redis established")


@app.on_event("shutdown")
async def on_shutdown():
    await redis_connection.close()
    logger.info("Processor stopped")


@app.post("/watch_experiment/{experiment_id}", status_code=200)
async def watch_experiment_handler(experiment_id: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(watch_experiment_task, experiment_id)
    return experiment_id


if __name__ == '__main__':
    IP = os.environ.get('NETUNICORN_PROCESSOR_IP', '0.0.0.0')
    PORT = int(os.environ.get('NETUNICORN_PROCESSOR_PORT', '26515'))
    logger.info(f"Starting processor on {IP}:{PORT}")
    uvicorn.run(app, host=IP, port=PORT)
