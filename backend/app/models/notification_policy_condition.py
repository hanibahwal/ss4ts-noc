from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, TypeAlias


class ConditionOperator(StrEnum):
    EQUALS = "eq"
    NOT_EQUALS = "ne"

    IN = "in"
    NOT_IN = "not_in"

    EXISTS = "exists"
    NOT_EXISTS = "not_exists"

    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "lte"

    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"

    REGEX = "regex"


class ConditionGroupOperator(StrEnum):
    ALL = "all"
    ANY = "any"
    NOT = "not"


class PolicyMatchStatus(StrEnum):
    MATCHED = "matched"
    NOT_MATCHED = "not_matched"
    INVALID_POLICY = "invalid_policy"


class NotificationConditionError(
    ValueError
):
    """Invalid notification-policy condition."""


@dataclass(
    frozen=True,
    slots=True,
)
class NotificationCondition:
    field_path: str
    operator: ConditionOperator
    expected: Any = None

    case_sensitive: bool = False

    def __post_init__(self) -> None:
        normalized_path = self.field_path.strip()

        if not normalized_path:
            raise NotificationConditionError(
                "Condition field path must not be empty"
            )

        if normalized_path.startswith("."):
            raise NotificationConditionError(
                "Condition field path cannot start with a dot"
            )

        if normalized_path.endswith("."):
            raise NotificationConditionError(
                "Condition field path cannot end with a dot"
            )

        if ".." in normalized_path:
            raise NotificationConditionError(
                "Condition field path contains an empty segment"
            )

        operators_without_expected = {
            ConditionOperator.EXISTS,
            ConditionOperator.NOT_EXISTS,
        }

        if (
            self.operator
            not in operators_without_expected
            and self.expected is None
        ):
            raise NotificationConditionError(
                f"Operator '{self.operator.value}' "
                "requires an expected value"
            )


NotificationConditionNode: TypeAlias = (
    "NotificationCondition | NotificationConditionGroup"
)


@dataclass(
    frozen=True,
    slots=True,
)
class NotificationConditionGroup:
    operator: ConditionGroupOperator

    children: tuple[
        NotificationConditionNode,
        ...,
    ] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        if not self.children:
            raise NotificationConditionError(
                "Condition group must contain at least one child"
            )

        if (
            self.operator
            is ConditionGroupOperator.NOT
            and len(self.children) != 1
        ):
            raise NotificationConditionError(
                "NOT condition group must contain exactly one child"
            )


@dataclass(
    frozen=True,
    slots=True,
)
class ConditionEvaluation:
    field_path: str
    operator: ConditionOperator

    matched: bool

    expected: Any = None
    actual: Any = None

    reason: str = ""


@dataclass(
    frozen=True,
    slots=True,
)
class PolicyMatchReport:
    policy_id: str

    status: PolicyMatchStatus
    matched: bool

    evaluations: tuple[
        ConditionEvaluation,
        ...,
    ] = field(
        default_factory=tuple
    )

    reason: str = ""
    error: str | None = None


def parse_condition_node(
    payload: dict[str, Any],
) -> NotificationConditionNode:
    if not isinstance(payload, dict):
        raise NotificationConditionError(
            "Condition node must be an object"
        )

    if "field" in payload:
        allowed_keys = {
            "field",
            "operator",
            "value",
            "case_sensitive",
        }

        unknown_keys = (
            set(payload)
            - allowed_keys
        )

        if unknown_keys:
            raise NotificationConditionError(
                "Unknown condition keys: "
                + ", ".join(
                    sorted(unknown_keys)
                )
            )

        field_path = str(
            payload["field"]
        ).strip()

        operator_value = payload.get(
            "operator",
            ConditionOperator.EQUALS.value,
        )

        try:
            operator = ConditionOperator(
                str(operator_value)
            )
        except ValueError as exc:
            raise NotificationConditionError(
                f"Unsupported condition operator: "
                f"{operator_value}"
            ) from exc

        return NotificationCondition(
            field_path=field_path,
            operator=operator,
            expected=payload.get("value"),
            case_sensitive=bool(
                payload.get(
                    "case_sensitive",
                    False,
                )
            ),
        )

    group_keys = [
        key
        for key in (
            ConditionGroupOperator.ALL.value,
            ConditionGroupOperator.ANY.value,
            ConditionGroupOperator.NOT.value,
        )
        if key in payload
    ]

    if len(group_keys) != 1:
        raise NotificationConditionError(
            "Condition group must contain exactly one "
            "of: all, any, not"
        )

    group_key = group_keys[0]

    unknown_keys = (
        set(payload)
        - {group_key}
    )

    if unknown_keys:
        raise NotificationConditionError(
            "Unknown condition group keys: "
            + ", ".join(
                sorted(unknown_keys)
            )
        )

    group_operator = ConditionGroupOperator(
        group_key
    )

    raw_children = payload[group_key]

    if (
        group_operator
        is ConditionGroupOperator.NOT
    ):
        if not isinstance(
            raw_children,
            dict,
        ):
            raise NotificationConditionError(
                "NOT condition must contain one condition object"
            )

        children = (
            parse_condition_node(
                raw_children
            ),
        )

    else:
        if not isinstance(
            raw_children,
            list,
        ):
            raise NotificationConditionError(
                f"'{group_key}' condition must contain a list"
            )

        children = tuple(
            parse_condition_node(item)
            for item in raw_children
        )

    return NotificationConditionGroup(
        operator=group_operator,
        children=children,
    )


def normalize_policy_conditions(
    conditions: dict[str, Any],
) -> dict[str, Any]:
    """
    Convert the early simple policy condition format into the
    canonical recursive condition-tree format.

    Supported legacy fields:
      event_types, severities, states, sources, device_ids,
      site_ids, interface_ids, metric_names and labels.
    """

    if not conditions:
        return {}

    canonical_keys = {
        "field",
        "all",
        "any",
        "not",
    }

    if any(
        key in conditions
        for key in canonical_keys
    ):
        return conditions

    mappings = {
        "event_types": "event_type",
        "severities": "severity",
        "states": "state",
        "sources": "source",
        "device_ids": "device.id",
        "site_ids": "site.id",
        "interface_ids": "interface.id",
        "metric_names": "metric.name",
    }

    nodes: list[dict[str, Any]] = []

    for legacy_key, field_path in mappings.items():
        if legacy_key not in conditions:
            continue

        nodes.append(
            {
                "field": field_path,
                "operator": "in",
                "value": conditions[
                    legacy_key
                ],
            }
        )

    labels = conditions.get(
        "labels"
    )

    if labels is not None:
        if not isinstance(labels, dict):
            raise NotificationConditionError(
                "Legacy labels condition must be an object"
            )

        for label_name, label_value in labels.items():
            nodes.append(
                {
                    "field": (
                        f"labels.{label_name}"
                    ),
                    "operator": "eq",
                    "value": label_value,
                }
            )

    supported_keys = (
        set(mappings)
        | {"labels"}
    )

    unknown_keys = (
        set(conditions)
        - supported_keys
    )

    if unknown_keys:
        raise NotificationConditionError(
            "Unsupported legacy policy condition keys: "
            + ", ".join(
                sorted(unknown_keys)
            )
        )

    if not nodes:
        return {}

    return {
        "all": nodes,
    }
