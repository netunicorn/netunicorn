"""
Small fast Executor API that goes to state holder (Redis) and returns to executors pipelines, events, or stores results
"""
import os
from typing import Optional
from base64 import b64encode, b64decode
from fastapi import FastAPI, Response

from netunicorn.director.base.resources import get_logger, redis_connection

from .api_types import PipelineResult

logger = get_logger('netunicorn.director.gateway')
GATEWAY_IP = os.environ.get('NETUNICORN_GATEWAY_IP', '0.0.0.0')
GATEWAY_PORT = int(os.environ.get('NETUNICORN_GATEWAY_PORT', '26512'))
logger.info(f"Starting gateway on {GATEWAY_IP}:{GATEWAY_PORT}")

app = FastAPI()


@app.on_event("startup")
async def startup():
    await redis_connection.ping()
    logger.info("Gateway started, connection to Redis established")


@app.on_event("shutdown")
async def shutdown():
    await redis_connection.close()
    logger.info("Gateway stopped")


@app.get("/api/v1/executor/pipeline", status_code=200)
async def return_pipeline(executor_id: str, response: Response) -> Optional[bytes]:
    """
    Returns pipeline for a given executor
    :param executor_id: ID of an executor
    :param response: FastAPI response object
    :return: b64encode(cloudpickle(pipeline))
    """

    pipeline = await redis_connection.get(f"executor:{executor_id}:pipeline")
    if pipeline is None:
        logger.warning(f"Executor {executor_id} requested pipeline, but it is not found")
        response.status_code = 204
        return

    return b64encode(pipeline)


@app.post("/api/v1/executor/result")
async def receive_result(result: PipelineResult):
    """
    Receives pipeline execution results from executor and stores it in Redis
    """
    pipeline_results = b64decode(result.results)
    await redis_connection.set(f"executor:{result.executor_id}:result", pipeline_results)

# TODO: https://stackoverflow.com/questions/63510041/adding-python-logging-to-fastapi-endpoints-hosted-on-docker-doesnt-display-api
