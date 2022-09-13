from typing import List, Dict, Union, Set

from netunicorn.base.architecture import Architecture


class Minion:
    def __init__(self, name: str, properties: Dict[str, Union[str, Set[str]]],
                 architecture: Architecture = Architecture.UNKNOWN):
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


class MinionPool:
    """
    Represents a pool of minions.
    # TODO: change representation to support cloud providers
    """

    def __init__(self, minions: List[Minion]):
        self.minions = minions

    def append(self, minion):
        self.minions.append(minion)

    def __str__(self):
        return str(self.minions)

    def __getitem__(self, item):
        return self.minions[item]

    def __len__(self):
        return len(self.minions)

    def __iter__(self):
        return iter(self.minions)

    def __contains__(self, item):
        return item in self.minions

    def __repr__(self):
        return str(self.minions)

    def filter(self, key: str, value: str) -> 'MinionPool':
        return MinionPool([x for x in self.minions if x.check_property(key, value)])

    def take(self, count: int) -> 'MinionPool':
        if count > len(self.minions):
            print(f'Warning: asked for {count} minions, but only {len(self.minions)} available')
            return self
        return MinionPool(self.minions[:count])
