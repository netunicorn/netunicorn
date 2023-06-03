# Compilation
This service process compilation requests from the mediation service.

## Docker compilation request procedure
To create an environment for a pipeline execution, mediation service takes environment definition from the deployment and creates a corresponding compilation request in the database.

Compilation service monitors active compilation requests in the database and process them. Specifically, for Docker compilation requests, it takes the environment definition and a pipeline to execute, creates a corresponding Dockerfile, compiles the image for a specific architecture and uploads the resulting image to the provided Docker repository.