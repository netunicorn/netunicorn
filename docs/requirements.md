# System requirements
In this document function and non-functional requirements are listed. Each requirement is described in a list, and requirement comments are sublists.

## Functional requirements
1. The system must provide a way to define tasks, pipelines/DAGs, and map them to nodes to execute.
2. The system must work with both physical and cloud infrastructures and provide Node (end-host + switch) abstraction to the user.
3. The system must take user-defined pipeline and pass it to nodes to execute, and collect results and logs afterwards.
	1. Do not collect data by default, because it's traffic-consuming (therefore can add noise to experiment) and not always needed.
4. The system must allow to specify different task implementations for different architectures. The resulting pipeline/DAG mapped to a certain host must contain only the instructions for this certain host and architecture.
5. The system must allow to attach user-specific infrastructure that would be available to the user only, together with system-level infrastructure attached by administrators. 
6. The system must support event-based interaction between nodes for synchronization and control purposes. The node can send events to itself (to control parallel pipelines/DAGs) or other nodes.
7. The system must automatically generate environment for pipeline/DAG execution and distribute it to the nodes.
8. The system must allow user authentication/authorization via different methods (including LDAP)
9. The system must allow administrators to attach Experiment preprocessors (arbitrary code). Preprocessor receives an Experiment and returns an Experiment. Administrators can define preprocessors to react to deployment (add nodes to allow-list), log information, etc.


## Non-functional requirements
1. The system should be easy to deploy
	1. As mostly it would be deployed by other people and organizations
2. Running experiments processing should be reliable
	1. It's more important to guarantee that current experiments would finish successfully than to allow to add one more experiment
3. The system should treat each node as unstable, potentially low-end device with bad Internet connection. The experiment execution should be reliable.
4. The system should minimize interference to running experiments on nodes with additional traffic or anything. Experiments purity can be broken by such traffic.
5. The system should ensure that pipeline/DAG execution on the node is as fast as it's possible and there's only a small downtime between tasks execution
