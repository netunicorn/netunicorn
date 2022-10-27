import os

import uvicorn
from fastapi import BackgroundTasks, FastAPI
from netunicorn.director.base.resources import get_logger

from .engine import healthcheck, on_shutdown, on_startup, watch_experiment_task

logger = get_logger("netunicorn.director.processor")

app = FastAPI()


@app.get("/health")
async def health_check() -> str:
    await healthcheck()
    return "OK"


@app.on_event("startup")
async def on_startup_handler():
    await on_startup()
    logger.info("Processor started, connection to DB established")


@app.on_event("shutdown")
async def on_shutdown_handler():
    await on_shutdown()
    logger.info("Processor stopped")


@app.post("/watch_experiment/{experiment_id}/{lock}", status_code=200)
async def watch_experiment_handler(
    experiment_id: str, lock: str, background_tasks: BackgroundTasks
):
    background_tasks.add_task(watch_experiment_task, experiment_id, lock)
    return experiment_id


if __name__ == "__main__":
    IP = os.environ.get("NETUNICORN_PROCESSOR_IP", "127.0.0.1")
    PORT = int(os.environ.get("NETUNICORN_PROCESSOR_PORT", "26515"))
    logger.info(f"Starting processor on {IP}:{PORT}")
    uvicorn.run(app, host=IP, port=PORT)
