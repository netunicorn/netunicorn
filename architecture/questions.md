# Unresolved questions
This file contains questions to discuss that influence or roadblock design decisions
- Pipelines or DAGs?
	- There're 2 ways to implement ordered structure of tasks - pipelines and DAGs
	- DAGs are direct acyclic graphs, where each stage has a set of prerequisite stages and would start executing only when all prerequisite stages would finish executing
		- DAGs would allow more complex scenarios
		- DAGs would be harder to implement
		- with DAGs (possibly) it would be harder to control synchronization of tasks that should be started together
			- check this
	- Pipelines are simplified versions of DAGs. They have only a single starting point, several stages, and ending point. Stages are ordered, and each stage can have multiple tasks inside. The next stage starts when all tasks of previous stage are finished.
		- Pipelines would be easier to implement
		- Stages are very direct and all tasks within one stage 