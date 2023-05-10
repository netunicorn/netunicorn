from typing import TypedDict


class StopExecutorRequest(TypedDict):
    executor_id: str
    node_name: str
