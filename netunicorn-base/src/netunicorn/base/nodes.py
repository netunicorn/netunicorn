"""
Abstractions for nodes representation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from itertools import chain, count, cycle
from typing import Callable, Dict, Iterable, Iterator, List, Sequence, Set, Union, cast

import netunicorn.base

from .architecture import Architecture
from .environment_definitions import _available_environment_definitions
from .types import NodeProperty, NodeRepresentation, NodesRepresentation


class Node:
    """
    Represents a single node in a pool of nodes.

    :param name: name of the node
    :param properties: custom properties of the node
    :param architecture: node architecture
    """

    def __init__(
        self,
        name: str,
        properties: Dict[str, NodeProperty],
        architecture: Architecture = Architecture.UNKNOWN,
    ):
        self.name: str = name
        """
        Node name.
        """

        self.properties: Dict[str, NodeProperty] = properties
        """
        Node properties. Could be used to store custom information about the node.
        """

        self.additional_properties: Dict[str, NodeProperty] = {}
        """
        Additional node properties, often used for internal purposes and not to be exposed to the user.
        """

        self.architecture: Architecture = architecture
        """
        Node architecture.
        """

        self.available_environments: Set[type] = self._infer_environments()
        """
        Supported environments for the node (see :py:mod:`netunicorn.base.environment_definitions`).
        """

    def _infer_environments(self) -> Set[type]:
        result = set()
        # noinspection PyBroadException
        try:
            environments = self.properties.get(
                "netunicorn-environments", _available_environment_definitions.keys()
            )
            if hasattr(environments, "__iter__"):
                for environment_name in cast(Iterable[str], environments):
                    if environment_name in _available_environment_definitions:
                        result.add(_available_environment_definitions[environment_name])
        except Exception:
            return set(_available_environment_definitions.values())
        return result

    def __getitem__(self, item: str) -> NodeProperty:
        """
        Returns a node property by name.

        :param item: name of the property
        :return: property value
        """
        return self.properties.get(item, None)

    def __iter__(self) -> Iterator[NodeProperty]:
        raise TypeError("Node is not iterable")

    def __setitem__(self, key: str, value: NodeProperty) -> None:
        """
        Sets a node property.

        :param key: name of the property
        :param value: property value
        """
        self.properties[key] = value

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name

    def __eq__(self, other: object) -> bool:
        """
        Checks if two nodes are equal.

        :param other: other node
        :return: True if the nodes have all parameters equal, False otherwise
        """
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
        """
        Returns an instance of the object from a JSON representation.

        :param data: JSON representation of the object
        :return: instance of the object
        """
        instance = cls(
            data["name"], data["properties"], Architecture(data["architecture"])
        )
        instance.additional_properties = data["additional_properties"]
        return instance


class Nodes(ABC):
    """
    A base class that represents a pool of nodes. Not to be used directly, but to be inherited from.
    """

    @abstractmethod
    def __json__(self) -> NodesRepresentation:
        """
        Returns a JSON representation of the object.
        """
        pass

    @staticmethod
    def dispatch_and_deserialize(data: NodesRepresentation) -> Nodes:
        """
        Deserializes a JSON representation of the object and returns an instance of the object.

        :param data: JSON representation of the object
        :return: instance of the object
        """

        cls: Nodes = getattr(netunicorn.base.nodes, data["node_pool_type"])
        return cls.from_json(data["node_pool_data"])

    @classmethod
    @abstractmethod
    def from_json(
        cls, data: List[Union[NodeRepresentation, NodesRepresentation]]
    ) -> Nodes:
        """
        Class-specific implementation of deserialization from JSON.

        :param data: JSON representation of the object
        :return: instance of the object
        """
        pass

    @abstractmethod
    def __str__(self) -> str:
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
        Returns a pool of nodes that match the given filter function.

        :param function: filter function returning True if the node should be included in the result
        :return: pool of nodes
        """
        pass

    @abstractmethod
    def take(self, count: int) -> Sequence[Node]:
        """
        Returns a sequence of nodes consisting of the first `count` nodes.

        :param count: number of nodes to take
        :return: sequence of nodes
        """
        pass

    @abstractmethod
    def skip(self, count: int) -> Nodes:
        """
        Returns a pool of nodes consisting of the nodes after the first 'count' nodes.

        :param count: number of nodes to skip
        :return: pool of nodes
        """
        pass

    @abstractmethod
    def set_property(self, name: str, value: NodeProperty) -> Nodes:
        """
        Sets a property for all nodes in the pool.

        :param name: name of the property
        :param value: property value
        :return: self
        """
        pass


class CountableNodePool(Nodes):
    """
    Represents a pool of nodes that contains a fixed number of nodes.

    :param nodes: list of nodes
    """

    def __init__(self, nodes: List[Union[Node, Nodes]]):
        self.nodes = nodes
        """
        Nodes in the pool.
        """

    def __json__(self) -> NodesRepresentation:
        return {
            "node_pool_type": self.__class__.__name__,
            "node_pool_data": [x.__json__() for x in self.nodes],
        }

    @classmethod
    def from_json(
        cls, data: List[Union[NodeRepresentation, NodesRepresentation]]
    ) -> CountableNodePool:
        """
        Returns an instance of the object from a JSON representation.

        :param data: JSON representation of the object
        :return: instance of the object
        """
        nodes: List[Union[Node, Nodes]] = []
        for element in data:
            if "node_pool_type" in element:
                # we know this is a NodesRepresentation
                nodes_representation_element = cast(NodesRepresentation, element)
                nodes.append(
                    Nodes.dispatch_and_deserialize(nodes_representation_element)
                )
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
        """
        Removes and returns the node at the given index.

        :param index: index of the node to remove
        :return: popped node
        """
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
            cast(
                Iterable[Iterable[Node]],
                ([x] if isinstance(x, Node) else x for x in self.nodes),
            )
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
    | Represents a pool of nodes that is not countable (i.e., contains possibly infinite amount of nodes, e.g. cloud provider).
    | In the current implementation cannot have Nodes as elements.

    :param node_template: list of nodes that will be used as a template for generating new nodes
    """

    def __init__(self, node_template: List[Node]):
        self._node_template = node_template
        """
        Node template used for generating new nodes.
        """

        self._nodes = cycle(node_template)
        """
        An iterator over the node template.
        """

        self._counter = count(start=1, step=1)
        """
        Node name counter.
        """

    def __str__(self) -> str:
        return str(
            f"<Uncountable node pool with next node template: {self._node_template}>"
        )

    def __repr__(self) -> str:
        return str(self)

    def __next__(self) -> Node:
        """
        Generate and returns the next node in the pool.

        :return: next node
        """
        node = deepcopy(next(self._nodes))
        node.name += str(next(self._counter))
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
        node_representation_data = cast(List[NodeRepresentation], data)
        return cls([Node.from_json(x) for x in node_representation_data])

    def set_property(self, name: str, value: NodeProperty) -> UncountableNodePool:
        for node in self._node_template:
            node.properties[name] = value
        return self
