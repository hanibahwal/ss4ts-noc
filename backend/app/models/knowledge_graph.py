from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from math import isfinite
from typing import Any


class NodeType(StrEnum):
    SITE = "site"
    TOWER = "tower"
    DEVICE = "device"
    ROUTER = "router"
    SWITCH = "switch"
    ACCESS_POINT = "access_point"
    INTERFACE = "interface"
    NETWORK_LINK = "network_link"
    CUSTOMER_SERVICE = "customer_service"
    VLAN = "vlan"
    ROUTE = "route"
    UNKNOWN = "unknown"


class RelationshipType(StrEnum):
    CONTAINS = "contains"
    LOCATED_AT = "located_at"
    CONNECTED_TO = "connected_to"
    DEPENDS_ON = "depends_on"
    SERVES = "serves"
    BACKED_UP_BY = "backed_up_by"
    UPLINK_OF = "uplink_of"
    DOWNLINK_OF = "downlink_of"
    MEMBER_OF = "member_of"
    IMPACTS = "impacts"
    UNKNOWN = "unknown"


def _text(
    value: Any,
    default: str = "",
) -> str:
    if value is None:
        return default

    text = str(value).strip()

    return text or default


def _optional_text(
    value: Any,
) -> str | None:
    text = _text(value)

    return text or None


