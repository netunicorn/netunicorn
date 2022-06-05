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

    # create deployment
    deployment_map = DeploymentMap()
    deployment_map.append(minion_pool[0], pipeline)

    # let's execute the same pipeline on the same node twice to see if it works
    deployment_map.append(minion_pool[0], pipeline)

    # let's create unique ID for deployment preparation
    # this make this method failure-safe: if you call this method twice with the same ID,
    # it will not create a new environment twice
    deployment_id = 'local_example_deployment'

    # ask engine to prepare deployment
    deployment_id = client.prepare_deployment(deployment_map, deployment_id)

    # wait for deployment to be prepared
    # wait for pipelines to finish
    while client.get_deployment_status(deployment_id) != DeploymentStatus.READY:
        time.sleep(1)

    # start executing
    client.start_execution(deployment_id)

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
