from pinot.base.deployment_map import Deployment

from pinot.base.environment_definitions import ShellExecution
from pinot.director.engine.config import environment_type


async def compile_deployment(login: str, deployment_id: str, deployment: Deployment) -> None:
    if environment_type == 'shell':
        return await compile_shell(deployment)
    elif environment_type == 'docker':
        return await compile_docker(login, deployment_id, deployment)
    else:
        raise NotImplementedError(f'Compiler for environment type {environment_type} is not implemented')


async def compile_docker(
        login: str,
        deployment_id: str,
        deployment: Deployment
) -> None:
    # TODO: create a docker image with these commands
    #  and push to local registry
    #  https://docs.docker.com/registry/deploying/
    #  And set to the pipeline DockerImage with returned image tag
    raise NotImplementedError('Compiler for docker is not yet implemented')


async def compile_shell(deployment: Deployment) -> None:
    env_def = deployment.pipeline.environment_definition
    if env_def is None or isinstance(env_def, ShellExecution):
        return

    exception = Exception(
        "Engine is working in shell mode only, "
        "but environment definition of the pipeline is not shell"
    )
    deployment.prepared = False
    deployment.error = exception
