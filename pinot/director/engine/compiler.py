from cloudpickle import dumps, loads

from pinot.base import Pipeline
from pinot.base.environment_definitions import ShellExecution, DockerImage
from pinot.director.engine.config import environment_type
from pinot.director.engine.resources import redis_connection


async def compile_environment(login: str, environment_id: str, pipeline: Pipeline) -> None:
    if environment_type == 'shell':
        return await compile_shell(login, environment_id, pipeline)
    elif environment_type == 'docker':
        return await compile_docker(login, environment_id, pipeline)
    else:
        raise NotImplementedError(f'Compiler for environment type {environment_type} is not implemented')


async def compile_docker(
        login: str,
        environment_id: str,
        pipeline: Pipeline
) -> None:
    if isinstance(pipeline.environment_definition, DockerImage):
        await redis_connection.set(f"{login}:pipeline:{environment_id}", dumps(pipeline))

    if isinstance(pipeline.environment_definition, ShellExecution):
        # TODO: create a docker image with these commands
        #  and push to local registry
        #  https://docs.docker.com/registry/deploying/
        #  And set to the pipeline DockerImage with returned image tag
        exception = NotImplementedError("Docker image creation from shell commands is not implemented yet")
        await redis_connection.set(f"{login}:pipeline:{environment_id}", dumps(exception))

    exception = Exception(f"Compiler for {pipeline.environment_definition} is not implemented")
    await redis_connection.set(f"{login}:pipeline:{environment_id}", dumps(exception))


async def compile_shell(
        login: str,
        environment_id: str,
        pipeline: Pipeline
) -> None:
    env_def = pipeline.environment_definition
    if env_def is None or isinstance(env_def, ShellExecution):
        await redis_connection.set(f"{login}:pipeline:{environment_id}", dumps(pipeline))
        return

    exception = Exception(
        "Engine is working in shell mode only, "
        "but environment definition of the pipeline is not shell"
    )
    await redis_connection.set(f"{login}:pipeline:{environment_id}", dumps(exception))
