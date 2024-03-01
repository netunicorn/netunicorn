# Deployment

In this section we describe how to deploy netUnicorn instance. We provide two deployment options: simplified deployment for testing purposes and production deployment.

## Support
You can join [netUnicorn Slack workspace](https://join.slack.com/t/netunicorn/shared_invite/zt-240tsalar-l1Wc3DERTlXJ6wE~DXmm9A) for support and discussions.


## AWS Deployment

If you want to deploy test instance of netUnicorn on AWS, you can use "netunicorn-v0.4" AMI.

Deployment steps:
1. Create AWS EC2 instance:
   1. Choose "netunicorn-v0.4" community AMI.
   2. Choose "Allow HTTP traffic" in the security group.
   3. [Optional] Allow TCP ports 5000 (docker registry), 5432 (PostgreSQL database), 9000 (netUnicorn UI), 26512 (netUnicorn gateway) for access to corresponding services 
2. Use the next credentials to access the netUnicorn instance:
   - Username: `test`
   - Password: `test`
   - URL: `http://<public IP or DNS name of the instance>`
3. You also can access the instance PostgreSQL database over the port 5432 (if allowed in security group) with the next credentials:
   - Username: `development`
   - Password: `development`
   - Database: `development`
4. [Optional] You can login into the machine and change the information in ~/netunicorn/docker-compose.yml.
   - [Optional] Change IP of the NETUNICORN_MEDIATOR_ENDPOINT environment variable in netunicorn-ui service to your VM IP address to enable netunicorn-ui at the http:/<your_ip>:9000  (use the same credentials as for netUnicorn API instance)

## Simplified deployment

This section describes the simplified deployment of netUnicorn instance for testing purposes. It could be done on your laptop
or any virtual machine.

**Important:** this deployment operates with default credentials for the netUnicorn instance and the database. It is not secure and should not be used in production. Database credentials are stored in the `docker-compose.yml` file. Instance will have `test` user with `test` password, defined in the `development/users.sql` file.

### Prerequisites
- Linux-based OS (as Docker containers are Linux-based)
- Installed `wget`
- Installed Docker and Docker Compose plugin. Please, refer to [Docker installation guide](https://docs.docker.com/engine/install/) and [Docker Compose installation guide](https://docs.docker.com/compose/install/).
    - If you use rootless installation of Docker, please modify `/var/run/docker.sock` links on the left side of volume sections in docker-compose.yml file as needed (usually, to `/run/user/1000/docker.sock` if your user id is 1000)

### Installation

1. Create a separate folder for local netunicorn configuration files and `cd` into this folder.
2. Download and run installation script:
   ```bash
   wget https://raw.githubusercontent.com/netunicorn/netunicorn/main/netunicorn-director/scripts/install.sh
   chmod +x install.sh
   ./install.sh
   ```
   - This script will create needed directories and put configuration files into them.
   - **Optional:** We encourage you to explore the file content before running to verify the harmless nature of the script.
3. Run docker compose:
   ```bash
   docker compose up
   ```
   - This command will download and run all needed containers.
   - **Optional:** You can explore the `docker-compose.yml` file content before running and make changes as needed (e.g., change database login and password, ports, etc.)

Now you should have running instance of `netunicorn` platform on your machine.

You can verify installation using the next methods:
- PostgreSQL database is available on `localhost:5432` with credentials from the `docker-compose.yml` file.
- Monitoring webpage is available on `localhost:26611/admin` with credentials from `development/user.sql` file (by default: `test/test`)
- netUnicorn API endpoint is available on `localhost:26611` with credentials from `development/user.sql` file (by default: `test/test`) and can be used in experiments (e.g., see example experiments in `/examples` folder of the repository)
- `docker-compose logs` command can be used to see logs of all running containers. All containers should be running stable. Some container could have errors in the log (connection errors to the database in the beginning when the database was not ready) but they should be resolved in a few seconds.

## Production deployment

This section describes the production deployment of netUnicorn instance.

### Services of netUnicorn platform

netUnicorn platform consists of several services communicating with each other. There are "General Services", that are external to the platform and could be used by other applications, and "netUnicorn Director Services", that are developed by netUnicorn team.

#### General Services

- PostgreSQL database: stores all data of the platform. Should be accessible by all director services. Could be used by other applications. Some administration could be done only via direct database access.
- Docker Registry. Should be accessible by the `compilation` service for write access and all nodes for read access. Could be used by other applications.

#### netUnicorn Director Services

- `authentication`: provides authentication for the platform. Should be accessible by the mediator.
- `compilation`: compiles Docker images for the platform. Should have mapping of `/var/run/docker.sock` to the host machine for using Docker engine for compilation, and local Docker engine should have write access to the Docker Registry.
- `gateway`: provides API for nodes. Should be accessible by the nodes (exposed port should be accessible by the nodes).
- `processor`: monitors current experiments and nodes locks.
- `infrastructure`: provides connectivity to the infrastructure (e.g., Kubernetes cluster). Separate configuration file should be provided during the startup. Should have access to the provided infrastructure (e.g., Kubernetes cluster, AWS, SaltStack API, etc.)
- `mediator`: API endpoint for end users. Depends on all other services. Exposed port should be available to netUnicorn users. Should have network access to `infrastructure` and `authentication` services.

### Deployment

Here we describe the deployment of the netUnicorn on the example of the docker compose deployment. In case of other deployment options (e.g., manual service deployment on different machines) the deployment process should be adjusted accordingly (expose ports from containers and verify network access between services).

#### Services in Docker containers

All services are implement as Docker images. If you want to deploy services outside of the containers, use preparation and entrypoint commands from the corresponding Dockerfiles for services startup.

#### Deployment steps

1. Download the `docker-compose-stable.yml` from the `netunicorn/netunicorn-director` folder. 
2. Create required files and modify variables (see "Deployment Modifications" below) in the `docker-compose-stable.yml` file according to your deployment scenario.
3. Run `docker-compose -f docker-compose-stable.yml up -d` command to start all services.
4. You can use `docker-compose -f docker-compose-stable.yml logs` command to see logs of all services.

#### Deployment Modifications

Most of the variables and parameters in the docker compose file are self-explanatory. We describe some of parameters, modification details, and files here in more details.

- environment variable `NETUNICORN_DATABASE_ENDPOINT` contains the URL of the database.
- `registry` service should expose registry port (by default: 5000)
- scripts for database initialization are available at `netunicorn-director/scripts/dbdeploy.sql`. If deploying the database from the docker compose file, they should be mapped to the `/docker-entrypoint-initdb.d` folder of the `database` service.
- `compilation` service should have `/var/run/docker.sock` mapped to the host machine for using Docker engine for compilation (usually `/var/run/docker.sock:/var/run/docker.sock`, but could be different (e.g., in case of using rootless Docker installation).
- `mediator` service should have `NETUNICORN_INFRASTRUCTURE_ENDPOINT` and `NETUNICORN_AUTH_ENDPOINT` variables pointing at the corresponding services, and also `NETUNICORN_DOCKER_REGISTRY_URL` with publicly available URL of the Docker Registry (e.g., `<public IP>:5000`).
- `infrastructure` service should be provided a configuration YAML file during the startup. This file describes what connectors should be imported and initialized and provides configuration for each connector. Example configuration file is available at `netunicorn-director/scripts/infrastructure-example-config.yaml`. 
  - Each of the connectors will have an example of their configuration for infrastructure config file. All settings should be combined into a single file to pass to the service.

