# netunicorn project

This is a main repository for netunicorn project.

netunicorn is a platform for building and running data pipelines on certain nodes for data collection experiments.
It allows users to express arbitrary Python-based tasks and pipelines and assign them to particular nodes.

This platform is close to the Apache Airflow or CI/CD platforms, but instead optimizes the following:
- ability to use different infrastructures via specific connectors (e.g., SaltStack-based, Azure Container Instances, Mininet, etc.)
- short time between tasks
- work under the conditions of unstable network
- reproducibility and easy sharing of tasks and pipelines

Full documentation is available at [architecture](docs/README.md) and in the platform whitepaper (to be published).

## Platform user documentation
Users are able to express arbitrary tasks and pipelines and run them on the already deployed platform.

### Installation
To use the platform, a user should install the next packages:
```bash
pip install netunicorn-client    # required, client to connect to the platform
pip install netunicorn-library   # optional, library with tasks and pipelines
```

### Prerequisites
To use the platform, administrators of the infrastructure should deploy it and provide you the next credentials:
- endpoint: API url of the platform
- username: your username
- password: your password

These credentials would be used to work with the platform via RemoteClient.

### Start of work
Please, refer to [examples](examples/README.md) to see how to use the platform.

## Platform administrator documentation
Administrators of the platform maintain the particular netunicorn installation and underlying infrastructure.  
Infrastructure is a set of nodes (like virtual machines, dynamically created containers, or physical nodes) that will be
used to run tasks and pipelines created by users.

### Prerequisites
The platform assumes that the infrastructure is already deployed and configured and **centrally** managed by one of
the existing management tools (like Ansible, SaltStack, etc.). For this tool, a connector should be implemented.
Currently, the connectors for the following infrastructures are available:
- SaltStack-managed infrastructure
- Azure Container Instances (in Azure Cloud)

Also, the next services are required for the platform:
- PostgreSQL database for states and logs

### Deployment
To be updated.
