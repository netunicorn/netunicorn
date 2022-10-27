"""
Small fast Executor API that goes to state holder (PostgreSQL) and returns to executors pipelines, events, or stores results
"""
import os
from base64 import b64decode, b64encode
from typing import Optional

import asyncpg
from fastapi import FastAPI, Response
from netunicorn.director.base.resources import (
    DATABASE_DB,
    DATABASE_ENDPOINT,
    DATABASE_PASSWORD,
    DATABASE_USER,
    get_logger,
)

from .api_types import PipelineResult

logger = get_logger("netunicorn.director.gateway")
GATEWAY_IP = os.environ.get("NETUNICORN_GATEWAY_IP", "127.0.0.1")
GATEWAY_PORT = int(os.environ.get("NETUNICORN_GATEWAY_PORT", "26512"))
logger.info(f"Starting gateway on {GATEWAY_IP}:{GATEWAY_PORT}")

app = FastAPI()
db_conn_pool: Optional[asyncpg.Pool] = None


@app.get("/health")
async def health_check() -> str:
    await db_conn_pool.fetchval("SELECT 1")
    return "OK"


@app.on_event("startup")
async def startup():
    global db_conn_pool
    db_conn_pool = await asyncpg.create_pool(
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        database=DATABASE_DB,
        host=DATABASE_ENDPOINT,
    )
    await db_conn_pool.fetchval("SELECT 1")
    logger.info("Gateway started, connection to DB established")


@app.on_event("shutdown")
async def shutdown():
    await db_conn_pool.close()
    logger.info("Gateway stopped")


@app.get("/api/v1/executor/pipeline", status_code=200)
async def return_pipeline(executor_id: str, response: Response) -> Optional[bytes]:
    """
    Returns pipeline for a given executor
    :param executor_id: ID of an executor
    :param response: FastAPI response object
    :return: b64encode(cloudpickle(pipeline))
    """

    pipeline = await db_conn_pool.fetchval(
        "SELECT pipeline::bytea FROM executors WHERE executor_id = $1 LIMIT 1",
        executor_id,
    )
    if pipeline is None:
        logger.warning(
            f"Executor {executor_id} requested pipeline, but it is not found"
        )
        response.status_code = 204
        return

    return b64encode(pipeline)


@app.post("/api/v1/executor/result")
async def receive_result(result: PipelineResult):
    """
    Receives pipeline execution results from executor and stores it in Redis
    """
    pipeline_results = b64decode(result.results)
    await db_conn_pool.execute(
        "UPDATE executors SET result = $1::bytea, finished = TRUE WHERE executor_id = $2",
        pipeline_results,
        result.executor_id,
    )


# TODO: https://stackoverflow.com/questions/63510041/adding-python-logging-to-fastapi-endpoints-hosted-on-docker-doesnt-display-api
