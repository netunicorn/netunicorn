from typing import List

from netunicorn.base.architecture import Architecture


class Minion:
    def __init__(self, name: str, properties: dict, architecture: Architecture = Architecture.UNKNOWN):
        self.name = name
        self.properties = properties
        self.additional_properties = {}
        self.architecture = architecture

    def __getitem__(self, item):
        return self.properties[item]

    def __setitem__(self, key, value):
        self.properties[key] = value

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
