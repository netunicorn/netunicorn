# Target infrastructure
This document describes *target infrastructure* and its components, such as **Environment** and **Executor**.

Each node of the system is treated in the same way - as a generic device capable of running some environment and executing arbitrary Python code via executor inside this environment. Environment are to be generated for each device according to their architectural capabilities (operating system, hardware architecture, etc.).
## Environment
Environment is defined as an execution space where executor is installed and to be started. Environment provides execution capabilities, such as installed software, proper file system configuration (e.g., all needed files are presented), and should (if possible) isolate executor from other executors and host device OS/hardware (to not modify node configuration itself) 
A good example of the environment is Docker Image:
- It provides software and needed file system changes to the executor that would work inside the container
- It isolates executor from operating system and prevent any changes (unless explicitly mount)
- It's reproducible
- It's easy to delete afterwards

Other examples of the environment are virtual machine images, installation scripts (for bare-metal deployments)

### Environment creation and usage
- Environment would be created by *core services*
- Environment would be distributed to devices via network
- Any *target* device would support at least one environment
- Pipeline for executor would be provided as part of the environment or obtained via gateway
	- In case of presenting in the environment it would be a serialized artifact in a specific location on file system
- Environment would provide variable information to the executor (unique IDs, etc.) via environment variables set during environment startup

## Executor
Executor is an agent that's deployed on a target node and executes a DAG.

By default, director infrastructure only has access to target nodes via deployment system which capabilities could be different. Therefore, and also to disentangle target nodes from central server to work even in bad network conditions, target nodes would have separate Executor to control DAG execution.

Executor is installed in the Environment distributed to the node together with the pipeline itself and everything that execution of the pipeline needs. 

### Design
Executor is a monolith application that starts together with the surrounding environment, load the DAG, executes the DAG, provides event-system access to tasks in the DAG, and report results.

### Functional requirements
Requirements are sorted by importance.
- Executor must load the DAG, execute it, and (potentially) be able to send results of execution to the master
- Executor must be Python-based and execute DAG tasks via multiprocessing system
- Executor will receive variable configuration information via environment variables
- Executor must implement keep-alive ping mechanism to notify *core services* about its status
- Executor must collect all internal log information (from the executor itself) and stdout/stderr of each executed tasks, combine them into a single log and send to the master together with results of execution
- Executor must hold a common in-memory storage for tasks. Each task should have read and write access to this storage to be able to put temporary information there for DAG execution purposes

### Non-functional requirements
- Executor should be as stable and reliable as it's possible
- Executor should minimize inter-task time (time between end of previous task and start of the next available task)
- Executor should minimize abstraction cost
