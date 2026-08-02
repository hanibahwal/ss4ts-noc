from __future__ import annotations

import re

from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.events.notification_event import (
    NotificationEvent,
)
from app.models.notification import (
    NotificationPolicy,
)
from app.models.notification_policy_condition import (
    ConditionEvaluation,
    ConditionGroupOperator,
    ConditionOperator,
    NotificationCondition,
    NotificationConditionError,
    NotificationConditionGroup,
    NotificationConditionNode,
    PolicyMatchReport,
    PolicyMatchStatus,
    normalize_policy_conditions,
    parse_condition_node,
)


_MISSING = object()


class ConditionEvaluationError(
    RuntimeError
):
    """Condition could not be evaluated safely."""


@dataclass(
    frozen=True,
    slots=True,
)
class _NodeEvaluation:
    matched: bool

    evaluations: tuple[
        ConditionEvaluation,
        ...,
    ]


def _normalize_scalar(
    value: Any,
    *,
    case_sensitive: bool,
) -> Any:
    if isinstance(value, Enum):
        value = value.value

    if (
        isinstance(value, str)
        and not case_sensitive
    ):
        return value.casefold()

    return value


def _normalize_collection(
    value: Any,
    *,
    case_sensitive: bool,
) -> Any:
    if isinstance(value, dict):
        return {
            _normalize_scalar(
                key,
                case_sensitive=case_sensitive,
            ): _normalize_collection(
                item,
                case_sensitive=case_sensitive,
            )
            for key, item in value.items()
        }

    if isinstance(
        value,
        (list, tuple, set, frozenset),
    ):
        return [
            _normalize_collection(
                item,
                case_sensitive=case_sensitive,
            )
            for item in value
        ]

    return _normalize_scalar(
        value,
        case_sensitive=case_sensitive,
    )


def _number(
    value: Any,
) -> float:
    if isinstance(value, bool):
        raise ConditionEvaluationError(
            "Boolean values cannot be used "
            "for numeric comparison"
        )

    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ConditionEvaluationError(
            f"Value is not numeric: {value!r}"
        ) from exc


def _resolve_field(
    payload: dict[str, Any],
    field_path: str,
) -> Any:
    current: Any = payload

    for segment in field_path.split("."):
        if isinstance(current, dict):
            if segment not in current:
                return _MISSING

            current = current[segment]
            continue

        if isinstance(current, (list, tuple)):
            try:
                index = int(segment)
            except ValueError:
                return _MISSING

            if (
                index < 0
                or index >= len(current)
            ):
                return _MISSING

            current = current[index]
            continue

        return _MISSING

    return current


