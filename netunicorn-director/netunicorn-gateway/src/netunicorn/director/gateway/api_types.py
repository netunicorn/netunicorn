from typing import Optional

from pydantic import BaseModel


class ExecutionGraphResult(BaseModel):
    executor_id: str
    results: bytes
    state: Optional[int] = None
