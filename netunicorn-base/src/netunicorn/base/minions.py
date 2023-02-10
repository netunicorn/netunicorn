from __future__ import annotations

from typing import Dict, List, Set, Union, Iterator

from netunicorn.base.architecture import Architecture


class Minion:
    def __init__(
        self,
        name: str,
        properties: Dict[str, Union[str, Set[str]]],
        architecture: Architecture = Architecture.UNKNOWN,
    ):
        self.name = name
        self.properties = properties
        self.additional_properties = {}
        self.architecture = architecture

    def __getitem__(self, item):
        return self.properties[item]

    def __setitem__(self, key: str, value: Union[str, Set[str]]):
        self.properties[key] = value

    def check_property(self, key: str, value: str) -> bool:
        if key not in self.properties:
            return False
        self_value = self.properties[key]

        if isinstance(self_value, str):
            return self_value == value

        if isinstance(self_value, set):
            return value in self_value

        return False

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    def __eq__(self, other):
        return (
            self.name == other.name
            and self.properties == other.properties
            and self.additional_properties == other.additional_properties
            and self.architecture == other.architecture
        )

    def __json__(self) -> dict:
        return {
            "name": self.name,
            "properties": self.properties,
            "additional_properties": self.additional_properties,
            "architecture": self.architecture.value,
        }

    @classmethod
    def from_json(cls, data: dict) -> Minion:
        instance = cls(
            data["name"], data["properties"], Architecture(data["architecture"])
        )
        instance.additional_properties = data["additional_properties"]
        return instance


class MinionPool:
    """
    Represents a pool of minions.
    # TODO: change representation to support cloud providers
    """

    def __init__(self, minions: List[Minion]):
        self.minions = minions

    def append(self, minion) -> MinionPool:
        self.minions.append(minion)
        return self

    def __json__(self):
        return [x.__json__() for x in self.minions]

    @classmethod
    def from_json(cls, data: dict):
        return cls([Minion.from_json(x) for x in data])

    def __str__(self) -> str:
        return str(self.minions)

    def __getitem__(self, key: Union[slice, int]) -> Union[Minion, MinionPool]:
        if isinstance(key, slice):
            return MinionPool(self.minions[key])
        return self.minions[key]

    def __len__(self) -> int:
        return len(self.minions)

    def __iter__(self) -> Iterator[Minion]:
        return iter(self.minions)

    def __contains__(self, item) -> bool:
        return item in self.minions

    def __repr__(self) -> str:
        return str(self.minions)

    def filter(self, key: str, value: str) -> MinionPool:
        return MinionPool([x for x in self.minions if x.check_property(key, value)])

    def take(self, count: int) -> MinionPool:
        if count > len(self.minions):
            print(
                f"Warning: asked for {count} minions, but only {len(self.minions)} available"
            )
            return self
        return MinionPool(self.minions[:count])

    def skip(self, count: int) -> MinionPool:
        if count > len(self.minions):
            print(
                f"Warning: asked to skip {count} minions, but only {len(self.minions)} available"
            )
            return self
        return MinionPool(self.minions[count:])
