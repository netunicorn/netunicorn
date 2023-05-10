"""
Small fast Executor API that goes to state holder (PostgreSQL) and returns to executors pipelines, events, or stores results
"""
from __future__ import annotations

import os
from base64 import b64decode, b64encode
from typing import Optional

import asyncpg
from fastapi import FastAPI, Response
from netunicorn.base.types import FlagValues, PipelineExecutorState
from netunicorn.director.base.resources import (
    DATABASE_DB,
    DATABASE_ENDPOINT,
    DATABASE_PASSWORD,
    DATABASE_USER,
    get_logger,
)

from .api_types import PipelineResult

logger = get_logger("netunicorn.director.gateway")
GATEWAY_IP = os.environ.get("NETUNICORN_GATEWAY_IP", "0.0.0.0")
GATEWAY_PORT = int(os.environ.get("NETUNICORN_GATEWAY_PORT", "26512"))
logger.info(f"Starting gateway on {GATEWAY_IP}:{GATEWAY_PORT}")

app = FastAPI()
db_conn_pool: asyncpg.Pool


@app.get("/health")
async def health_check() -> str:
    await db_conn_pool.fetchval("SELECT 1")
    return "OK"


@app.on_event("startup")
async def startup() -> None:
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
async def shutdown() -> None:
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
        return None

    return b64encode(pipeline)


@app.post("/api/v1/executor/result")
async def receive_result(result: PipelineResult) -> None:
    """
    Receives pipeline execution results from executor and stores it in database
    """
    pipeline_results = b64decode(result.results)
    state = (
        result.state
        if result.state is not None
        else PipelineExecutorState.FINISHED.value
    )
    finished = state in {
        PipelineExecutorState.FINISHED.value,
        PipelineExecutorState.REPORTING.value,
    }
    await db_conn_pool.execute(
        "UPDATE executors SET result = $1::bytea, finished = $2, state = $3 WHERE executor_id = $4",
        pipeline_results,
        finished,
        state,
        result.executor_id,
    )


@app.post("/api/v1/executor/heartbeat/{executor_id}")
async def receive_heartbeat(executor_id: str) -> None:
    """
    Receives executor heartbeat and updates it in database
    """
    await db_conn_pool.execute(
        "UPDATE executors SET keepalive = timezone('utc', now()) WHERE executor_id = $1",
        executor_id,
    )


@app.get("/api/v1/experiment/{experiment_id}/flag/{flag_name}")
async def get_flag_value(
    experiment_id: str, flag_name: str, response: Response
) -> FlagValues | None:
    """
    Returns flag values for a given experiment
    """
    flag_value = await db_conn_pool.fetch(
        "SELECT text_value, int_value FROM flags WHERE experiment_id = $1 AND key = $2 LIMIT 1",
        experiment_id,
        flag_name,
    )
    if len(flag_value) == 0:
        response.status_code = 404
        return None

    return FlagValues(
        text_value=flag_value[0]["text_value"],
        int_value=flag_value[0]["int_value"],
    )


@app.post("/api/v1/experiment/{experiment_id}/flag/{flag_name}", status_code=200)
async def set_flag_value(
    experiment_id: str, flag_name: str, flag_value: FlagValues, response: Response
) -> Optional[str]:
    """
    Sets flag values for a given experiment
    """
    if flag_value.text_value is None and flag_value.int_value is None:
        response.status_code = 400
        return "Either text_value or int_value must be set"

    if flag_value.int_value is None:
        flag_value.int_value = 0

    await db_conn_pool.execute(
        "INSERT INTO flags (experiment_id, key, text_value, int_value) VALUES ($1, $2, $3, $4) ON CONFLICT (experiment_id, key) DO UPDATE SET text_value = $3, int_value = $4",
        experiment_id,
        flag_name,
        flag_value.text_value,
        flag_value.int_value,
    )
    return None


@app.post(
    "/api/v1/experiment/{experiment_id}/flag/{flag_name}/increment", status_code=200
)
async def increment_int_flag_value(experiment_id: str, flag_name: str) -> None:
    """
    Increments int flag value for a given experiment
    """
    await db_conn_pool.execute(
        "INSERT INTO flags (experiment_id, key, text_value, int_value) VALUES ($1, $2, NULL, 1) "
        "ON CONFLICT (experiment_id, key) DO UPDATE SET int_value = flags.int_value + 1",
        experiment_id,
        flag_name,
    )


@app.post(
    "/api/v1/experiment/{experiment_id}/flag/{flag_name}/decrement", status_code=200
)
async def decrement_int_flag_value(experiment_id: str, flag_name: str) -> None:
    """
    Decrements int flag value for a given experiment
    """
    await db_conn_pool.execute(
        "INSERT INTO flags (experiment_id, key, text_value, int_value) VALUES ($1, $2, NULL, -1) "
        "ON CONFLICT (experiment_id, key) DO UPDATE SET int_value = flags.int_value - 1",
        experiment_id,
        flag_name,
    )
