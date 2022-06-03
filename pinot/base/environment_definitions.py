from __future__ import annotations
from typing import List
from .task import Task


class EnvironmentDefinition:
    def add_requirements(self, task: Task) -> EnvironmentDefinition:
        raise NotImplementedError


class ShellExecution(EnvironmentDefinition):
    """
    This class represents Environment Definition that's created by executing shell commands.
    """

    def __init__(self):
        self.commands: List[str] = []

    def add_requirements(self, task: Task) -> EnvironmentDefinition:
        self.commands.extend(task.requirements)
        return self


class DockerImage(EnvironmentDefinition):
    """
    This class represents Environment Definition that is created by using a Docker image.
    TODO: add possibility to add commands and create new image from defined with these commands executed
    """
    def __init__(self, image: str):
        self.image = image

    def add_requirements(self, task: Task) -> EnvironmentDefinition:
        return self
