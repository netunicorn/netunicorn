from __future__ import annotations
from typing import Optional
from dataclasses import dataclass, field
import platform

# TODO: make classes frozen to make hash stable


@dataclass
class EnvironmentDefinition:
    commands: Optional[list[str]] = field(default_factory=list)

    def __hash__(self):
        return hash(tuple(self.commands))

    @classmethod
    def from_json(cls, data: dict) -> EnvironmentDefinition:
        instance = cls.__new__(cls)
        instance.commands = data["commands"]
        return instance

    def __json__(self):
        return {
            "commands": self.commands,
        }


@dataclass
class ShellExecution(EnvironmentDefinition):
    """
    This class represents Environment Definition that's created by executing shell commands.
    """
    @classmethod
    def from_json(cls, data: dict) -> ShellExecution:
        instance = cls.__new__(cls)
        instance.commands = data["commands"]
        return instance


@dataclass
class DockerImage(EnvironmentDefinition):
    """
    This class represents Environment Definition that is created by using a Docker image.
    If image name is not provided, then it would be created automatically
    """
    image: Optional[str] = None
    python_version: str = platform.python_version()

    def __hash__(self):
        if self.image:
            return hash(self.image)

        return hash((self.python_version, tuple(self.commands)))

    def __json__(self):
        return {
            "image": self.image,
            "python_version": self.python_version,
            "commands": self.commands,
        }

    @classmethod
    def from_json(cls, data: dict) -> DockerImage:
        instance = cls.__new__(cls)
        instance.commands = data["commands"]
        instance.image = data["image"]
        instance.python_version = data["python_version"]
        return instance
