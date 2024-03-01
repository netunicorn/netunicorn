# Connectors
The modular design of netunicorn allows to implement connectors to different local, virtual, and physical infrastructures. Anyone can implement a connector as a simple Python package and share to other netunicorn users (even without the netunicorn core team support). 

## Connectors design
Connectors are Python packages that implement a specific interface, defined in [protocol](https://github.com/netunicorn/netunicorn/blob/main/netunicorn-base/src/netunicorn/director/base/connectors/protocol.py) document. 

If you want to create a new connector, you can use the [template](https://github.com/netunicorn/netunicorn-connector-template) provided by the netunicorn core team.

Administrators of netunicorn instance can easily attach connectors to the platform instance and control by providing configuration parameters. Please, refer to specific connectors' documentation for details on configuration.

## Available connectors
Here we provide a (non-exhaustive) list of available connectors known to netunicorn core team:

- [SaltStack](https://github.com/netunicorn/netunicorn-connector-salt) -- a connector to SaltStack-controlled infrastructure.
- [Mininet (Containernet)](https://github.com/netunicorn/netunicorn-connector-containernet) -- connector using Containernet to create virtual topologies for experiments.
- [AWS Fargate](https://github.com/netunicorn/netunicorn-connector-aws) -- connector to AWS Fargate-based containers.
- [Azure Container Instances](https://github.com/netunicorn/netunicorn-connector-aci) -- connector to Azure Container Instances.
- [Docker](https://github.com/netunicorn/netunicorn-connector-docker) -- connector for local Docker-based experiments.
- [Kubernetes](https://github.com/netunicorn/netunicorn-connector-kubernetes) -- connector to Kubernetes infrastructures.
- [SSH](https://github.com/netunicorn/netunicorn-connector-ssh) -- simple connector utilizing SSH to control remote hosts and deploy experiments.

If you have implemented a connector and want to share it with the community, you can contact us to add it to the list.