# Executor
Executor is an agent that's deployed on a target node and executes a pipeline/DAG.

By default, director infrastructure only has access to target nodes via deployment system which capabilities could be different. Therefore, and also to disentangle target nodes from central server to work even in bad network conditions, target nodes would have separate Executor to control DAG execution.

Executor is installed in the Environment distributed to the node together with the pipeline itself and everything that execution of the pipeline needs. 

