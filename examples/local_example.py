import time

from pinot.library.basic import SleepTask
from pinot.base.pipeline import Pipeline
from pinot.client.local import LocalClient
from pinot.base.deployment_map import DeploymentStatus, DeploymentMap


def main():
    # get client and available minions
    client = LocalClient()
    minion_pool = client.get_minion_pool()

    # prepare a pipeline
    pipeline = Pipeline().then([SleepTask(5), SleepTask(5)])

    # let's create unique ID for environment preparation
    # this make this method failure-safe: if you call this method twice with the same ID,
    # it will not create a new environment twice
    environment_id = 'local_example'

    # ask director to prepare environment for the pipeline
    environment_id = client.compile_pipeline(pipeline, environment_id)
    compiled_pipeline = client.get_compiled_pipeline(environment_id)

    deployment_map = DeploymentMap()
    # create deployment
    deployment_map.append(minion_pool[0], compiled_pipeline)

    # let's execute the same pipeline on the same node twice to see if it works
    deployment_map.append(minion_pool[0], compiled_pipeline)

    # doing the same with deployment_id
    deployment_id = 'local_example_deployment'

    # start deployment
    deployment_id = client.deploy_map(deployment_map, deployment_id)

    # wait for pipelines to finish
    while client.get_deployment_status(deployment_id) != DeploymentStatus.FINISHED:
        time.sleep(1)

    # get results
    results = client.get_deployment_result(deployment_id)
    print(results)


if __name__ == '__main__':
    # Unfortunately, as we use multiprocessing for LocalClient, you have to guard your main file with __main__ statement
    # It's a restriction of Python's multiprocessing module
    # You can safely use interactive mode for RemoteClient with real PINOT installation
    main()
