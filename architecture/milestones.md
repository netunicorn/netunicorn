# Milestones
In this document description of milestones is provided and what requirements the platform should satisfy for each of them

## Milestone 0.1
Goal: ability to use the platform for dataset collection based research in the particular university with fixed infrastructure
#### Requirements
- Task/Pipeline/Experiment definition and processing
- Ability to use a particular infrastructure deployed in the university (SaltStack)
- Ability to collect results, logs, and produced artifacts
- Task implementation support for different platforms (linux-based amd64, arm64, pisa switches via sidecar)
- Docker environment generation and usage

## Milestone 0.2
Goal: ability to deploy this platform in another universities and provide basic usage capabilities
#### Requirements
- Event-based system for nodes synchronization
- Easiness of deployment of the system (docker-compose)
- Basic authentication/authorization
- AWS and Ansible support
- Experiment preprocessor and postprocessor attachments

## Unsorted
- Adding user-specific infrastructure dynamically
- Implementation of DAGs instead of pipelines
- Inter-platform event-based interaction
- Analysis platform integration (closing the loop)