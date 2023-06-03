# Unresolved questions
This file contains questions to discuss that influence or roadblock design decisions
- Pipelines or DAGs?
	- There're 2 ways to implement ordered structure of tasks - pipelines and DAGs
	- DAGs are direct acyclic graphs, where each stage has a set of prerequisite stages and would start executing only when all prerequisite stages would finish executing
		- DAGs would allow more complex scenarios
		- DAGs would be harder to implement
		- with DAGs (possibly) it would be harder to control synchronization of tasks that should be started together
			- check this
			- probably not true: if implement as 'check all available tasks after end of each task', it would be the same as pipelines' stages
		- DAG probably would be more complex for user to use
			- Implement DAG and Pipeline as simplified version of DAG?
	- Pipelines are simplified versions of DAGs. They have only a single starting point, several stages, and ending point. Stages are ordered, and each stage can have multiple tasks inside. The next stage starts when all tasks of previous stage are finished.
		- Pipelines would be easier to implement
		- Stages are very direct and all tasks within one stage 
		- I like this more
- Flow control design. If a user wants to 'close the loop' - process the data and react to some events or conditions - how to provide these capabilities?
	1. Allow to receive and control things on user's laptop and spawn events to the system
		- Pros:
			- Easy debugging
			- Update code without restarting experiments
		- Cons:
			- Network latency is not 0
			- User's laptop should be working during the experiment and be available
	2. Spawn preprocessing/control pipeline on a director and fire events from there
		- Pros:
			- Supports long experiments
			- Latency is smaller
			- More stable
			- Vertically scalable
		- Cons:
			- No debugging
			- Cannot be hot-swapped during the experiment
	3. Can we do 2nd approach with mix of 1st? Like attaching user's own laptop as infrastructure and spawn preprocessing there?
		- It will allow debugging and switch to master process when release deployment