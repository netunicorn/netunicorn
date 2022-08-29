from __future__ import annotations
from typing import Optional
from dataclasses import dataclass
import platform


@dataclass
class EnvironmentDefinition:
    commands: Optional[list[str]] = None
    pass


class ShellExecution(EnvironmentDefinition):
    """
    This class represents Environment Definition that's created by executing shell commands.
    """
    pass


class DockerImage(EnvironmentDefinition):
    """
    This class represents Environment Definition that is created by using a Docker image.
    If image name is not provided, then it would be created automatically
    """
    image: Optional[str] = None
    python_version: str = platform.python_version()
