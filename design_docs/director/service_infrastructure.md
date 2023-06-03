# Infrastructure service
This service is responsible for representing the current existing and available infrastructure to users. Specifically, it receives requests from mediation service and asks available connectors to provide the required information or execute a request.

## Implemented requests
- Get nodes: returns information from connectors about nodes available to a user
- Create deployment: determine and request connectors to start a deployment of given environment definition
- Start execution: determine and request connectors to start specific deployments
- Stop experiment execution: determine and request connectors to stop experiment execution
- Stop executors: determine and request connectors to stop specific executors

## Connectors system
This module retranslates most of the requests to different connectors that implements logic particular to a specific system. For example, Azure Container Instances connector works with Azure Container Instances in Azure Cloud to dynamically create and deploy executors. Each connector should implement all of the requests enumerated above.

By default, connectors are implemented as Python package (which allows to just install them in the system) and imported during the startup of the module. Besides this, there's also a generic REST connector that can enable interaction with another part of the connector, implemented and hosted as a separate API.

The example of infrastructure module initialization and configuration is provided in the [configuration-example.yaml](../../netunicorn-director/netunicorn-infrastructure/configuration-example.yaml).