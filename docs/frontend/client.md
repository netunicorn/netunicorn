# Client
Client provides basic abstractions to users that would allow them to define tasks and DAGs based on their requests. Besides that, client also ensures connection to the *director services* of the system, and is responsible for presenting to the user an existing target infrastructure, user-based information (like running DAGs, etc.), ability to run experiments and receive results of the execution (including logs and artifacts). 
In addition to that, the client should also allow user to attach their own infrastructure to the *director services*. This should be done via providing instantiation information to the *director services* about access to this infrastructure

## Functional requirements
Requirements are sorted by importance.
- Client must provide common system program abstractions for Task/DAG creation
- Client must allow user to connect to the *director services*, authenticate, and receive/present information about *target infrastructure*
- Client must allow user to design Experiment and properly choose DAG implementations based on Node information
- Client must allow user to run the Experiment
- Client must provide user information about current experiments
- Client must provide user a way to cancel experiments
- Client must allow user to receive Experiment results (including logs and produced artifacts)
- Client must allow user to manually send and receive events
- Client must allow user to execute DAGs locally using dummy Environment on the localhost
- Client must allow user to provide information about their own *target infrastructure* to attach to the existing system installation
## Non-functional requirements
- Client should correctly process all *director services* responds, including error information
- Client should be lightweight and implemented as Python library without additional services or processes
## Design
Client is a single monolithic Python library that provides needed classes for user's needs. Basic abstraction classes (such as Task, DAG, Experiment, etc.) should be reimported from system-common package (that also would be used by *core services*, and *executor*)