def _number(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return default

    if not isfinite(numeric_value):
        return default

    return numeric_value


def _boolean(
    value: Any,
    default: bool = True,
) -> bool:
    if isinstance(value, bool):
        return value

    if value is None:
        return default

    normalized = str(value).strip().lower()

    if normalized in {
        "true",
        "1",
        "yes",
        "on",
        "enabled",
        "active",
    }:
        return True

    if normalized in {
        "false",
        "0",
        "no",
        "off",
        "disabled",
        "inactive",
    }:
        return False

    return default


def _metadata(
    value: Any,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    return dict(value)


def _normalize_node_type(
    value: Any,
) -> NodeType:
    normalized = _text(
        value,
        NodeType.UNKNOWN,
    ).lower().replace("-", "_")

    aliases = {
        "ap": "access_point",
        "accesspoint": "access_point",
        "link": "network_link",
        "networklink": "network_link",
        "customer": "customer_service",
        "service": "customer_service",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    try:
        return NodeType(normalized)
    except ValueError:
        return NodeType.UNKNOWN


def _normalize_relationship_type(
    value: Any,
) -> RelationshipType:
    normalized = _text(
        value,
        RelationshipType.UNKNOWN,
    ).lower().replace("-", "_")

    aliases = {
        "connected": "connected_to",
        "depends": "depends_on",
        "located": "located_at",
        "backup": "backed_up_by",
        "uplink": "uplink_of",
        "downlink": "downlink_of",
        "member": "member_of",
        "impact": "impacts",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    try:
        return RelationshipType(normalized)
    except ValueError:
        return RelationshipType.UNKNOWN


@dataclass(slots=True)
class KnowledgeNode:
    """
    Canonical entity inside the SS4TS Network Knowledge Graph.

    A node may represent a site, tower, device, interface, link,
    customer service, VLAN, route, or another network-domain object.
    """

    id: str
    type: NodeType
    label: str

    status: str | None = None
    external_id: str | None = None

    site: str | None = None
    location: str | None = None

    active: bool = True
    confidence: float = 1.0

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.id = _text(self.id)
        self.label = _text(self.label)
        self.type = _normalize_node_type(
            self.type
        )

        self.status = _optional_text(
            self.status
        )
        self.external_id = _optional_text(
            self.external_id
        )
        self.site = _optional_text(
            self.site
        )
        self.location = _optional_text(
            self.location
        )

        self.active = _boolean(
            self.active
        )

        self.confidence = round(
            max(
                0.0,
                min(
                    _number(
                        self.confidence,
                        1.0,
                    ),
                    1.0,
                ),
            ),
            4,
        )

        self.metadata = _metadata(
            self.metadata
        )

        if not self.id:
            raise ValueError(
                "KnowledgeNode id must not be empty"
            )

        if not self.label:
            raise ValueError(
                "KnowledgeNode label must not be empty"
            )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> KnowledgeNode:
        if not isinstance(data, dict):
            raise TypeError(
                "KnowledgeNode data must be a dictionary"
            )

        return cls(
            id=_text(
                data.get("id")
                or data.get("node_id")
            ),
            type=_normalize_node_type(
                data.get("type")
                or data.get("node_type")
            ),
            label=_text(
                data.get("label")
                or data.get("name")
                or data.get("identity")
            ),
            status=_optional_text(
                data.get("status")
            ),
            external_id=_optional_text(
                data.get("external_id")
                or data.get("source_id")
            ),
            site=_optional_text(
                data.get("site")
            ),
            location=_optional_text(
                data.get("location")
            ),
            active=_boolean(
                data.get("active"),
                True,
            ),
            confidence=_number(
                data.get("confidence"),
                1.0,
            ),
            metadata=_metadata(
                data.get("metadata")
            ),
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        result = asdict(self)

        result["type"] = self.type.value

        return result


@dataclass(slots=True)
class KnowledgeEdge:
    """
    Directed relationship between two Knowledge Graph nodes.
    """

    id: str
    source_id: str
    target_id: str
    type: RelationshipType

    label: str | None = None
    active: bool = True
    bidirectional: bool = False

    weight: float = 1.0
    confidence: float = 1.0

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.id = _text(self.id)
        self.source_id = _text(
            self.source_id
        )
        self.target_id = _text(
            self.target_id
        )

        self.type = (
            _normalize_relationship_type(
                self.type
            )
        )

        self.label = _optional_text(
            self.label
        )

        self.active = _boolean(
            self.active
        )
        self.bidirectional = _boolean(
            self.bidirectional,
            False,
        )

        self.weight = round(
            max(
                0.0,
                _number(
                    self.weight,
                    1.0,
                ),
            ),
            4,
        )

        self.confidence = round(
            max(
                0.0,
                min(
                    _number(
                        self.confidence,
                        1.0,
                    ),
                    1.0,
                ),
            ),
            4,
        )

        self.metadata = _metadata(
            self.metadata
        )

        if not self.id:
            raise ValueError(
                "KnowledgeEdge id must not be empty"
            )

        if not self.source_id:
            raise ValueError(
                "KnowledgeEdge source_id must not be empty"
            )

        if not self.target_id:
            raise ValueError(
                "KnowledgeEdge target_id must not be empty"
            )

        if self.source_id == self.target_id:
            raise ValueError(
                "KnowledgeEdge self-references are not allowed"
            )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> KnowledgeEdge:
        if not isinstance(data, dict):
            raise TypeError(
                "KnowledgeEdge data must be a dictionary"
            )

        return cls(
            id=_text(
                data.get("id")
                or data.get("edge_id")
            ),
            source_id=_text(
                data.get("source_id")
                or data.get("source")
            ),
            target_id=_text(
                data.get("target_id")
                or data.get("target")
            ),
            type=_normalize_relationship_type(
                data.get("type")
                or data.get("relationship_type")
            ),
            label=_optional_text(
                data.get("label")
            ),
            active=_boolean(
                data.get("active"),
                True,
            ),
            bidirectional=_boolean(
                data.get("bidirectional"),
                False,
            ),
            weight=_number(
                data.get("weight"),
                1.0,
            ),
            confidence=_number(
                data.get("confidence"),
                1.0,
            ),
            metadata=_metadata(
                data.get("metadata")
            ),
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        result = asdict(self)

        result["type"] = self.type.value

        return result


@dataclass(slots=True)
class ImpactPath:
    """
    Ordered dependency or impact traversal through the graph.
    """

    source_id: str
    target_id: str

    node_ids: list[str]
    edge_ids: list[str] = field(
        default_factory=list
    )

    total_weight: float = 0.0
    confidence: float = 1.0
    circular: bool = False

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.source_id = _text(
            self.source_id
        )
        self.target_id = _text(
            self.target_id
        )

        self.node_ids = [
            _text(item)
            for item in self.node_ids
            if _text(item)
        ]

        self.edge_ids = [
            _text(item)
            for item in self.edge_ids
            if _text(item)
        ]

        self.total_weight = round(
            max(
                0.0,
                _number(
                    self.total_weight,
                    0.0,
                ),
            ),
            4,
        )

        self.confidence = round(
            max(
                0.0,
                min(
                    _number(
                        self.confidence,
                        1.0,
                    ),
                    1.0,
                ),
            ),
            4,
        )

        self.circular = _boolean(
            self.circular,
            False,
        )

        self.metadata = _metadata(
            self.metadata
        )

        if not self.source_id:
            raise ValueError(
                "ImpactPath source_id must not be empty"
            )

        if not self.target_id:
            raise ValueError(
                "ImpactPath target_id must not be empty"
            )

        if len(self.node_ids) < 2:
            raise ValueError(
                "ImpactPath requires at least two nodes"
            )

        if self.node_ids[0] != self.source_id:
            raise ValueError(
                "ImpactPath must start with source_id"
            )

        if self.node_ids[-1] != self.target_id:
            raise ValueError(
                "ImpactPath must end with target_id"
            )

        expected_edges = len(
            self.node_ids
        ) - 1

        if (
            self.edge_ids
            and len(self.edge_ids)
            != expected_edges
        ):
            raise ValueError(
                "ImpactPath edge count must equal "
                "node count minus one"
            )

        has_duplicate_nodes = (
            len(set(self.node_ids))
            != len(self.node_ids)
        )

        if (
            has_duplicate_nodes
            and not self.circular
        ):
            raise ValueError(
                "ImpactPath contains a cycle but "
                "circular is false"
            )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> ImpactPath:
        if not isinstance(data, dict):
            raise TypeError(
                "ImpactPath data must be a dictionary"
            )

        return cls(
            source_id=_text(
                data.get("source_id")
                or data.get("source")
            ),
            target_id=_text(
                data.get("target_id")
                or data.get("target")
            ),
            node_ids=list(
                data.get("node_ids")
                or data.get("nodes")
                or []
            ),
            edge_ids=list(
                data.get("edge_ids")
                or data.get("edges")
                or []
            ),
            total_weight=_number(
                data.get("total_weight"),
                0.0,
            ),
            confidence=_number(
                data.get("confidence"),
                1.0,
            ),
            circular=_boolean(
                data.get("circular"),
                False,
            ),
            metadata=_metadata(
                data.get("metadata")
            ),
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class GraphSnapshot:
    """
    Immutable-in-time representation of the known network graph.
    """

    nodes: list[KnowledgeNode] = field(
        default_factory=list
    )
    edges: list[KnowledgeEdge] = field(
        default_factory=list
    )

    generated_at: str | None = None
    version: str = "1.0"

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.nodes = [
            item
            if isinstance(
                item,
                KnowledgeNode,
            )
            else KnowledgeNode.from_dict(
                item
            )
            for item in self.nodes
            if isinstance(
                item,
                (
                    KnowledgeNode,
                    dict,
                ),
            )
        ]

        self.edges = [
            item
            if isinstance(
                item,
                KnowledgeEdge,
            )
            else KnowledgeEdge.from_dict(
                item
            )
            for item in self.edges
            if isinstance(
                item,
                (
                    KnowledgeEdge,
                    dict,
                ),
            )
        ]

        self.generated_at = _optional_text(
            self.generated_at
        )
        self.version = _text(
            self.version,
            "1.0",
        )
        self.metadata = _metadata(
            self.metadata
        )

        node_ids = [
            node.id
            for node in self.nodes
        ]

        edge_ids = [
            edge.id
            for edge in self.edges
        ]

        if len(node_ids) != len(
            set(node_ids)
        ):
            raise ValueError(
                "GraphSnapshot contains duplicate node ids"
            )

        if len(edge_ids) != len(
            set(edge_ids)
        ):
            raise ValueError(
                "GraphSnapshot contains duplicate edge ids"
            )

        known_node_ids = set(node_ids)

        for edge in self.edges:
            if edge.source_id not in known_node_ids:
                raise ValueError(
                    "GraphSnapshot edge references "
                    f"unknown source node: {edge.source_id}"
                )

            if edge.target_id not in known_node_ids:
                raise ValueError(
                    "GraphSnapshot edge references "
                    f"unknown target node: {edge.target_id}"
                )

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    @property
    def active_nodes(self) -> list[KnowledgeNode]:
        return [
            node
            for node in self.nodes
            if node.active
        ]

    @property
    def active_edges(self) -> list[KnowledgeEdge]:
        return [
            edge
            for edge in self.edges
            if edge.active
        ]

    def get_node(
        self,
        node_id: str,
    ) -> KnowledgeNode | None:
        normalized_id = _text(
            node_id
        )

        return next(
            (
                node
                for node in self.nodes
                if node.id == normalized_id
            ),
            None,
        )

    def outgoing_edges(
        self,
        node_id: str,
    ) -> list[KnowledgeEdge]:
        normalized_id = _text(
            node_id
        )

        return [
            edge
            for edge in self.edges
            if edge.source_id == normalized_id
        ]

    def incoming_edges(
        self,
        node_id: str,
    ) -> list[KnowledgeEdge]:
        normalized_id = _text(
            node_id
        )

        return [
            edge
            for edge in self.edges
            if edge.target_id == normalized_id
        ]

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> GraphSnapshot:
        if not isinstance(data, dict):
            raise TypeError(
                "GraphSnapshot data must be a dictionary"
            )

        return cls(
            nodes=list(
                data.get("nodes")
                or []
            ),
            edges=list(
                data.get("edges")
                or []
            ),
            generated_at=_optional_text(
                data.get("generated_at")
            ),
            version=_text(
                data.get("version"),
                "1.0",
            ),
            metadata=_metadata(
                data.get("metadata")
            ),
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "nodes": [
                node.to_dict()
                for node in self.nodes
            ],
            "edges": [
                edge.to_dict()
                for edge in self.edges
            ],
            "generated_at":
                self.generated_at,
            "version": self.version,
            "metadata": dict(
                self.metadata
            ),
            "node_count":
                self.node_count,
            "edge_count":
                self.edge_count,
        }


def normalize_graph(
    data: GraphSnapshot | dict[str, Any] | None,
) -> GraphSnapshot:
    """
    Normalize graph input into one canonical GraphSnapshot instance.
    """

    if isinstance(
        data,
        GraphSnapshot,
    ):
        return data

    if data is None:
        return GraphSnapshot()

    if not isinstance(data, dict):
        raise TypeError(
            "Knowledge Graph input must be a dictionary"
        )

    return GraphSnapshot.from_dict(
        data
    )
