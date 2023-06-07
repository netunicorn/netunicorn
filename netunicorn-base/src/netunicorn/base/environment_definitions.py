"""
Environment definitions to create an environment for a deployment.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass, field
from typing import Dict, List, Optional, cast

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
    """
    Stores a runtime context for a Deployment, such as port mapping or environment variables, that would be available during deployment

    :param ports_mapping: map of ports to be mapped to the host
    :param environment_variables: map of environment variables to be set
    :param additional_arguments: list of additional arguments to be passed to the runtime
    """

    ports_mapping: Dict[int, int] = field(default_factory=dict)
    """
    Desired port mapping (for all protocols)
    """

    environment_variables: Dict[str, str] = field(default_factory=dict)
    """
    Desired values of environment variables
    """

    additional_arguments: List[str] = field(default_factory=list)
    """
    Additional arguments (could be interpreted by runtimes)
    """

    def __json__(self) -> RuntimeContextRepresentation:
        return {
            "ports_mapping": self.ports_mapping,
            "environment_variables": self.environment_variables,
            "additional_arguments": self.additional_arguments,
        }

    @classmethod
    def from_json(cls, data: RuntimeContextRepresentation) -> RuntimeContext:
        """
        Creates RuntimeContext from JSON representation.

        :param data: JSON representation of RuntimeContext
        :return: Deserialized RuntimeContext
        """

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
    """
    A base class for all Environment Definitions.

    :param commands: commands that should be executed to create an environment
    """

    commands: List[str] = field(default_factory=list)
    """
    A list of commands that should be executed to create an environment.
    """

    runtime_context: RuntimeContext = field(default_factory=RuntimeContext)
    """
    Runtime context for this environment definition
    """

    def __hash__(self) -> int:
        return hash(tuple(self.commands))

    @classmethod
    def from_json(
        cls, data: EnvironmentDefinitionRepresentation
    ) -> EnvironmentDefinition:
        """
        Creates EnvironmentDefinition from JSON representation.

        :param data: JSON representation of EnvironmentDefinition
        :return: Deserialized EnvironmentDefinition
        """

        instance = cls.__new__(cls)
        instance.commands = data["commands"]
        return instance

    def __json__(self) -> EnvironmentDefinitionRepresentation:
        return {
            "commands": self.commands,
            "runtime_context": self.runtime_context.__json__(),
        }


@dataclass
class ShellExecution(EnvironmentDefinition):
    """
    This class represents Environment Definition that's created by executing commands in OS's shell.

    :param runtime_context: runtime context for this environment definition
    """

    @classmethod
    def from_json(cls, _data: EnvironmentDefinitionRepresentation) -> ShellExecution:
        """
        Creates ShellExecution from JSON representation.

        :param _data: JSON representation of ShellExecution
        :return: Deserialized ShellExecution
        """

        if "runtime_context" not in _data:
            raise ValueError("runtime_context is missing")
        data = cast(ShellExecutionRepresentation, _data)
        instance = cls.__new__(cls)
        instance.commands = data["commands"]
        instance.runtime_context = RuntimeContext.from_json(data["runtime_context"])
        return instance


@dataclass(frozen=True)
class BuildContext:
    """
    Stores a build context for a Deployment, such as Python version or cloudpickle version, used during deployment

    :param python_version: User's Python version
    :param cloudpickle_version: User's cloudpickle version
    """

    python_version: str = field(default_factory=platform.python_version)
    """
    User's Python version
    """

    cloudpickle_version: Optional[str] = field(
        default_factory=lambda: BuildContext._get_cloudpickle_version()
    )
    """
    User's cloudpickle version
    """

    @staticmethod
    def _get_cloudpickle_version() -> Optional[str]:
        try:
            import cloudpickle

            return cast(str, cloudpickle.__version__)
        except ImportError:
            return None

    def __json__(self) -> BuildContextRepresentation:
        return {
            "python_version": self.python_version,
            "cloudpickle_version": self.cloudpickle_version,
        }

    @classmethod
    def from_json(cls, data: BuildContextRepresentation) -> BuildContext:
        """
        Creates BuildContext from JSON representation.

        :param data: JSON representation of BuildContext
        :return: Deserialized BuildContext
        """

        python_version = data["python_version"]
        cloudpickle_version = data["cloudpickle_version"]
        return cls(
            python_version=python_version, cloudpickle_version=cloudpickle_version
        )


@dataclass
class DockerImage(EnvironmentDefinition):
    """
    | This class represents Environment Definition that is created by using a Docker image.
    | If image name is not provided, then it would be created automatically

    :param image: Docker image name
    :param build_context: build context for this environment definition
    :param runtime_context: runtime context for this environment definition
    """

    image: Optional[str] = None
    """
    Docker image name
    """

    build_context: BuildContext = field(default_factory=BuildContext)
    """
    Build context for this environment definition
    """

    runtime_context: RuntimeContext = field(default_factory=RuntimeContext)
    """
    Runtime context for this environment definition
    """

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
        """
        Creates DockerImage from JSON representation.

        :param _data: JSON representation of DockerImage
        :return: Deserialized DockerImage
        """

        if "image" not in _data:
            raise ValueError("image is missing")
        data = cast(DockerImageRepresentation, _data)
        instance = cls.__new__(cls)
        instance.commands = data["commands"]
        instance.image = data["image"]
        instance.build_context = BuildContext.from_json(data["build_context"])
        instance.runtime_context = RuntimeContext.from_json(data["runtime_context"])
        return instance


_available_environment_definitions = {
    ShellExecution.__name__: ShellExecution,
    DockerImage.__name__: DockerImage,
}
