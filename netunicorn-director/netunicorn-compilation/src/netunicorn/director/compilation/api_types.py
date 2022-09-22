from pydantic import BaseModel


class CompilationRequest(BaseModel):
    experiment_id: str
    compilation_id: str
    architecture: str
    environment_definition: dict
    pipeline: bytes
