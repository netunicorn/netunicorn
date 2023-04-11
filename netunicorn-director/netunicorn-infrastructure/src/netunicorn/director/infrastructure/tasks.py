import asyncio
import logging
from collections import defaultdict
from typing import NoReturn

import asyncpg
from netunicorn.base import Experiment, ExperimentStatus
from netunicorn.base.deployment import Deployment
from netunicorn.base.types import ExperimentRepresentation
from netunicorn.director.base.connectors.protocol import NetunicornConnectorProtocol


async def cleanup_watchdog_task(
    connectors: dict[str, NetunicornConnectorProtocol],
    db_conn_pool: asyncpg.pool.Pool,
    logger: logging.Logger,
    timeout_sec: int = 300,
) -> NoReturn:
    logger.info("Cleanup watchdog task started.")
    while True:
        async with db_conn_pool.acquire() as conn:
            async with conn.transaction():
                experiments = await conn.fetch(
                    "SELECT experiment_id, data::jsonb FROM experiments "
                    "WHERE status IN ($1, $2) AND NOT cleaned_up LIMIT 1",
                    ExperimentStatus.FINISHED.value,
                    ExperimentStatus.UNKNOWN.value,
                )
                if not experiments:
                    await asyncio.sleep(timeout_sec)
                    continue

                for row in experiments:
                    await conn.execute(
                        "UPDATE experiments SET cleaned_up = TRUE WHERE experiment_id = $1",
                        row["experiment_id"],
                    )
                    logger.info(
                        f"Cleanup watchdog task: experiment {row['experiment_id']} marked as cleaned up."
                    )

                    experiment_data: ExperimentRepresentation = row["data"]
                    if experiment_data is None:
                        logger.warning(
                            f"Cleanup watchdog task: experiment {row['experiment_id']} has no data."
                        )
                        continue
                    experiment: Experiment = Experiment.from_json(experiment_data)
                    deployments: dict[str, list[Deployment]] = defaultdict(list)
                    for deployment in experiment.deployment_map:
                        if deployment.cleanup:
                            deployments[str(deployment.node["connector"])].append(
                                deployment
                            )

                    for connector_name in connectors:
                        if connector_name not in deployments:
                            continue
                        connector = connectors[connector_name]
                        try:
                            await connector.cleanup(
                                row["experiment_id"], deployments[connector_name]
                            )
                        except Exception as e:
                            logger.exception(
                                f"Cleanup watchdog task: error while cleaning up experiment {row['experiment_id']}.",
                                exc_info=e,
                            )
                            logger.warning(
                                f"Connector {connector_name} raised an exception: {str(e.with_traceback(e.__traceback__))}"
                            )
                            logger.warning(
                                f"Connector {connector_name} moved to unavailable status."
                            )
                            connectors.pop(connector_name)
