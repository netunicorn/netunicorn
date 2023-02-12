import asyncio
from datetime import datetime, timedelta
from typing import Optional, NoReturn

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
update_experiments_task_handler: asyncio.Task


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


async def update_experiment_status(experiment_id: str, experiment: Experiment, start_time: datetime) -> None:
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
    executor_timeouts = {x.executor_id: x.keep_alive_timeout_minutes for x in experiment}
    unfinished_executors = await db_conn_pool.fetchval(
        "SELECT executor_id, keepalive FROM executors WHERE experiment_id = $1 AND finished = FALSE",
        experiment_id,
    )
    alive_executor_exists = False
    for executor_id, keepalive in unfinished_executors:
        if keepalive is None:
            keepalive = start_time
        if keepalive + timedelta(minutes=executor_timeouts[executor_id]) < datetime.now():
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
                    await update_experiment_status(experiment_id, experiment, start_time)
        await asyncio.sleep(timeout_sec)


async def locker_task(timeout_sec: int = 10) -> NoReturn:
    logger.info("Locker task started.")
    while True:
        # get all experiment that are in PREPARING, READY, or RUNNING state
        experiments = await db_conn_pool.fetch(
            "SELECT username, data::json FROM experiments WHERE status IN ($1, $2, $3)",
            ExperimentStatus.PREPARING.value,
            ExperimentStatus.READY.value,
            ExperimentStatus.RUNNING.value,
        )
        if not experiments:
            await asyncio.sleep(timeout_sec)
            continue

        nodes_to_lock: set[tuple[str, str, str]] = set()  # username, node_name, connector
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
    global db_conn_pool, locker_task_handler, update_experiments_task_handler
    db_conn_pool = await asyncpg.create_pool(
        host=DATABASE_ENDPOINT,
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        database=DATABASE_DB,
        init=__init_connection,
    )
    locker_task_handler = asyncio.create_task(locker_task())
    update_experiments_task_handler = asyncio.create_task(update_experiments_task())


async def main():
    global locker_task_handler, update_experiments_task_handler
    await on_startup()
    locker_task_handler = asyncio.create_task(locker_task())
    update_experiments_task_handler = asyncio.create_task(update_experiments_task())
    while True:
        await asyncio.sleep(1)
        if locker_task_handler.done() or update_experiments_task_handler.done():
            locker_task_handler.cancel()
            update_experiments_task_handler.cancel()
            break

if __name__ == '__main__':
    asyncio.run(main())


