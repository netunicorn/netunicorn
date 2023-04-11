from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from itertools import chain, cycle
from typing import Callable, Dict, Iterator, List, Sequence, Union
from uuid import uuid4

import netunicorn

from .architecture import Architecture
from .types import NodeProperty, NodeRepresentation, NodesRepresentation


class Node:
    def __init__(
        self,
        name: str,
        properties: Dict[str, NodeProperty],
        architecture: Architecture = Architecture.UNKNOWN,
    ):
        self.name = name
        self.properties = properties
        self.additional_properties: Dict[str, NodeProperty] = {}
        self.architecture = architecture

    def __getitem__(self, item: str) -> NodeProperty:
        return self.properties.get(item, None)

    def __iter__(self) -> Iterator[NodeProperty]:
        raise TypeError("Node is not iterable")

    def __setitem__(self, key: str, value: NodeProperty) -> None:
        self.properties[key] = value

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Node)
            and self.name == other.name
            and self.properties == other.properties
            and self.additional_properties == other.additional_properties
            and self.architecture == other.architecture
        )

    def __json__(self) -> NodeRepresentation:
        return {
            "name": self.name,
            "properties": self.properties,
            "additional_properties": self.additional_properties,
            "architecture": self.architecture.value,
        }

    @classmethod
    def from_json(cls, data: NodeRepresentation) -> Node:
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
    def __json__(self) -> NodesRepresentation:
        """
        Returns a JSON representation of the object.
        """
        pass

    @staticmethod
    def dispatch_and_deserialize(data: NodesRepresentation) -> Nodes:
        cls: Nodes = getattr(netunicorn.base.nodes, data["node_pool_type"])
        return cls.from_json(data["node_pool_data"])

    @classmethod
    @abstractmethod
    def from_json(
        cls, data: List[Union[NodeRepresentation, NodesRepresentation]]
    ) -> Nodes:
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
    def __getitem__(self, item: int) -> Union[Node, Nodes]:
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
    def set_property(self, name: str, value: NodeProperty) -> Nodes:
        pass


class CountableNodePool(Nodes):
    """
    Represents a typical pool of nodes.
    """

    def __init__(self, nodes: List[Union[Node, Nodes]]):
        self.nodes = nodes

    def __json__(self) -> NodesRepresentation:
        return {
            "node_pool_type": self.__class__.__name__,
            "node_pool_data": [x.__json__() for x in self.nodes],
        }

    @classmethod
    def from_json(
        cls, data: List[Union[NodeRepresentation, NodesRepresentation]]
    ) -> CountableNodePool:
        nodes: List[Union[Node, Nodes]] = []
        for element in data:
            if "node_pool_type" in element:
                # we know this is a NodesRepresentation
                nodes.append(Nodes.dispatch_and_deserialize(element))  # type: ignore
            else:
                nodes.append(Node.from_json(element))
        return cls(nodes)

    def __str__(self) -> str:
        return str(self.nodes)

    def __len__(self) -> int:
        return len(self.nodes)

    def __getitem__(self, key: int) -> Union[Node, Nodes]:
        return self.nodes[key]

    def __setitem__(
        self, key: int, value: Union[Node, CountableNodePool, UncountableNodePool]
    ) -> None:
        self.nodes[key] = value

    def pop(self, index: int) -> Union[Node, Nodes]:
        return self.nodes.pop(index)

    def __repr__(self) -> str:
        return str(self.nodes)

    def filter(self, function: Callable[[Node], bool]) -> CountableNodePool:
        nodes: List[Union[Node, Nodes]] = []
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
        iterator: Iterator[Node] = chain.from_iterable(
            [x] if isinstance(x, Node) else x for x in self.nodes  # type: ignore
        )
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

    def set_property(self, name: str, value: NodeProperty) -> CountableNodePool:
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

    def __init__(self, node_template: List[Node]):
        self._node_template = node_template
        self._nodes = cycle(node_template)

    def __str__(self) -> str:
        return str(
            f"<Uncountable node pool with next node template: {self._node_template}>"
        )

    def __repr__(self) -> str:
        return str(self)

    def __next__(self) -> Node:
        node = deepcopy(next(self._nodes))
        node.name += str(uuid4())
        return node

    def __getitem__(self, key: int) -> Node:
        return self._node_template[key]

    def __setitem__(self, key: int, value: Node) -> None:
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

    def __json__(self) -> NodesRepresentation:
        return {
            "node_pool_type": self.__class__.__name__,
            "node_pool_data": [x.__json__() for x in self._node_template],
        }

    @classmethod
    def from_json(
        cls, data: List[Union[NodeRepresentation, NodesRepresentation]]
    ) -> UncountableNodePool:
        for x in data:
            if "node_pool_type" in x:
                raise ValueError("UncountableNodePool cannot have Nodes as elements.")
        # now we have only NodeRepresentation in the list
        return cls([Node.from_json(x) for x in data])  # type: ignore

    def set_property(self, name: str, value: NodeProperty) -> UncountableNodePool:
        for node in self._node_template:
            node.properties[name] = value
        return self
