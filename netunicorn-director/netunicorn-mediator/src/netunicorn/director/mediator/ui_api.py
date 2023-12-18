from os.path import dirname, join

from fastapi.templating import Jinja2Templates
from returns.result import Result, Success

from netunicorn.base.experiment import Experiment, ExperimentStatus

from .engine import get_db_connection_pool, verify_sudo
from .resources import logger

template_dir = join(dirname(__file__), "templates")
templates = Jinja2Templates(directory=template_dir)
logger.info(f"Templates directory: {template_dir}")


async def get_locked_nodes(username: str) -> Result[list, str]:
    """Returns locked nodes."""
    db_conn_pool = await get_db_connection_pool()

    # if sudo - return all
    if await verify_sudo(username):
        result = await db_conn_pool.fetch(
            "SELECT node_name, username, connector FROM locks "
        )
    else:
        result = await db_conn_pool.fetch(
            "SELECT node_name, username, connector FROM locks WHERE username = $1",
            username,
        )

    return Success(
        [
            {
                "node_name": row["node_name"],
                "username": row["username"],
                "connector": row["connector"],
            }
            for row in result
        ]
    )


def try_get_nodes(data) -> list[str]:
    try:
        experiment = Experiment.from_json(data)
        return [deployment.node.name for deployment in experiment.deployment_map]
    except Exception:
        return []


async def _get_experiments(query: str) -> Result[list, str]:
    db_conn_pool = await get_db_connection_pool()

    rows = await db_conn_pool.fetch(query)

    result = [
        {
            "username": row["username"],
            "experiment_name": row["experiment_name"],
            "experiment_id": row["experiment_id"],
            "status": str(ExperimentStatus(row["status"])),
            "error": row["error"],
            "creation_time": str(row["creation_time"]),
            "start_time": str(row["start_time"]),
            "nodes": "",
        }
        for row in rows
    ]

    for i, row in enumerate(rows):
        result[i]["nodes"] = ", ".join(try_get_nodes(row["data"]))

    return Success(result)


async def get_last_experiments(username: str, days: int) -> Result[list, str]:
    query = f"""
            SELECT username, experiment_name, experiment_id, status, error, creation_time, start_time, data
            FROM experiments where creation_time > now() - interval '{days} days' 
            """

    if not await verify_sudo(username):
        query += f" AND username = '{username}' "

    query += "ORDER BY start_time DESC, creation_time DESC"
    return await _get_experiments(query)


async def get_running_experiments(username: str) -> Result[list, str]:
    query = f"""
        SELECT username, experiment_name, experiment_id, status, error, creation_time, start_time, data 
        FROM experiments where status in (
            '{ExperimentStatus.PREPARING.value}',
            '{ExperimentStatus.RUNNING.value}'
         ) 
        """

    if not await verify_sudo(username):
        query += f" AND username = '{username}'"

    query += "ORDER BY start_time DESC, creation_time DESC"

    return await _get_experiments(query)


async def get_active_compilations(username: str) -> Result[list, str]:
    db_conn_pool = await get_db_connection_pool()

    request = """
    SELECT e.username, e.experiment_name, c.experiment_id, c.compilation_id, c.architecture
        FROM compilations as c
        LEFT JOIN experiments as e ON c.experiment_id = e.experiment_id
        where c.status is NULL
    """

    if await verify_sudo(username):
        result = await db_conn_pool.fetch(request)
    else:
        result = await db_conn_pool.fetch(request + " AND e.username = $1", username)

    return Success(
        [
            {
                "username": row["username"],
                "experiment_name": row["experiment_name"],
                "experiment_id": row["experiment_id"],
                "compilation_id": row["compilation_id"],
                "architecture": row["architecture"],
            }
            for row in result
        ]
    )
