from pydantic import BaseModel


class PipelineResult(BaseModel):
    executor_id: str
    results: bytes
