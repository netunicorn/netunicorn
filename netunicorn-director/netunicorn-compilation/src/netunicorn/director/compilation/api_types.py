from pydantic import BaseModel


class CompilationRequest(BaseModel):
    uid: str
    architecture: str
    environment_definition: bytes
    pipeline: bytes