def _compare(
    condition: NotificationCondition,
    actual: Any,
) -> tuple[bool, str]:
    operator = condition.operator

    if operator is ConditionOperator.EXISTS:
        matched = actual is not _MISSING

        return (
            matched,
            (
                "Field exists"
                if matched
                else "Field does not exist"
            ),
        )

    if operator is ConditionOperator.NOT_EXISTS:
        matched = actual is _MISSING

        return (
            matched,
            (
                "Field does not exist"
                if matched
                else "Field exists"
            ),
        )

    if actual is _MISSING:
        return (
            False,
            "Field does not exist",
        )

    expected = _normalize_collection(
        condition.expected,
        case_sensitive=(
            condition.case_sensitive
        ),
    )

    normalized_actual = _normalize_collection(
        actual,
        case_sensitive=(
            condition.case_sensitive
        ),
    )

    if operator is ConditionOperator.EQUALS:
        matched = (
            normalized_actual
            == expected
        )

        return (
            matched,
            (
                "Values are equal"
                if matched
                else "Values are not equal"
            ),
        )

    if operator is ConditionOperator.NOT_EQUALS:
        matched = (
            normalized_actual
            != expected
        )

        return (
            matched,
            (
                "Values are different"
                if matched
                else "Values are equal"
            ),
        )

    if operator in {
        ConditionOperator.IN,
        ConditionOperator.NOT_IN,
    }:
        if not isinstance(
            expected,
            (
                list,
                tuple,
                set,
                frozenset,
            ),
        ):
            raise ConditionEvaluationError(
                f"Operator '{operator.value}' "
                "requires an array value"
            )

        included = (
            normalized_actual
            in expected
        )

        matched = (
            included
            if operator
            is ConditionOperator.IN
            else not included
        )

        return (
            matched,
            (
                "Value is included"
                if included
                else "Value is not included"
            ),
        )

    if operator in {
        ConditionOperator.GREATER_THAN,
        ConditionOperator.GREATER_THAN_OR_EQUAL,
        ConditionOperator.LESS_THAN,
        ConditionOperator.LESS_THAN_OR_EQUAL,
    }:
        actual_number = _number(
            normalized_actual
        )

        expected_number = _number(
            expected
        )

        if (
            operator
            is ConditionOperator.GREATER_THAN
        ):
            matched = (
                actual_number
                > expected_number
            )

        elif (
            operator
            is ConditionOperator
            .GREATER_THAN_OR_EQUAL
        ):
            matched = (
                actual_number
                >= expected_number
            )

        elif (
            operator
            is ConditionOperator.LESS_THAN
        ):
            matched = (
                actual_number
                < expected_number
            )

        else:
            matched = (
                actual_number
                <= expected_number
            )

        return (
            matched,
            (
                "Numeric comparison matched"
                if matched
                else "Numeric comparison did not match"
            ),
        )

    if operator is ConditionOperator.CONTAINS:
        try:
            matched = (
                expected
                in normalized_actual
            )
        except TypeError as exc:
            raise ConditionEvaluationError(
                "Actual value does not support "
                "the contains operator"
            ) from exc

        return (
            matched,
            (
                "Actual value contains expected value"
                if matched
                else "Actual value does not contain expected value"
            ),
        )

    if operator in {
        ConditionOperator.STARTS_WITH,
        ConditionOperator.ENDS_WITH,
    }:
        if not isinstance(
            normalized_actual,
            str,
        ):
            raise ConditionEvaluationError(
                f"Operator '{operator.value}' "
                "requires a string field"
            )

        if not isinstance(expected, str):
            raise ConditionEvaluationError(
                f"Operator '{operator.value}' "
                "requires a string expected value"
            )

        if (
            operator
            is ConditionOperator.STARTS_WITH
        ):
            matched = (
                normalized_actual
                .startswith(expected)
            )

        else:
            matched = (
                normalized_actual
                .endswith(expected)
            )

        return (
            matched,
            (
                "String comparison matched"
                if matched
                else "String comparison did not match"
            ),
        )

    if operator is ConditionOperator.REGEX:
        if not isinstance(actual, str):
            raise ConditionEvaluationError(
                "Regex operator requires a string field"
            )

        if not isinstance(
            condition.expected,
            str,
        ):
            raise ConditionEvaluationError(
                "Regex operator requires a string pattern"
            )

        flags = (
            0
            if condition.case_sensitive
            else re.IGNORECASE
        )

        try:
            matched = (
                re.search(
                    condition.expected,
                    actual,
                    flags,
                )
                is not None
            )
        except re.error as exc:
            raise ConditionEvaluationError(
                f"Invalid regular expression: {exc}"
            ) from exc

        return (
            matched,
            (
                "Regular expression matched"
                if matched
                else "Regular expression did not match"
            ),
        )

    raise ConditionEvaluationError(
        f"Unsupported operator: {operator.value}"
    )


