from typing_extensions import TypedDict


class StopExecutorRequest(TypedDict):
    executor_id: str
    node_name: str
