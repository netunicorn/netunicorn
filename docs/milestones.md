# Milestones
In this document description of milestones is provided and what requirements the platform should satisfy for each of them

## Milestone 0.1 - achieved 12/19/22
Goal: ability to use the platform for dataset collection based research in the particular university with the fixed infrastructure
#### Requirements
- Task/Pipeline/Experiment definition and processing
- Ability to use a particular infrastructure deployed in the university (SaltStack)
- Ability to collect results, logs, and produced artifacts
- Task implementation support for different platforms (linux-based amd64, arm64, pisa switches via sidecar)
- Docker environment generation and usage

## Milestone 0.2 -- achieved 02/19/23
Goal: public availability of the platform (repositories and documentation), ability to deploy infrastructure in other places using cloud connectors
#### Requirements
- Stabilize the public API (netunicorn-base, netunicorn-client, public part of netunicorn-mediator)
- Ability to use multiple nodes infrastructures together
- Public documentation of the user-side of the platform
- Public documentation of the platform general design
- Examples of user-side code (basic usage, tasks creating, etc)
- Public repositories CI/CD workflows for releases
- Public Python package releases
- Public Docker images releases

## Milestone 0.3
Goal: ability to deploy this platform in another universities and provide basic usage capabilities
#### Requirements
- Event-based system for nodes synchronization
- Easiness of deployment of the system (docker-compose)
- AWS and Ansible support

## Unsorted
- Adding user-specific infrastructure dynamically
- Implementation of DAGs instead of pipelines
- Inter-platform event-based interaction
- Analysis platform integration (closing the loop)