from __future__ import annotations

import platform
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .types import (
    BuildContextRepresentation,
    DockerImageRepresentation,
    EnvironmentDefinitionRepresentation,
    RuntimeContextRepresentation,
    ShellExecutionRepresentation,
)

# TODO: make classes frozen to make hash stable


@dataclass
class RuntimeContext:
    ports_mapping: Dict[int, int] = field(default_factory=dict)
    environment_variables: Dict[str, str] = field(default_factory=dict)
    additional_arguments: List[str] = field(default_factory=list)

    def __json__(self) -> RuntimeContextRepresentation:
        return {
            "ports_mapping": self.ports_mapping,
            "environment_variables": self.environment_variables,
            "additional_arguments": self.additional_arguments,
        }

    @classmethod
    def from_json(cls, data: RuntimeContextRepresentation) -> RuntimeContext:
        ports_mapping = data["ports_mapping"]
        environment_variables = data["environment_variables"]
        additional_arguments = data["additional_arguments"]
        return cls(
            ports_mapping=ports_mapping,
            environment_variables=environment_variables,
            additional_arguments=additional_arguments,
        )


@dataclass
class EnvironmentDefinition:
    commands: List[str] = field(default_factory=list)

    def __hash__(self) -> int:
        return hash(tuple(self.commands))

    @classmethod
    def from_json(
        cls, data: EnvironmentDefinitionRepresentation
    ) -> EnvironmentDefinition:
        instance = cls.__new__(cls)
        instance.commands = data["commands"]
        return instance

    def __json__(self) -> EnvironmentDefinitionRepresentation:
        return {
            "commands": self.commands,
        }


@dataclass
class ShellExecution(EnvironmentDefinition):
    """
    This class represents Environment Definition that's created by executing shell commands.
    """

    runtime_context: RuntimeContext = field(default_factory=RuntimeContext)

    def __json__(self) -> ShellExecutionRepresentation:
        return {
            "commands": self.commands,
            "runtime_context": self.runtime_context.__json__(),
        }

    @classmethod
    def from_json(cls, _data: EnvironmentDefinitionRepresentation) -> ShellExecution:
        if "runtime_context" not in _data:
            raise ValueError("runtime_context is missing")
        data: ShellExecutionRepresentation = _data  # type: ignore
        instance = cls.__new__(cls)
        instance.commands = data["commands"]
        instance.runtime_context = RuntimeContext.from_json(data["runtime_context"])
        return instance


@dataclass(frozen=True)
class BuildContext:
    """ """

    python_version: str = field(default_factory=platform.python_version)
    cloudpickle_version: Optional[str] = field(
        default_factory=lambda: BuildContext._get_cloudpickle_version()
    )

    @staticmethod
    def _get_cloudpickle_version() -> Optional[str]:
        try:
            import cloudpickle

            return cloudpickle.__version__  # type: ignore
        except ImportError:
            return None

    def __json__(self) -> BuildContextRepresentation:
        return {
            "python_version": self.python_version,
            "cloudpickle_version": self.cloudpickle_version,
        }

    @classmethod
    def from_json(cls, data: BuildContextRepresentation) -> BuildContext:
        python_version = data["python_version"]
        cloudpickle_version = data["cloudpickle_version"]
        return cls(
            python_version=python_version, cloudpickle_version=cloudpickle_version
        )


@dataclass
class DockerImage(EnvironmentDefinition):
    """
    This class represents Environment Definition that is created by using a Docker image.
    If image name is not provided, then it would be created automatically
    """

    image: Optional[str] = None
    build_context: BuildContext = field(default_factory=BuildContext)
    runtime_context: RuntimeContext = field(default_factory=RuntimeContext)

    def __hash__(self) -> int:
        if self.image:
            return hash(self.image)

        return hash(
            (
                self.build_context.python_version,
                self.build_context.cloudpickle_version,
                tuple(self.commands),
            )
        )

    def __json__(self) -> DockerImageRepresentation:
        return {
            "image": self.image,
            "build_context": self.build_context.__json__(),
            "runtime_context": self.runtime_context.__json__(),
            "commands": self.commands,
        }

    @classmethod
    def from_json(cls, _data: EnvironmentDefinitionRepresentation) -> DockerImage:
        if "image" not in _data:
            raise ValueError("image is missing")
        data: DockerImageRepresentation = _data  # type: ignore
        instance = cls.__new__(cls)
        instance.commands = data["commands"]
        instance.image = data["image"]
        instance.build_context = BuildContext.from_json(data["build_context"])
        instance.runtime_context = RuntimeContext.from_json(data["runtime_context"])
        return instance
