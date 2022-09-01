import asyncio
from pickle import loads, dumps
from typing import Dict
from datetime import datetime

from netunicorn.base.experiment import ExperimentStatus, Experiment, ExperimentExecutionResult
from netunicorn.director.base.resources import get_logger, redis_connection

logger = get_logger('netunicorn.director.processor')


async def collect_all_executor_results(experiment: Experiment, experiment_id: str) -> None:
    experiment_result = await redis_connection.get(f"experiment:{experiment_id}:result")
    if experiment_result is not None and isinstance(loads(experiment_result), Exception):
        # do nothing
        return

    experiment_result = []
    for deployment in experiment:
        executor_result = await redis_connection.get(f"executor:{deployment.executor_id}:result")
        executor_result = loads(executor_result) if executor_result else None
        experiment_result.append(
            ExperimentExecutionResult(
                minion=deployment.minion,
                pipeline=deployment.pipeline,
                result=executor_result
            )
        )
    await redis_connection.set(f"experiment:{experiment_id}:result", dumps(experiment_result))


async def watch_experiment_task(experiment_id: str) -> None:
    experiment_data = await redis_connection.get(f"experiment:{experiment_id}")
    if experiment_data is None:
        logger.error(f"Experiment {experiment_id} not found.")
        return
    experiment: Experiment = loads(experiment_data)
    timeout_minutes = experiment.keep_alive_timeout_minutes
    start_time = datetime.now()

    status = await redis_connection.get(f"experiment:{experiment_id}:status")
    if status is None:
        logger.error(f"Experiment {experiment_id} status is not found.")
        return

    status = loads(status)
    if status != ExperimentStatus.RUNNING:
        logger.error(f"Experiment {experiment_id} is not running.")
        return

    # executor_id: finished_flag
    executor_status: Dict[str, bool] = {x.executor_id: not x.prepared for x in experiment}

    while True:
        status = await redis_connection.get(f"experiment:{experiment_id}:status")
        status = loads(status) if status else ExperimentStatus.UNKNOWN
        if status == ExperimentStatus.FINISHED:
            logger.warning("Unexpected status FINISHED for experiment {experiment_id}.")
            break

        if status != ExperimentStatus.RUNNING:
            await redis_connection.set(
                f"experiment:{experiment_id}:result",
                dumps(Exception(f"Experiment {experiment_id} is in unexpected status {status}. "))
            )
            break

        for executor_id, finished in executor_status.items():
            if finished:
                continue
            if await redis_connection.exists(f"executor:{executor_id}:result"):
                executor_status[executor_id] = True
                continue
            last_time_contacted = await redis_connection.get(f"executor:{executor_id}:keepalive")
            last_time_contacted = loads(last_time_contacted) if last_time_contacted else start_time
            if (datetime.now() - last_time_contacted).total_seconds() > timeout_minutes * 60:
                executor_status[executor_id] = True
                await redis_connection.set(
                    f"executor:{executor_id}:result",
                    dumps(Exception(f"Executor {executor_id} is not responding."))
                )

        await collect_all_executor_results(experiment, experiment_id)
        if all(executor_status.values()):
            break

        await asyncio.sleep(30)

    # again update final experiment result
    await collect_all_executor_results(experiment, experiment_id)
    await redis_connection.set(f"experiment:{experiment_id}:status", dumps(ExperimentStatus.FINISHED))
    return
