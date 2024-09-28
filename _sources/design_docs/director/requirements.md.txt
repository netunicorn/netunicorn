# Requirements
This document describes functional and non-functional requirements to core services
## Functional requirements
- The services must receive user-defined Experiment (consisting of mapping of DAGs to hosts) and process it
	- The services must create an appropriate environment to each of such mappings, that must containt executor and everything that executor needs
	- The services must distribute created environments to corresponding nodes
	- The services must allow to start experiment execution - spin up all environments on corresponding nodes and provide dynamic information (if needed)
- The services must support different deployment systems and use them as information source about infrastructure
- The services must support experiment execution by checking if nodes are still alive, and receiving results of the execution
- The services must provide all needed information about user's objects (experiments, statuses, infrastructure info) to the user via Frontend
	- The services must store information about running Experiments
	- The services must dynamically retranslate infrastructure information from deployment systema
- The services must allow executors exchange with events 
- The services must allow administrators of the system to add Experiment preprocessors
- The services must maintain user's authentication and authorization
- The services must allow user to dynamically add target infrastructure using pre-defined connectors
## Non-functional requirements
- Services, responsible for supporting running experiments, should be fast and stable
- The system should be easy to deploy
- Services, working with users, should be stable and correctly retranslate all problems and errors of users' requests
- Services for environment preparation should be horizontally scalable