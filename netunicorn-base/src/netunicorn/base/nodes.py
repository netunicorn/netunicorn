from __future__ import annotations

from copy import deepcopy

from itertools import cycle, chain
from uuid import uuid4
from typing import Dict, Set, Union, Iterator, Callable, Sequence

import netunicorn
from netunicorn.base.architecture import Architecture

from abc import ABC, abstractmethod


class Node:
    def __init__(
        self,
        name: str,
        properties: Dict[str, Union[str, int, float, Set[str]]],
        architecture: Architecture = Architecture.UNKNOWN,
    ):
        self.name = name
        self.properties = properties
        self.additional_properties = {}
        self.architecture = architecture

    def __getitem__(self, item: str) -> Union[str, Set[str], None]:
        return self.properties.get(item, None)

    def __setitem__(self, key: str, value: Union[str, Set[str]]):
        self.properties[key] = value

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name

    def __eq__(self, other) -> bool:
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
    def from_json(cls, data: dict) -> Node:
        instance = cls(
            data["name"], data["properties"], Architecture(data["architecture"])
        )
        instance.additional_properties = data["additional_properties"]
        return instance


class Nodes(ABC):
    """
    Represents a pool of nodes.
    """

    @abstractmethod
    def __json__(self) -> dict:
        """
        Returns a JSON representation of the object.
        Required to have the next structure:
        {
            "node_pool_type": self.__class__.__name__,
            "node_pool_data": { ... }
        }
        """
        pass

    @staticmethod
    def dispatch_and_deserialize(data: dict) -> Nodes:
        return getattr(netunicorn.base.nodes, data["node_pool_type"]).from_json(
            data["node_pool_data"]
        )

    @classmethod
    @abstractmethod
    def from_json(cls, data: dict) -> Nodes:
        """
        Accepts a JSON representation of the object (from "node_pool_data") and returns an instance of the object.
        """
        pass

    @abstractmethod
    def __str__(self) -> str:
        """
        Returns a string representation of the object.
        """
        pass

    @abstractmethod
    def __len__(self) -> int:
        pass

    @abstractmethod
    def __getitem__(self, item) -> Node:
        pass

    @abstractmethod
    def filter(self, function: Callable[[Node], bool]) -> Nodes:
        """
        Returns a pool of nodes that match the given filter.
        """
        pass

    @abstractmethod
    def take(self, count: int) -> Sequence[Node]:
        """
        Returns a sequence of nodes consisting of the first n nodes.
        """
        pass

    @abstractmethod
    def skip(self, count: int) -> Nodes:
        """
        Returns a pool of nodes consisting of the nodes after the first n nodes.
        """
        pass

    @abstractmethod
    def set_property(self, name: str, value: Union[str, Set[str]]) -> Nodes:
        pass


class CountableNodePool(Nodes):
    """
    Represents a typical pool of nodes.
    """

    def __init__(self, nodes: list[Union[Node, Nodes]]):
        self.nodes = nodes

    def __json__(self):
        return {
            "node_pool_type": self.__class__.__name__,
            "node_pool_data": [x.__json__() for x in self.nodes],
        }

    @classmethod
    def from_json(cls, data: list[dict]) -> CountableNodePool:
        nodes = []
        for element in data:
            if "node_pool_type" in element:
                nodes.append(Nodes.dispatch_and_deserialize(element))
            else:
                nodes.append(Node.from_json(element))
        return cls(nodes)

    def __str__(self) -> str:
        return str(self.nodes)

    def __len__(self) -> int:
        return len(self.nodes)

    def __getitem__(self, key: int) -> Union[Node, UncountableNodePool, CountableNodePool]:
        return self.nodes[key]

    def __setitem__(self, key: int, value: Union[Node, CountableNodePool, UncountableNodePool]):
        self.nodes[key] = value

    def __iter__(self) -> Iterator[Union[Node, UncountableNodePool, CountableNodePool]]:
        return iter(self.nodes)

    def pop(self, index: int):
        self.nodes.pop(index)

    def __repr__(self) -> str:
        return str(self.nodes)

    def filter(self, function: Callable[[Node], bool]) -> CountableNodePool:
        nodes = []
        for node in self.nodes:
            if isinstance(node, Node):
                if function(node):
                    nodes.append(node)
            else:
                filtered_nodes = node.filter(function)
                if len(filtered_nodes) > 0:
                    nodes.append(filtered_nodes)
        return CountableNodePool(nodes)

    def take(self, count: int) -> Sequence[Node]:
        iterator = chain.from_iterable([x] if isinstance(x, Node) else x for x in self.nodes)
        nodes = []
        for _ in range(count):
            try:
                nodes.append(next(iterator))
            except StopIteration:
                break
        return nodes

    def skip(self, count: int) -> CountableNodePool:
        if count > len(self.nodes):
            print(
                f"Warning: asked to skip {count} nodes, but pool length is {len(self.nodes)}. "
                f"Returning empty pool."
            )
            return CountableNodePool([])
        return CountableNodePool(self.nodes[count:])

    def set_property(self, name: str, value: Union[str, Set[str]]) -> CountableNodePool:
        for node in self.nodes:
            if isinstance(node, Node):
                node.properties[name] = value
            else:
                node.set_property(name, value)
        return self


class UncountableNodePool(Nodes):
    """
    Represents a pool of nodes that is not countable (e.g., dynamic pools of cloud providers).
    In the current implementation cannot have Nodes as elements.
    """

    def __init__(self, node_template: list[Node]):
        self._node_template = node_template
        self._nodes = cycle(node_template)

    def __str__(self) -> str:
        return str(
            f"<Uncountable node pool with next node template: {self._node_template}>"
        )

    def __repr__(self) -> str:
        return str(self)

    def __iter__(self):
        return self

    def __next__(self) -> Node:
        node = deepcopy(next(self._nodes))
        node.name += str(uuid4())
        return node

    def __getitem__(self, key: int) -> Node:
        return self._node_template[key]

    def __setitem__(self, key: int, value: Node):
        self._node_template[key] = value

    def __len__(self) -> int:
        return len(self._node_template)

    def filter(self, function: Callable[[Node], bool]) -> UncountableNodePool:
        return UncountableNodePool([x for x in self._node_template if function(x)])

    def take(self, count: int) -> Sequence[Node]:
        nodes = []
        for _ in range(count):
            nodes.append(next(self))
        return nodes

    def skip(self, count: int) -> UncountableNodePool:
        count = count % len(self._node_template)
        for _ in range(count):
            next(self._nodes)
        return self

    def __json__(self) -> dict:
        return {
            "node_pool_type": self.__class__.__name__,
            "node_pool_data": [x.__json__() for x in self._node_template],
        }
        pass

    @classmethod
    def from_json(cls, data: dict) -> UncountableNodePool:
        return cls([Node.from_json(x) for x in data])

    def set_property(
        self, name: str, value: Union[str, Set[str]]
    ) -> UncountableNodePool:
        for node in self._node_template:
            node.properties[name] = value
        return self
