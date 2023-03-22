from typing import Optional, TypeAlias

ConnectorContext: TypeAlias = Optional[dict[str, dict[str, str]]]


class ExecutorsCancellationRequest:
    executors: list[str]
    cancellation_context: Optional[dict[str, dict[str, str]]] = None
