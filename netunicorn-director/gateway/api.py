"""
Small fast Executor API that goes to state holder (Redis) and returns to executors pipelines, events, or stores results
"""
import os
import logging
from typing import Optional
from base64 import b64encode, b64decode

import redis.asyncio as redis

from fastapi import FastAPI, Response

from unicorn.director.gateway.api_types import PipelineResult

_name = 'netunicorn.director.gateway'
logger = logging.getLogger(_name)
logger.addHandler(logging.FileHandler(f'{_name}.log'))
logger.setLevel(logging.INFO)

app = FastAPI()

GATEWAY_IP = os.environ.get('PINOT_GATEWAY_IP', '0.0.0.0')
GATEWAY_PORT = int(os.environ.get('PINOT_GATEWAY_PORT', '26512'))
logger.info(f"Starting gateway on {GATEWAY_IP}, {GATEWAY_PORT}")

REDIS_IP = os.environ.get('PINOT_REDIS_IP', '127.0.0.1')
REDIS_PORT = int(os.environ.get('PINOT_REDIS_PORT', '6379'))
logger.info(f"Connecting to Redis on {REDIS_IP}:{REDIS_PORT}")
redis_connection = redis.Redis(host=REDIS_IP, port=REDIS_PORT, db=0)


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
