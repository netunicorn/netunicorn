import asyncio
import base64
import os
from typing import Mapping, NoReturn

import cloudpickle
from aiohttp import web

from pinot.director.engine.resources import logger
import pinot.director.engine.engine as engine

routes = web.RouteTableDef()


def parse_credentials(headers: Mapping) -> (str, str):
    """
    Parse credentials from Authorization header
    :param headers: request headers
    :return: (username, password)
    """
    try:
        if 'Authorization' not in headers:
            raise web.HTTPUnauthorized()

        credentials_string = headers['Authorization'].split(' ')[1]
        credentials = base64.b64decode(credentials_string).decode('utf-8').split(':', maxsplit=1)
        login, password = credentials
        return login, password
    except Exception as e:
        logger.exception(f"Failed to parse credentials: {e}")
        raise web.HTTPUnauthorized()


@routes.get("/api/v1/minion_pool")
async def get_minion_pool(request: web.Request):
    """
    This method should return description of minions from a deployer
    """

    credentials = parse_credentials(request.headers)
    result = await engine.get_minion_pool(credentials)
    return web.Response(body=cloudpickle.dumps(result), status=200)


@routes.post("/api/v1/compile/{environment_id}")
async def compile_pipeline(request: web.Request):
    """
    This method should start preparation of environment and return a unique id for the process
    :return: unique id of preparation process
    """
    environment_id = request.match_info['environment_id']
    credentials = parse_credentials(request.headers)
    pipeline = cloudpickle.loads(await request.read())
    result = engine.compile_pipeline(credentials, environment_id, pipeline)
    return web.Response(body=result, status=200)


@routes.get("/api/v1/compile/{environment_id}")
async def get_compiled_pipeline(request: web.Request):
    """
    This method should accept unique id of environment preparation and return compiled pipeline
    """
    environment_id = request.match_info['environment_id']
    credentials = parse_credentials(request.headers)
    result = await engine.get_compiled_pipeline(credentials, environment_id)
    return web.Response(body=cloudpickle.dumps(result), status=200)


@routes.post("/api/v1/deployment/{deployment_id}")
async def deploy_map(request: web.Request):
    """
    This method should accept deployment map and start deployment of a pipeline according to the map
    :return: unique id of deployment
    """
    deployment_id: str = request.match_info['deployment_id']
    credentials = parse_credentials(request.headers)
    deployment_map = cloudpickle.loads(await request.read())
    result = engine.deploy_map(credentials, deployment_map, deployment_id)
    return web.Response(body=result, status=200)


@routes.get("/api/v1/deployment/{deployment_id}")
async def get_deployment_status(request: web.Request):
    """
    This method should accept unique id of deployment and return status of deployment (running, finished)
    """
    deployment_id = request.match_info['deployment_id']
    credentials = parse_credentials(request.headers)
    result = await engine.get_deployment_status(credentials, deployment_id)
    return web.Response(body=cloudpickle.dumps(result), status=200)


@routes.get("/api/v1/deployment/{deployment_id}/result")
async def get_deployment_result(request: web.Request):
    """
    This method should accept unique id of deployment and return result of execution of pipelines on all minions
    :return: {"<executor_id>": {"minion": minion_info, "result": result}, ...}
    """
    deployment_id = request.match_info['deployment_id']
    credentials = parse_credentials(request.headers)
    result = await engine.get_deployment_result(credentials, deployment_id)
    return web.Response(body=cloudpickle.dumps(result), status=200)


async def start_web_server() -> NoReturn:
    app = web.Application()
    app.add_routes(routes)

    address = os.environ.get('PINOT_ENGINE_IP') or '0.0.0.0'
    port = int(os.environ.get('PINOT_ENGINE_PORT') or '26511')
    logger.info(f"Starting engine on {address}:{port}")

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, address, port)
    await site.start()
    logger.info(f"Engine started")
    while True:
        await asyncio.sleep(3600)
