import sys
from typing import Dict, List, Optional

if sys.version_info >= (3, 9):
    from typing import TypeAlias, TypedDict
else:
    from typing_extensions import TypeAlias, TypedDict


ConnectorContext: TypeAlias = Optional[Dict[str, Dict[str, str]]]


class ExecutorsCancellationRequest(TypedDict):
    executors: List[str]
    cancellation_context: ConnectorContext
