# General design
This document contains a general design of the system. Also take a look at the [vocabulary](vocabulary.md).

The [user story](userstory.md) describes user's view on the system. From the user story [requirements](requirements.md) and this architecture are created.

## Workflow
1. User defines a Directed Acyclic Graph (DAG) of tasks
    - Each task consists of installation part and execution part
2. The DAG defines an environment where it should be executed. 
	- The system creates an environment definition (instructions how to create the environment) using combined installation instructions from each task and pushes it to corresponding nodes
3. User asks to start the experiment. The system transfer this command to corresponding nodes. Each node spins up environment and executors.
4. Each executor starts executing the DAG
5. After executor finishes all the tasks (or fails), it reports results to the system
6. After results received, the system finalizes the corresponding environment

## Assumptions
- Infrastructure has resources (servers/VMs/etc) to host the netunicorn system services ([vocabulary](vocabulary.md): core services)
- Public endpoint of some services of director infrastructure is presented to users (mediator service API)
- Endpoint of gateway service of director infrastructure is available to target (deployment) nodes
- All target infrastructure devices are capable of executing arbitrary Python code (to support arbitrary pipelines) or docker containers
	- Target infrastructure devices that are not capable can use [sidecar pattern](https://docs.microsoft.com/en-us/azure/architecture/patterns/sidecar)
- Target infrastructure is controlled by some deployment system (IT automation software like Ansible, SaltStack, etc.).
	- netunicorn does not present its own deployment system or infrastructure control, and fully relies on existing system via a specific connector

## Coarse architecture of the system
```mermaid
flowchart LR
	subgraph User
		fr[System Frontend]
	end
	
	subgraph Director Infrastructure
		core[Core Services]
	end

	ds[Deployment System]
	
	
	subgraph Node
		subgraph env[Environment]
			ex[Executor]
		end
	end
	
	fr --- core
	core --- ds
	core --- ex
	ds -.- Node
```

As this system is designed to work close to target infrastructure and with many users, most often it would be constantly online and deployed on server-based machine. At the same time, users need to be able to design experiments and tasks even without connection to installation, and easily migrate experiments between installations, therefore a separate user-side module (*frontend*) is required.

As target network infrastructure could be different for different locations, and also usually already controlled by some IT automation software (like Ansible), the system will work via existing deployment systems to deploy user's code. This would allow to not to give direct node access to the system, but leave it to infrastructure administrators only.

As pipelines/DAGs do consists of several steps, these steps execution order should be controlled. It can be done on central server, but that wouldn't work well with bad Internet connection and establish certain requirements to deployment system (like fast transfer of results, etc.). Therefore, the system would use separate 'executors' deployed on nodes to control pipeline execution. In addition, these executors will provide additional capabilities that original deployment system is not able to (like event-exchange system).

Therefore, the system consists of 3 different parts:
- User-side Frontend
- Core services
- Executor

### User-side Frontend
Frontend is a separate module that’s located on a user side. It's a single point of interaction with the system for user.
Frontend:
- contains building blocks for tasks/DAGs
- connects to Core Services to provide users information about available infrastructure
- allows user to interact with system (prepare, start, and cancel experiments, receive status, etc.)
- allows user to attach additional infrastructures to the system
See [Frontend documentation](frontend) for further information.

### Core Services
The core engine is deployed on *system installation location (core).* Usually it would be servers of infrastructure owner (e.g., university, research lab, company) that's relatively close to infrastructure used for experiments (to reduce latency, ensure proper bandwidth, etc.).

The local infrastructure would be controlled by *deployment system*, controlled by administrators. It would be accessible by system engine via a connector.

One of core services (gateway) is always available to Executors via network.

Core services:
- interact with *deployment system* to obtain information about local infrastructure and issue commands to deploy experiments
- prepare environment for user's experiments
- maintain currently running experiments
- provide event exchange support for the experiments
- controls preprocessors for experiments

See [Director documentation](director) for additional information.

### Target infrastructure
Target infrastructure node would contain environment and executor. Executor works on a node inside the *environment* (usually generated by the engine). It receives a DAG and executes it, reports results, sends and receives events. Executor's lifetime is bounded by the Environment.

See [Target documentation](target) for additional information.
