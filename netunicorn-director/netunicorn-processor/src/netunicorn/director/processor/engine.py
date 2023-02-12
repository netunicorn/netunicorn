import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, NoReturn

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

locker_task_handler: asyncio.Task


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
                node=deployment.node,
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


async def watch_experiment_task(experiment_id: str) -> None:
    experiment_data = await db_conn_pool.fetchval(
        "SELECT data::jsonb FROM experiments WHERE experiment_id = $1", experiment_id
    )
    if experiment_data is None:
        logger.error(f"Experiment {experiment_id} not found.")
        return

    experiment: Experiment = Experiment.from_json(experiment_data)
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
        if datetime.utcnow() > start_time + timedelta(minutes=10):
            exc = f"Experiment {experiment_id} timeout (10 minutes) reached and still not started."
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

    logger.debug(f"Experiment {experiment_id} started at {start_time}")
    # executor_id: (finished_flag, timeout_minutes)
    executor_status: Dict[str, list[bool, int]] = {
        x.executor_id: [not x.prepared, x.keep_alive_timeout_minutes]
        for x in experiment
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

        for executor_id, (finished, timeout_minutes) in executor_status.items():
            if finished:
                continue
            if await db_conn_pool.fetchval(
                "SELECT finished from executors WHERE experiment_id = $1 AND executor_id = $2",
                experiment_id,
                executor_id,
            ):
                executor_status[executor_id][0] = True
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
                executor_status[executor_id][0] = True
                exception = f"Executor {executor_id} timeout reached."
                await db_conn_pool.execute(
                    "UPDATE executors SET error = $1, finished = TRUE WHERE experiment_id = $2 AND executor_id = $3",
                    exception,
                    experiment_id,
                    executor_id,
                )

        await collect_all_executor_results(experiment, experiment_id)
        if all(x[0] for x in executor_status.values()):
            break

        await asyncio.sleep(30)

    # again update final experiment result
    await collect_all_executor_results(experiment, experiment_id)
    await db_conn_pool.execute(
        "UPDATE experiments SET status = $1 WHERE experiment_id = $2",
        ExperimentStatus.FINISHED.value,
        experiment_id,
    )
    logger.debug(f"Experiment {experiment_id} finished.")
    return


async def healthcheck() -> None:
    await db_conn_pool.fetchval("SELECT 1")


async def locker_task(timeout_sec: int = 10) -> NoReturn:
    logger.info("Locker task started.")
    while True:
        # get all experiment that are in PREPARING, READY, or RUNNING state
        experiments = await db_conn_pool.fetch(
            "SELECT username, data FROM experiments WHERE status IN ($1, $2, $3)",
            ExperimentStatus.PREPARING.value,
            ExperimentStatus.READY.value,
            ExperimentStatus.RUNNING.value,
        )
        if not experiments:
            await asyncio.sleep(timeout_sec)
            continue

        nodes_to_lock: set[tuple[str, str, str]] = set()   # username, node_name, connector
        # get all nodes that are in use by these experiments
        for experiment in experiments:
            experiment_data = Experiment.from_json(experiment["data"])
            for deployment in experiment_data.deployment_map:
                nodes_to_lock.add((experiment["username"], deployment.node.name, deployment.node['connector']))

        # in transaction: delete all from the table and insert current locks
        async with db_conn_pool.acquire() as conn:
            async with conn.transaction():
                # we want to delete all rows, seriously
                await conn.execute("TRUNCATE TABLE locks")
                for username, node, connector in nodes_to_lock:
                    await conn.executemany(
                        "INSERT INTO locks (username, node_name, connector) VALUES ($1, $2, $3)",
                        username, node, connector
                    )

        await asyncio.sleep(timeout_sec)


async def on_startup() -> None:
    global db_conn_pool, locker_task_handler
    db_conn_pool = await asyncpg.create_pool(
        host=DATABASE_ENDPOINT,
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        database=DATABASE_DB,
        init=__init_connection,
    )
    await healthcheck()
    locker_task_handler = asyncio.create_task(locker_task())


async def on_shutdown() -> None:
    locker_task_handler.cancel()
    await db_conn_pool.close()
