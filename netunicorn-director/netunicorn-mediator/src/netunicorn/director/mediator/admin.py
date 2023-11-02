from os.path import dirname, join

from fastapi import HTTPException, Request, Response
from fastapi.templating import Jinja2Templates
from netunicorn.base.experiment import ExperimentStatus

from .engine import get_db_connection_pool, verify_sudo
from .resources import logger

template_dir = join(dirname(__file__), "templates")
templates = Jinja2Templates(directory=template_dir)
logger.info(f"Templates directory: {template_dir}")


async def get_locked_nodes() -> list[tuple[str, str, str]]:
    """
    Returns a list of locked nodes.

    :returns: List of (node_name, username, connector)
    """
    db_conn_pool = await get_db_connection_pool()

    result = await db_conn_pool.fetch(
        "SELECT node_name, username, connector FROM locks"
    )
    return [(row["node_name"], row["username"], row["connector"]) for row in result]


async def get_active_experiments() -> list[
    tuple[str, str, str, ExperimentStatus, str, str, str]
]:
    """
    Returns a list of active experiments.

    :returns: List of (username, experiment_name, experiment_id, status, error, creation_time, start_time)
    """
    db_conn_pool = await get_db_connection_pool()

    result = await db_conn_pool.fetch(
        f"""
        SELECT username, experiment_name, experiment_id, status, error, creation_time, start_time 
        FROM experiments where status in (
            '{ExperimentStatus.PREPARING.value}',
            '{ExperimentStatus.RUNNING.value}',
            '{ExperimentStatus.UNKNOWN.value}',
            '{ExperimentStatus.READY.value}'
         )
        """
    )
    return [
        (
            row["username"],
            row["experiment_name"],
            row["experiment_id"],
            ExperimentStatus(row["status"]),
            row["error"],
            row["creation_time"],
            row["start_time"],
        )
        for row in result
    ]


async def get_active_compilations() -> list[tuple[str, str, str, str]]:
    """
    Returns a list of active compilations.

    :returns: List of (experiment_id, compilation_id, architecture, environment_definition)
    """
    db_conn_pool = await get_db_connection_pool()

    result = await db_conn_pool.fetch(
        f"""
        SELECT experiment_id, compilation_id, architecture, environment_definition
        FROM compilations where status is NULL
        """
    )
    return [
        (
            row["experiment_id"],
            row["compilation_id"],
            row["architecture"],
            row["environment_definition"],
        )
        for row in result
    ]


async def admin_page(request: Request, username: str) -> Response:
    if not await verify_sudo(username):
        raise HTTPException(status_code=403, detail="Access denied")

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "active_experiments": await get_active_experiments(),
            "locked_nodes": await get_locked_nodes(),
            "active_compilations": await get_active_compilations(),
        },
    )