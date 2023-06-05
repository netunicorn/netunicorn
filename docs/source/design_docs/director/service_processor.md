# Processor service
This service monitors responses by executors of currently running experiments and controls the next two issues:
- Updating the Experiment result with results from executors, including timing them out (depending on Experiment settings).
- Controlling currently locked devices participating in experiments