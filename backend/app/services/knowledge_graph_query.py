from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from app.models.knowledge_graph import (
    GraphSnapshot,
    ImpactPath,
    KnowledgeEdge,
    KnowledgeNode,
    RelationshipType,
)


Direction = Literal[
    "outgoing",
    "incoming",
    "both",
]


@dataclass(slots=True, frozen=True)
class TraversalStep:
    """
    One graph traversal step from a node through an edge.
    """

    source_id: str
    target_id: str
    edge_id: str
    relationship: RelationshipType
    depth: int


def _normalize_relationships(
    relationships: (
        Iterable[
            RelationshipType | str
        ]
        | None
    ),
) -> set[RelationshipType] | None:
    if relationships is None:
        return None

    normalized: set[
        RelationshipType
    ] = set()

    for item in relationships:
        if isinstance(
            item,
            RelationshipType,
        ):
            normalized.add(item)
            continue

        try:
            normalized.add(
                RelationshipType(
                    str(item).strip().lower()
                )
            )
        except ValueError:
            continue

    return normalized


class KnowledgeGraphQuery:
    """
    Safe query and traversal engine for GraphSnapshot.

    The engine performs no network I/O and does not mutate the supplied
    graph. All traversals have explicit depth and path limits.
    """

    def __init__(
        self,
        graph: GraphSnapshot,
    ) -> None:
        if not isinstance(
            graph,
            GraphSnapshot,
        ):
            raise TypeError(
                "KnowledgeGraphQuery requires "
                "a GraphSnapshot"
            )

        self.graph = graph

        self._nodes = {
            node.id: node
            for node in graph.nodes
        }

        self._edges = {
            edge.id: edge
            for edge in graph.edges
        }

        self._outgoing: dict[
            str,
            list[KnowledgeEdge],
        ] = {
            node_id: []
            for node_id in self._nodes
        }

        self._incoming: dict[
            str,
            list[KnowledgeEdge],
        ] = {
            node_id: []
            for node_id in self._nodes
        }

        for edge in graph.edges:
            self._outgoing[
                edge.source_id
            ].append(edge)

            self._incoming[
                edge.target_id
            ].append(edge)

    def _require_node(
        self,
        node_id: str,
    ) -> KnowledgeNode:
        node = self._nodes.get(
            str(node_id).strip()
        )

        if node is None:
            raise KeyError(
                f"Unknown graph node: {node_id}"
            )

        return node

    @staticmethod
    def _validate_direction(
        direction: Direction,
    ) -> Direction:
        if direction not in {
            "outgoing",
            "incoming",
            "both",
        }:
            raise ValueError(
                "direction must be outgoing, "
                "incoming or both"
            )

        return direction

    def node(
        self,
        node_id: str,
    ) -> KnowledgeNode:
        return self._require_node(
            node_id
        )

    def edge(
        self,
        edge_id: str,
    ) -> KnowledgeEdge:
        edge = self._edges.get(
            str(edge_id).strip()
        )

        if edge is None:
            raise KeyError(
                f"Unknown graph edge: {edge_id}"
            )

        return edge

    def _adjacent_steps(
        self,
        node_id: str,
        *,
        direction: Direction,
        relationships: (
            set[RelationshipType]
            | None
        ),
        include_inactive: bool,
        depth: int,
    ) -> list[TraversalStep]:
        self._require_node(node_id)
        self._validate_direction(
            direction
        )

        steps: list[
            TraversalStep
        ] = []

        if direction in {
            "outgoing",
            "both",
        }:
            for edge in self._outgoing[
                node_id
            ]:
                if (
                    not include_inactive
                    and not edge.active
                ):
                    continue

                if (
                    relationships is not None
                    and edge.type
                    not in relationships
                ):
                    continue

                steps.append(
                    TraversalStep(
                        source_id=node_id,
                        target_id=edge.target_id,
                        edge_id=edge.id,
                        relationship=edge.type,
                        depth=depth,
                    )
                )

                if edge.bidirectional:
                    steps.append(
                        TraversalStep(
                            source_id=edge.target_id,
                            target_id=node_id,
                            edge_id=edge.id,
                            relationship=edge.type,
                            depth=depth,
                        )
                    )

        if direction in {
            "incoming",
            "both",
        }:
            for edge in self._incoming[
                node_id
            ]:
                if (
                    not include_inactive
                    and not edge.active
                ):
                    continue

                if (
                    relationships is not None
                    and edge.type
                    not in relationships
                ):
                    continue

                steps.append(
                    TraversalStep(
                        source_id=node_id,
                        target_id=edge.source_id,
                        edge_id=edge.id,
                        relationship=edge.type,
                        depth=depth,
                    )
                )

                if edge.bidirectional:
                    steps.append(
                        TraversalStep(
                            source_id=edge.source_id,
                            target_id=node_id,
                            edge_id=edge.id,
                            relationship=edge.type,
                            depth=depth,
                        )
                    )

        unique: dict[
            tuple[str, str],
            TraversalStep,
        ] = {}

        for step in steps:
            key = (
                step.target_id,
                step.edge_id,
            )

            unique[key] = step

        return list(
            unique.values()
        )

    def neighbors(
        self,
        node_id: str,
        *,
        direction: Direction = "both",
        relationships: (
            Iterable[
                RelationshipType | str
            ]
            | None
        ) = None,
        include_inactive: bool = False,
    ) -> list[KnowledgeNode]:
        relationship_filter = (
            _normalize_relationships(
                relationships
            )
        )

        steps = self._adjacent_steps(
            node_id,
            direction=direction,
            relationships=
                relationship_filter,
            include_inactive=
                include_inactive,
            depth=1,
        )

        result: dict[
            str,
            KnowledgeNode,
        ] = {}

        for step in steps:
            node = self._nodes[
                step.target_id
            ]

            if (
                include_inactive
                or node.active
            ):
                result[node.id] = node

        return list(
            result.values()
        )

    def dependencies(
        self,
        node_id: str,
        *,
        recursive: bool = False,
        max_depth: int = 10,
    ) -> list[KnowledgeNode]:
        if recursive:
            return self.traverse(
                node_id,
                direction="outgoing",
                relationships={
                    RelationshipType.DEPENDS_ON,
                },
                max_depth=max_depth,
            )

        return self.neighbors(
            node_id,
            direction="outgoing",
            relationships={
                RelationshipType.DEPENDS_ON,
            },
        )

    def dependents(
        self,
        node_id: str,
        *,
        recursive: bool = False,
        max_depth: int = 10,
    ) -> list[KnowledgeNode]:
        if recursive:
            return self.traverse(
                node_id,
                direction="incoming",
                relationships={
                    RelationshipType.DEPENDS_ON,
                },
                max_depth=max_depth,
            )

        return self.neighbors(
            node_id,
            direction="incoming",
            relationships={
                RelationshipType.DEPENDS_ON,
            },
        )

    def traverse(
        self,
        start_id: str,
        *,
        direction: Direction = "outgoing",
        relationships: (
            Iterable[
                RelationshipType | str
            ]
            | None
        ) = None,
        max_depth: int = 10,
        include_start: bool = False,
        include_inactive: bool = False,
    ) -> list[KnowledgeNode]:
        self._require_node(start_id)

        if max_depth < 0:
            raise ValueError(
                "max_depth must be zero "
                "or greater"
            )

        relationship_filter = (
            _normalize_relationships(
                relationships
            )
        )

        visited = {
            start_id,
        }

        queue = deque([
            (
                start_id,
                0,
            ),
        ])

        result: list[
            KnowledgeNode
        ] = []

        if include_start:
            result.append(
                self._nodes[start_id]
            )

        while queue:
            current_id, depth = (
                queue.popleft()
            )

            if depth >= max_depth:
                continue

            steps = self._adjacent_steps(
                current_id,
                direction=direction,
                relationships=
                    relationship_filter,
                include_inactive=
                    include_inactive,
                depth=depth + 1,
            )

            for step in steps:
                if (
                    step.target_id
                    in visited
                ):
                    continue

                target = self._nodes[
                    step.target_id
                ]

                if (
                    not include_inactive
                    and not target.active
                ):
                    continue

                visited.add(
                    step.target_id
                )

                result.append(target)

                queue.append(
                    (
                        step.target_id,
                        depth + 1,
                    )
                )

        return result

    def shortest_path(
        self,
        source_id: str,
        target_id: str,
        *,
        direction: Direction = "both",
        relationships: (
            Iterable[
                RelationshipType | str
            ]
            | None
        ) = None,
        max_depth: int = 20,
        include_inactive: bool = False,
    ) -> ImpactPath | None:
        self._require_node(source_id)
        self._require_node(target_id)

        if source_id == target_id:
            raise ValueError(
                "source_id and target_id "
                "must be different"
            )

        if max_depth < 1:
            raise ValueError(
                "max_depth must be at least 1"
            )

        relationship_filter = (
            _normalize_relationships(
                relationships
            )
        )

        queue = deque([
            (
                source_id,
                [source_id],
                [],
                0.0,
                1.0,
            ),
        ])

        visited = {
            source_id,
        }

        while queue:
            (
                current_id,
                node_path,
                edge_path,
                total_weight,
                confidence,
            ) = queue.popleft()

            depth = len(edge_path)

            if depth >= max_depth:
                continue

            steps = self._adjacent_steps(
                current_id,
                direction=direction,
                relationships=
                    relationship_filter,
                include_inactive=
                    include_inactive,
                depth=depth + 1,
            )

            for step in steps:
                next_id = step.target_id

                if next_id in node_path:
                    continue

                target_node = self._nodes[
                    next_id
                ]

                if (
                    not include_inactive
                    and not target_node.active
                ):
                    continue

                edge = self._edges[
                    step.edge_id
                ]

                next_nodes = [
                    *node_path,
                    next_id,
                ]

                next_edges = [
                    *edge_path,
                    edge.id,
                ]

                next_weight = (
                    total_weight
                    + edge.weight
                )

                next_confidence = (
                    confidence
                    * edge.confidence
                    * target_node.confidence
                )

                if next_id == target_id:
                    return ImpactPath(
                        source_id=source_id,
                        target_id=target_id,
                        node_ids=next_nodes,
                        edge_ids=next_edges,
                        total_weight=
                            next_weight,
                        confidence=round(
                            next_confidence,
                            4,
                        ),
                    )

                if next_id in visited:
                    continue

                visited.add(next_id)

                queue.append(
                    (
                        next_id,
                        next_nodes,
                        next_edges,
                        next_weight,
                        next_confidence,
                    )
                )

        return None

    def all_paths(
        self,
        source_id: str,
        target_id: str,
        *,
        direction: Direction = "outgoing",
        relationships: (
            Iterable[
                RelationshipType | str
            ]
            | None
        ) = None,
        max_depth: int = 10,
        max_paths: int = 100,
        include_inactive: bool = False,
    ) -> list[ImpactPath]:
        self._require_node(source_id)
        self._require_node(target_id)

        if source_id == target_id:
            raise ValueError(
                "source_id and target_id "
                "must be different"
            )

        if max_depth < 1:
            raise ValueError(
                "max_depth must be at least 1"
            )

        if max_paths < 1:
            raise ValueError(
                "max_paths must be at least 1"
            )

        relationship_filter = (
            _normalize_relationships(
                relationships
            )
        )

        paths: list[
            ImpactPath
        ] = []

        stack = [
            (
                source_id,
                [source_id],
                [],
                0.0,
                1.0,
            ),
        ]

        while (
            stack
            and len(paths) < max_paths
        ):
            (
                current_id,
                node_path,
                edge_path,
                total_weight,
                confidence,
            ) = stack.pop()

            if len(edge_path) >= max_depth:
                continue

            steps = self._adjacent_steps(
                current_id,
                direction=direction,
                relationships=
                    relationship_filter,
                include_inactive=
                    include_inactive,
                depth=len(edge_path) + 1,
            )

            for step in reversed(steps):
                next_id = step.target_id

                if next_id in node_path:
                    continue

                target_node = self._nodes[
                    next_id
                ]

                if (
                    not include_inactive
                    and not target_node.active
                ):
                    continue

                edge = self._edges[
                    step.edge_id
                ]

                next_nodes = [
                    *node_path,
                    next_id,
                ]

                next_edges = [
                    *edge_path,
                    edge.id,
                ]

                next_weight = (
                    total_weight
                    + edge.weight
                )

                next_confidence = (
                    confidence
                    * edge.confidence
                    * target_node.confidence
                )

                if next_id == target_id:
                    paths.append(
                        ImpactPath(
                            source_id=
                                source_id,
                            target_id=
                                target_id,
                            node_ids=
                                next_nodes,
                            edge_ids=
                                next_edges,
                            total_weight=
                                next_weight,
                            confidence=round(
                                next_confidence,
                                4,
                            ),
                        )
                    )

                    if (
                        len(paths)
                        >= max_paths
                    ):
                        break

                    continue

                stack.append(
                    (
                        next_id,
                        next_nodes,
                        next_edges,
                        next_weight,
                        next_confidence,
                    )
                )

        return paths

    def blast_radius(
        self,
        node_id: str,
        *,
        max_depth: int = 10,
        include_inactive: bool = False,
    ) -> list[KnowledgeNode]:
        """
        Return nodes affected if node_id fails.

        If A DEPENDS_ON B, failure of B affects A, therefore dependency
        impact is traversed in the incoming direction.
        """

        return self.traverse(
            node_id,
            direction="incoming",
            relationships={
                RelationshipType.DEPENDS_ON,
                RelationshipType.IMPACTS,
            },
            max_depth=max_depth,
            include_inactive=
                include_inactive,
        )

    def impact_paths(
        self,
        node_id: str,
        *,
        max_depth: int = 10,
        max_paths_per_target: int = 10,
    ) -> list[ImpactPath]:
        affected = self.blast_radius(
            node_id,
            max_depth=max_depth,
        )

        result: list[
            ImpactPath
        ] = []

        for target in affected:
            paths = self.all_paths(
                node_id,
                target.id,
                direction="incoming",
                relationships={
                    RelationshipType.DEPENDS_ON,
                    RelationshipType.IMPACTS,
                },
                max_depth=max_depth,
                max_paths=
                    max_paths_per_target,
            )

            result.extend(paths)

        return result

    def connected_components(
        self,
        *,
        relationships: (
            Iterable[
                RelationshipType | str
            ]
            | None
        ) = None,
        include_inactive: bool = False,
    ) -> list[list[KnowledgeNode]]:
        relationship_filter = (
            _normalize_relationships(
                relationships
            )
        )

        remaining = {
            node_id
            for node_id, node
            in self._nodes.items()
            if (
                include_inactive
                or node.active
            )
        }

        components: list[
            list[KnowledgeNode]
        ] = []

        while remaining:
            start_id = next(
                iter(remaining)
            )

            component_ids = {
                start_id,
            }

            queue = deque([
                start_id,
            ])

            remaining.remove(
                start_id
            )

            while queue:
                current_id = (
                    queue.popleft()
                )

                steps = self._adjacent_steps(
                    current_id,
                    direction="both",
                    relationships=
                        relationship_filter,
                    include_inactive=
                        include_inactive,
                    depth=1,
                )

                for step in steps:
                    target_id = (
                        step.target_id
                    )

                    if (
                        target_id
                        not in remaining
                    ):
                        continue

                    target_node = self._nodes[
                        target_id
                    ]

                    if (
                        not include_inactive
                        and not target_node.active
                    ):
                        continue

                    remaining.remove(
                        target_id
                    )

                    component_ids.add(
                        target_id
                    )

                    queue.append(
                        target_id
                    )

            components.append([
                self._nodes[node_id]
                for node_id
                in component_ids
            ])

        return sorted(
            components,
            key=len,
            reverse=True,
        )
