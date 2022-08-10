from __future__ import annotations
from typing import List, Optional
from .task import Task


class EnvironmentDefinition:
    pass


class ShellExecution(EnvironmentDefinition):
    """
    This class represents Environment Definition that's created by executing shell commands.
    """
    pass


class DockerImage(EnvironmentDefinition):
    """
    This class represents Environment Definition that is created by using a Docker image.
    """
    def __init__(self, image: Optional[str] = None):
        """
        Initialize DockerImage with an image name.
        :param image: image name. If not provided, image would be created automatically.
        """
        self.image = image
