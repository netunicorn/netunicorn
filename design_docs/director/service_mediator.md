# Mediator service
This service provides API for users to get nodes information, experiments status, submit and start new experiments, and others. It interacts with the database and other services to support Experiment workflow and obtain requested information.

Specifically, it:
- Interactis with authentication service to authenticate users
- Represents information (stored in database) about currently running experiments belonging to a user
- Interacts with infrastructure service to represent nodes available to a user
- Handles an experiment preparation request, including interaction with the compilation service for environment compilation and interaction with the infrastructure service to deploy and start experiments

## Public endpoint
This service's public endpoint is supposed to be available by users.