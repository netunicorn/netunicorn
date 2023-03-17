import asyncio
from datetime import datetime, timedelta
from typing import NoReturn

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
db_conn_pool: asyncpg.Pool

locker_task_handler: asyncio.Task[NoReturn]
update_experiments_task_handler: asyncio.Task[NoReturn]
preparing_experiment_watchdog_task_handler: asyncio.Task[NoReturn]


async def collect_executors_results(experiment_id: str, experiment: Experiment) -> None:
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


async def update_experiment_status(
    experiment_id: str, experiment: Experiment, start_time: datetime
) -> None:
    if await db_conn_pool.fetchval(
        "SELECT error FROM experiments WHERE experiment_id = $1", experiment_id
    ):
        # error happened, set status to UNKNOWN
        await db_conn_pool.execute(
            "UPDATE experiments SET status = $1 WHERE experiment_id = $2",
            ExperimentStatus.UNKNOWN.value,
            experiment_id,
        )
        return

    # collect all results and add to experiment object
    await collect_executors_results(experiment_id, experiment)

    # check if there are any unfinished executors
    executor_timeouts = {
        x.executor_id: x.keep_alive_timeout_minutes for x in experiment
    }
    unfinished_executors = await db_conn_pool.fetch(
        "SELECT executor_id, keepalive FROM executors WHERE experiment_id = $1 AND finished = FALSE",
        experiment_id,
    )
    alive_executor_exists = False
    if unfinished_executors is not None:
        for line in unfinished_executors:
            executor_id = line["executor_id"]
            keepalive = line["keepalive"]
            if keepalive is None:
                keepalive = start_time
            if (
                keepalive + timedelta(minutes=executor_timeouts[executor_id])
                < datetime.now()
            ):
                # executor is timed out
                await db_conn_pool.execute(
                    "UPDATE executors SET finished = TRUE, error = $1 WHERE experiment_id = $2 AND executor_id = $3",
                    "Executor timed out",
                    experiment_id,
                    executor_id,
                )
                logger.debug(f"Executor {executor_id} timed out")
            else:
                alive_executor_exists = True

    if not alive_executor_exists:
        # all executors are finished
        await db_conn_pool.execute(
            "UPDATE experiments SET status = $1 WHERE experiment_id = $2",
            ExperimentStatus.FINISHED.value,
            experiment_id,
        )
        await collect_executors_results(experiment_id, experiment)
        logger.debug(f"Experiment {experiment_id} finished")


async def update_experiments_task(timeout_sec: int = 30) -> NoReturn:
    while True:
        async with db_conn_pool.acquire() as conn:
            async with conn.transaction():
                experiment_ids = await conn.fetch(
                    "SELECT experiment_id, data::jsonb, start_time FROM experiments WHERE status = $1",
                    ExperimentStatus.RUNNING.value,
                )
                for line in experiment_ids:
                    experiment_id = line["experiment_id"]
                    experiment = Experiment.from_json(line["data"])
                    start_time = line["start_time"]
                    await update_experiment_status(
                        experiment_id, experiment, start_time
                    )
        await asyncio.sleep(timeout_sec)


async def locker_task(timeout_sec: int = 10) -> NoReturn:
    logger.info("Locker task started.")
    while True:
        # get all experiment that are in PREPARING, READY, or RUNNING state
        experiments = await db_conn_pool.fetch(
            "SELECT username, data::jsonb FROM experiments WHERE status IN ($1, $2)",
            ExperimentStatus.PREPARING.value,
            ExperimentStatus.RUNNING.value,
        )
        if not experiments:
            await asyncio.sleep(timeout_sec)
            continue

        nodes_to_lock: set[
            tuple[str, str, str]
        ] = set()  # username, node_name, connector
        # get all nodes that are in use by these experiments
        for experiment in experiments:
            experiment_data = experiment["data"]
            if experiment_data is None:
                continue
            experiment_data = Experiment.from_json(experiment_data)
            for deployment in experiment_data.deployment_map:
                nodes_to_lock.add(
                    (
                        experiment["username"],
                        deployment.node.name,
                        deployment.node["connector"],
                    )
                )

        # in transaction: delete all from the table and insert current locks
        async with db_conn_pool.acquire() as conn:
            async with conn.transaction():
                # we want to delete all rows, seriously
                await conn.execute("TRUNCATE TABLE locks")
                for username, node, connector in nodes_to_lock:
                    await conn.execute(
                        "INSERT INTO locks (username, node_name, connector) VALUES ($1, $2, $3)",
                        username,
                        node,
                        connector,
                    )

        await asyncio.sleep(timeout_sec)


async def preparing_experiment_watchdog_task(timeout_sec: int = 3600) -> NoReturn:
    logger.info("Preparing experiment watchdog task started.")
    while True:
        async with db_conn_pool.acquire() as conn:
            async with conn.transaction():
                experiment_ids = await conn.fetch(
                    "SELECT experiment_id, data::jsonb, start_time FROM experiments WHERE status = $1",
                    ExperimentStatus.PREPARING.value,
                )
                for line in experiment_ids:
                    experiment_id = line["experiment_id"]
                    creation_time = line["creation_time"]
                    if datetime.now() - creation_time > timedelta(days=1):
                        # most likely something went wrong, set status to UNKNOWN
                        await conn.execute(
                            "UPDATE experiments SET status = $1 WHERE experiment_id = $2",
                            ExperimentStatus.UNKNOWN.value,
                            experiment_id,
                        )
                        logger.warning(
                            f"Experiment {experiment_id} timed out during preparation."
                        )
        await asyncio.sleep(timeout_sec)


async def task_done_callback(fut: asyncio.Future[NoReturn]) -> None:
    try:
        locker_task_handler.cancel()
        update_experiments_task_handler.cancel()
        preparing_experiment_watchdog_task_handler.cancel()
        fut.result()
    except asyncio.CancelledError:
        logger.info("Task cancelled.")
    except Exception as e:
        logger.error(f"Task failed: {e}")
        raise e


async def main() -> None:
    global locker_task_handler, update_experiments_task_handler, db_conn_pool, preparing_experiment_watchdog_task_handler
    db_conn_pool = await asyncpg.create_pool(
        host=DATABASE_ENDPOINT,
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        database=DATABASE_DB,
        init=__init_connection,
    )

    locker_task_handler = asyncio.create_task(locker_task())
    locker_task_handler.add_done_callback(task_done_callback)

    update_experiments_task_handler = asyncio.create_task(update_experiments_task())
    update_experiments_task_handler.add_done_callback(task_done_callback)

    preparing_experiment_watchdog_task_handler = asyncio.create_task(
        preparing_experiment_watchdog_task()
    )
    preparing_experiment_watchdog_task_handler.add_done_callback(task_done_callback)

    await asyncio.gather(locker_task_handler, update_experiments_task_handler)


if __name__ == "__main__":
    asyncio.run(main())
