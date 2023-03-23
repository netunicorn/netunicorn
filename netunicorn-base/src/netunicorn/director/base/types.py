import sys
from typing import Dict, List, Optional

if sys.version_info >= (3, 9):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias


ConnectorContext: TypeAlias = Optional[Dict[str, Dict[str, str]]]


class ExecutorsCancellationRequest:
    executors: List[str]
    cancellation_context: ConnectorContext = None
