# Gateway
This service provides an endpoint for executors to request pipelines, send heartbeat messages, and provide execution results.

This service implements a lightweight API over netunicorn database to receive REST requests from executors and provide the next methods:
- Get serialized pipeline for execution
- Post serialized execution result
- Post heartbeat message

# Nodes public endpoint
This service's endpoint is supposed to be available by executors on target nodes.