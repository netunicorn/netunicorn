from __future__ import annotations

import platform
from dataclasses import dataclass, field
from typing import Optional


# TODO: make classes frozen to make hash stable


@dataclass
class RuntimeContext:
    ports_mapping: dict[int, int] = field(default_factory=dict)
    environment_variables: dict[str, str] = field(default_factory=dict)
    additional_arguments: list[str] = field(default_factory=list)

    def __json__(self):
        return {
            "ports_mapping": self.ports_mapping,
            "environment_variables": self.environment_variables,
            "additional_arguments": self.additional_arguments,
        }

    @classmethod
    def from_json(cls, data: dict) -> RuntimeContext:
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

    runtime_context: RuntimeContext = field(default_factory=RuntimeContext)

    def __json__(self):
        return {
            "commands": self.commands,
            "runtime_context": self.runtime_context,
        }

    @classmethod
    def from_json(cls, data: dict) -> ShellExecution:
        instance = cls.__new__(cls)
        instance.commands = data["commands"]
        instance.runtime_context = RuntimeContext.from_json(data["runtime_context"])
        return instance


@dataclass(frozen=True)
class BuildContext:
    """ """

    python_version: str = field(default_factory=lambda: platform.python_version())
    cloudpickle_version: Optional[str] = field(
        default_factory=lambda: BuildContext._get_cloudpickle_version()
    )

    @staticmethod
    def _get_cloudpickle_version() -> Optional[str]:
        try:
            import cloudpickle

            return cloudpickle.__version__
        except ImportError:
            return None

    def __json__(self):
        return {
            "python_version": self.python_version,
            "cloudpickle_version": self.cloudpickle_version,
        }

    @classmethod
    def from_json(cls, data: dict) -> BuildContext:
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

    def __hash__(self):
        if self.image:
            return hash(self.image)

        return hash(
            (
                self.build_context.python_version,
                self.build_context.cloudpickle_version,
                tuple(self.commands),
            )
        )

    def __json__(self):
        return {
            "image": self.image,
            "build_context": self.build_context.__json__(),
            "runtime_context": self.runtime_context.__json__(),
            "commands": self.commands,
        }

    @classmethod
    def from_json(cls, data: dict) -> DockerImage:
        instance = cls.__new__(cls)
        instance.commands = data["commands"]
        instance.image = data["image"]
        instance.build_context = BuildContext.from_json(data["build_context"])
        instance.runtime_context = RuntimeContext.from_json(data["runtime_context"])
        return instance