class NotificationConditionMatcher:
    """
    Evaluate recursive policy-condition trees against
    canonical NotificationEvent objects.

    This service performs no persistence and sends no messages.
    """

    def evaluate_condition(
        self,
        condition: NotificationCondition,
        event_payload: dict[str, Any],
    ) -> ConditionEvaluation:
        actual = _resolve_field(
            event_payload,
            condition.field_path,
        )

        matched, reason = _compare(
            condition,
            actual,
        )

        return ConditionEvaluation(
            field_path=condition.field_path,
            operator=condition.operator,
            matched=matched,
            expected=condition.expected,
            actual=(
                None
                if actual is _MISSING
                else actual
            ),
            reason=reason,
        )

    def evaluate_node(
        self,
        node: NotificationConditionNode,
        event_payload: dict[str, Any],
    ) -> _NodeEvaluation:
        if isinstance(
            node,
            NotificationCondition,
        ):
            evaluation = self.evaluate_condition(
                node,
                event_payload,
            )

            return _NodeEvaluation(
                matched=evaluation.matched,
                evaluations=(
                    evaluation,
                ),
            )

        child_results = tuple(
            self.evaluate_node(
                child,
                event_payload,
            )
            for child in node.children
        )

        evaluations = tuple(
            evaluation
            for result in child_results
            for evaluation in result.evaluations
        )

        if (
            node.operator
            is ConditionGroupOperator.ALL
        ):
            matched = all(
                result.matched
                for result in child_results
            )

        elif (
            node.operator
            is ConditionGroupOperator.ANY
        ):
            matched = any(
                result.matched
                for result in child_results
            )

        else:
            matched = not (
                child_results[0].matched
            )

        return _NodeEvaluation(
            matched=matched,
            evaluations=evaluations,
        )

    def match(
        self,
        *,
        policy: NotificationPolicy,
        event: NotificationEvent,
    ) -> PolicyMatchReport:
        if not policy.enabled:
            return PolicyMatchReport(
                policy_id=policy.policy_id,
                status=(
                    PolicyMatchStatus
                    .NOT_MATCHED
                ),
                matched=False,
                reason="Policy is disabled",
            )

        if not policy.conditions:
            return PolicyMatchReport(
                policy_id=policy.policy_id,
                status=PolicyMatchStatus.MATCHED,
                matched=True,
                reason=(
                    "Policy contains no conditions "
                    "and therefore matches all events"
                ),
            )

        try:
            normalized_conditions = (
                normalize_policy_conditions(
                    policy.conditions
                )
            )

            if not normalized_conditions:
                return PolicyMatchReport(
                    policy_id=policy.policy_id,
                    status=(
                        PolicyMatchStatus
                        .MATCHED
                    ),
                    matched=True,
                    reason=(
                        "Policy contains no effective conditions"
                    ),
                )

            condition_tree = parse_condition_node(
                normalized_conditions
            )

            event_payload = event.to_payload()

            result = self.evaluate_node(
                condition_tree,
                event_payload,
            )

        except (
            NotificationConditionError,
            ConditionEvaluationError,
            TypeError,
            ValueError,
        ) as exc:
            return PolicyMatchReport(
                policy_id=policy.policy_id,
                status=(
                    PolicyMatchStatus
                    .INVALID_POLICY
                ),
                matched=False,
                reason=(
                    "Policy conditions could not be evaluated"
                ),
                error=str(exc),
            )

        failed_count = sum(
            1
            for evaluation in result.evaluations
            if not evaluation.matched
        )

        if result.matched:
            reason = (
                "All required policy conditions matched"
            )

            status = PolicyMatchStatus.MATCHED

        else:
            reason = (
                f"Policy did not match; "
                f"{failed_count} condition evaluation(s) failed"
            )

            status = (
                PolicyMatchStatus.NOT_MATCHED
            )

        return PolicyMatchReport(
            policy_id=policy.policy_id,
            status=status,
            matched=result.matched,
            evaluations=result.evaluations,
            reason=reason,
        )


def match_notification_policy(
    *,
    policy: NotificationPolicy,
    event: NotificationEvent,
) -> PolicyMatchReport:
    return NotificationConditionMatcher().match(
        policy=policy,
        event=event,
    )
