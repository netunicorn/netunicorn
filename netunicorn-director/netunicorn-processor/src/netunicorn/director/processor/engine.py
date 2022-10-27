import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional

import asyncpg
from netunicorn.base.experiment import (
    DeploymentExecutionResult,
    Experiment,
    ExperimentStatus,
)
from netunicorn.director.base.resources import (
    DATABASE_DB,
    DATABASE_ENDPOINT,
    DATABASE_PASSWORD,
    DATABASE_USER,
    get_logger,
)
from netunicorn.director.base.utils import __init_connection

logger = get_logger("netunicorn.director.processor")
db_conn_pool: Optional[asyncpg.Pool] = None


async def collect_all_executor_results(
    experiment: Experiment, experiment_id: str
) -> None:
    if await db_conn_pool.fetchval(
        "SELECT error FROM experiments WHERE experiment_id = $1", experiment_id
    ):
        # do nothing - already finished with error
        return

    execution_results = []
    for deployment in experiment:
        row = await db_conn_pool.fetchrow(
            "SELECT result::bytea, error FROM executors WHERE experiment_id = $1 AND executor_id = $2",
            experiment_id,
            deployment.executor_id,
        )

        if row is not None:
            executor_result, error = row["result"], row["error"]
        else:
            executor_result, error = None, None

        execution_results.append(
            DeploymentExecutionResult(
                minion=deployment.minion,
                serialized_pipeline=deployment.pipeline,
                result=executor_result,
                error=error,
            )
        )
    await db_conn_pool.execute(
        "UPDATE experiments SET execution_results = $1::jsonb[] WHERE experiment_id = $2",
        execution_results,
        experiment_id,
    )


async def watch_experiment_task(experiment_id: str, lock: str) -> None:
    experiment_data = await db_conn_pool.fetchval(
        "SELECT data::jsonb FROM experiments WHERE experiment_id = $1", experiment_id
    )
    if experiment_data is None:
        logger.error(f"Experiment {experiment_id} not found.")
        return

    experiment: Experiment = Experiment.from_json(experiment_data)
    timeout_minutes = experiment.keep_alive_timeout_minutes
    start_time = datetime.utcnow()

    try:
        status = ExperimentStatus(
            await db_conn_pool.fetchval(
                "SELECT status FROM experiments WHERE experiment_id = $1", experiment_id
            )
        )
    except ValueError:
        logger.error(f"Unknown status for experiment {experiment_id}")
        return

    while status == ExperimentStatus.READY:
        # haven't started yet, waiting
        await asyncio.sleep(5)
        logger.debug(f"Experiment {experiment_id} is still not running, waiting")
        status = ExperimentStatus(
            await db_conn_pool.fetchval(
                "SELECT status FROM experiments WHERE experiment_id = $1", experiment_id
            )
        )
        if datetime.utcnow() > start_time + timedelta(minutes=timeout_minutes):
            exc = f"Experiment {experiment_id} timeout reached and still not started."
            logger.error(exc)
            await db_conn_pool.execute(
                "UPDATE experiments SET status = $1, error = $2 WHERE experiment_id = $3",
                ExperimentStatus.FINISHED.value,
                exc,
                experiment_id,
            )
            return

    if status != ExperimentStatus.RUNNING:
        logger.error(f"Experiment {experiment_id} is in unexpected status {status}")
        return

    logger.debug(
        f"Experiment {experiment_id} started at {start_time}, keep alive timeout: {timeout_minutes} minutes"
    )
    # executor_id: finished_flag
    executor_status: Dict[str, bool] = {
        x.executor_id: not x.prepared for x in experiment
    }
    logger.debug(f"Executors finished: {executor_status}")

    while True:
        logger.debug(f"New cycle iteration for experiment {experiment_id}")
        status = ExperimentStatus(
            await db_conn_pool.fetchval(
                "SELECT status FROM experiments WHERE experiment_id = $1", experiment_id
            )
        )
        if status == ExperimentStatus.FINISHED:
            logger.warning(
                f"Unexpected status FINISHED for experiment {experiment_id}."
            )
            break

        if status != ExperimentStatus.RUNNING:
            exception = f"Experiment {experiment_id} is in unexpected status {status}. "
            await db_conn_pool.execute(
                "UPDATE experiments SET error = $1 WHERE experiment_id = $2",
                ExperimentStatus.FINISHED.value,
                exception,
                experiment_id,
            )
            break

        for executor_id, finished in executor_status.items():
            if finished:
                continue
            if await db_conn_pool.fetchval(
                "SELECT finished from executors WHERE experiment_id = $1 AND executor_id = $2",
                experiment_id,
                executor_id,
            ):
                executor_status[executor_id] = True
                continue

            last_time_contacted = (
                await db_conn_pool.fetchval(
                    "SELECT keepalive FROM executors WHERE experiment_id = $1 AND executor_id = $2",
                    experiment_id,
                    executor_id,
                )
                or start_time
            )

            time_elapsed = (datetime.utcnow() - last_time_contacted).total_seconds()
            logger.debug(
                f"Executor {executor_id} last time contacted: {last_time_contacted},"
                f" time elapsed: {time_elapsed / 60} minutes, timeout: {timeout_minutes} minutes"
            )
            if time_elapsed > timeout_minutes * 60:
                executor_status[executor_id] = True
                exception = f"Executor {executor_id} timeout reached."
                await db_conn_pool.execute(
                    "UPDATE executors SET error = $1, finished = TRUE WHERE experiment_id = $2 AND executor_id = $3",
                    exception,
                    experiment_id,
                    executor_id,
                )

        await collect_all_executor_results(experiment, experiment_id)
        if all(executor_status.values()):
            break

        await asyncio.sleep(30)

    # again update final experiment result
    await collect_all_executor_results(experiment, experiment_id)
    await db_conn_pool.execute(
        "UPDATE experiments SET status = $1 WHERE experiment_id = $2",
        ExperimentStatus.FINISHED.value,
        experiment_id,
    )

    # remove all locks from minions
    minion_names = [x.minion.name for x in experiment]
    await db_conn_pool.execute(
        "UPDATE locks SET username = NULL WHERE username = $1 AND minion_name = ANY($2)",
        lock,
        minion_names,
    )
    logger.debug(f"Experiment {experiment_id} finished.")
    return


async def healthcheck() -> None:
    await db_conn_pool.fetchval("SELECT 1")


async def on_startup() -> None:
    global db_conn_pool
    db_conn_pool = await asyncpg.create_pool(
        host=DATABASE_ENDPOINT,
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        database=DATABASE_DB,
        init=__init_connection,
    )
    await healthcheck()


async def on_shutdown() -> None:
    await db_conn_pool.close()
