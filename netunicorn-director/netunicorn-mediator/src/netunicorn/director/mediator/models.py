from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class CancellationRequest(BaseModel):
    executors: List[str]
    cancellation_context: Optional[dict[str, dict[str, str]]] = None


# Web Models
class WebPipeline(BaseModel):
    short_name: str
    full_name: str
    description: str


class WebNode(BaseModel):
    name: str
    properties: Dict[str, Any] = {}
    additional_properties: Dict[str, Any] = {}
    architecture: str


class WebExperimentMapping(BaseModel):
    pipeline: WebPipeline
    nodes: List[WebNode]
