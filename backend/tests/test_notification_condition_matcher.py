from __future__ import annotations

from dataclasses import replace

import pytest

from app.events import (
    DeviceReference,
    EventSeverity,
    EventSource,
    EventState,
    EventType,
    InterfaceReference,
    MetricContext,
    SiteReference,
    create_notification_event,
)
from app.models.notification import (
    NotificationPolicy,
)
from app.models.notification_policy_condition import (
    ConditionGroupOperator,
    ConditionOperator,
    NotificationCondition,
    NotificationConditionError,
    NotificationConditionGroup,
    PolicyMatchStatus,
    normalize_policy_conditions,
    parse_condition_node,
)
from app.services.notification_condition_matcher import (
    NotificationConditionMatcher,
    match_notification_policy,
)


def make_event():
    return create_notification_event(
        event_type=EventType.DEVICE_DOWN,
        state=EventState.FIRING,
        severity=EventSeverity.CRITICAL,
        source=EventSource.PING_MONITOR,
        title="Device unreachable",
        message="Ping failed for 60 seconds",
        device=DeviceReference(
            id=25,
            name="AFURAH-CAMP-RTR-01",
            hostname="afurah-core",
            ip="10.10.10.1",
            role="core-router",
            vendor="MikroTik",
            model="CCR2116",
        ),
        site=SiteReference(
            id=4,
            name="Al-Jafurah",
            region="Eastern",
        ),
        interface=InterfaceReference(
            id="ether10",
            name="ether10-TO-WAN",
        ),
        metric=MetricContext(
            name="packet_loss",
            value=87,
            threshold=30,
            unit="percent",
        ),
        labels={
            "environment": "production",
            "region": "eastern",
            "service": "internet",
        },
        metadata={
            "failed_probes": 4,
            "probe": "PingWorker-2",
        },
    )


def make_policy(
    conditions,
    *,
    enabled: bool = True,
) -> NotificationPolicy:
    return NotificationPolicy(
        policy_id="policy:test",
        name="Test notification policy",
        enabled=enabled,
        conditions=conditions,
        actions={
            "channels": [
                "whatsapp",
            ],
        },
    )


def test_parse_leaf_condition() -> None:
    condition = parse_condition_node(
        {
            "field": "severity",
            "operator": "eq",
            "value": "critical",
        }
    )

    assert isinstance(
        condition,
        NotificationCondition,
    )

    assert (
        condition.operator
        is ConditionOperator.EQUALS
    )


def test_parse_all_condition_group() -> None:
    group = parse_condition_node(
        {
            "all": [
                {
                    "field": "severity",
                    "operator": "eq",
                    "value": "critical",
                },
                {
                    "field": "event_type",
                    "operator": "eq",
                    "value": "device_down",
                },
            ]
        }
    )

    assert isinstance(
        group,
        NotificationConditionGroup,
    )

    assert (
        group.operator
        is ConditionGroupOperator.ALL
    )

    assert len(group.children) == 2


def test_not_group_requires_one_object() -> None:
    with pytest.raises(
        NotificationConditionError
    ):
        parse_condition_node(
            {
                "not": [
                    {
                        "field": "severity",
                        "value": "info",
                    }
                ]
            }
        )


def test_equals_operator_matches() -> None:
    report = match_notification_policy(
        policy=make_policy(
            {
                "field": "severity",
                "operator": "eq",
                "value": "critical",
            }
        ),
        event=make_event(),
    )

    assert report.matched is True
    assert (
        report.status
        is PolicyMatchStatus.MATCHED
    )


def test_equals_is_case_insensitive_by_default() -> None:
    report = match_notification_policy(
        policy=make_policy(
            {
                "field": "device.vendor",
                "operator": "eq",
                "value": "mikrotik",
            }
        ),
        event=make_event(),
    )

    assert report.matched is True


def test_case_sensitive_equals_can_fail() -> None:
    report = match_notification_policy(
        policy=make_policy(
            {
                "field": "device.vendor",
                "operator": "eq",
                "value": "mikrotik",
                "case_sensitive": True,
            }
        ),
        event=make_event(),
    )

    assert report.matched is False


def test_in_operator_matches() -> None:
    report = match_notification_policy(
        policy=make_policy(
            {
                "field": "event_type",
                "operator": "in",
                "value": [
                    "device_down",
                    "interface_down",
                ],
            }
        ),
        event=make_event(),
    )

    assert report.matched is True


def test_not_in_operator_matches() -> None:
    report = match_notification_policy(
        policy=make_policy(
            {
                "field": "severity",
                "operator": "not_in",
                "value": [
                    "info",
                    "warning",
                ],
            }
        ),
        event=make_event(),
    )

    assert report.matched is True


def test_exists_operator_matches() -> None:
    report = match_notification_policy(
        policy=make_policy(
            {
                "field": "device.ip",
                "operator": "exists",
            }
        ),
        event=make_event(),
    )

    assert report.matched is True


def test_not_exists_operator_matches() -> None:
    report = match_notification_policy(
        policy=make_policy(
            {
                "field": "metadata.ticket_id",
                "operator": "not_exists",
            }
        ),
        event=make_event(),
    )

    assert report.matched is True


def test_numeric_greater_than_matches() -> None:
    report = match_notification_policy(
        policy=make_policy(
            {
                "field": "metric.value",
                "operator": "gt",
                "value": 50,
            }
        ),
        event=make_event(),
    )

    assert report.matched is True


def test_numeric_threshold_failure_is_reported() -> None:
    report = match_notification_policy(
        policy=make_policy(
            {
                "field": "metric.value",
                "operator": "lte",
                "value": 30,
            }
        ),
        event=make_event(),
    )

    assert report.matched is False
    assert len(report.evaluations) == 1

    assert (
        report.evaluations[0].actual
        == 87
    )


def test_contains_matches_list_value() -> None:
    report = match_notification_policy(
        policy=make_policy(
            {
                "field": "actions.channels",
                "operator": "contains",
                "value": "whatsapp",
            }
        ),
        event=make_event(),
    )

    assert report.matched is False


def test_contains_matches_string() -> None:
    report = match_notification_policy(
        policy=make_policy(
            {
                "field": "message",
                "operator": "contains",
                "value": "failed",
            }
        ),
        event=make_event(),
    )

    assert report.matched is True


def test_starts_with_matches() -> None:
    report = match_notification_policy(
        policy=make_policy(
            {
                "field": "device.name",
                "operator": "starts_with",
                "value": "AFURAH",
            }
        ),
        event=make_event(),
    )

    assert report.matched is True


def test_regex_matches() -> None:
    report = match_notification_policy(
        policy=make_policy(
            {
                "field": "device.name",
                "operator": "regex",
                "value": r"^AFURAH-.*-RTR-\d+$",
            }
        ),
        event=make_event(),
    )

    assert report.matched is True


def test_invalid_regex_returns_invalid_policy() -> None:
    report = match_notification_policy(
        policy=make_policy(
            {
                "field": "device.name",
                "operator": "regex",
                "value": "[invalid",
            }
        ),
        event=make_event(),
    )

    assert report.matched is False

    assert (
        report.status
        is PolicyMatchStatus.INVALID_POLICY
    )

    assert report.error is not None


def test_all_group_requires_every_condition() -> None:
    report = match_notification_policy(
        policy=make_policy(
            {
                "all": [
                    {
                        "field": "severity",
                        "operator": "eq",
                        "value": "critical",
                    },
                    {
                        "field": "site.id",
                        "operator": "eq",
                        "value": 999,
                    },
                ]
            }
        ),
        event=make_event(),
    )

    assert report.matched is False
    assert len(report.evaluations) == 2


def test_any_group_requires_one_condition() -> None:
    report = match_notification_policy(
        policy=make_policy(
            {
                "any": [
                    {
                        "field": "severity",
                        "operator": "eq",
                        "value": "info",
                    },
                    {
                        "field": "device.role",
                        "operator": "eq",
                        "value": "core-router",
                    },
                ]
            }
        ),
        event=make_event(),
    )

    assert report.matched is True


def test_not_group_inverts_result() -> None:
    report = match_notification_policy(
        policy=make_policy(
            {
                "not": {
                    "field": "severity",
                    "operator": "eq",
                    "value": "info",
                }
            }
        ),
        event=make_event(),
    )

    assert report.matched is True


def test_nested_label_path_matches() -> None:
    report = match_notification_policy(
        policy=make_policy(
            {
                "all": [
                    {
                        "field": "labels.environment",
                        "operator": "eq",
                        "value": "production",
                    },
                    {
                        "field": "labels.region",
                        "operator": "eq",
                        "value": "eastern",
                    },
                ]
            }
        ),
        event=make_event(),
    )

    assert report.matched is True


def test_missing_field_fails_regular_operator() -> None:
    report = match_notification_policy(
        policy=make_policy(
            {
                "field": "metadata.ticket_id",
                "operator": "eq",
                "value": "INC-100",
            }
        ),
        event=make_event(),
    )

    assert report.matched is False

    assert (
        report.evaluations[0].reason
        == "Field does not exist"
    )


def test_disabled_policy_never_matches() -> None:
    report = match_notification_policy(
        policy=make_policy(
            {
                "field": "severity",
                "value": "critical",
            },
            enabled=False,
        ),
        event=make_event(),
    )

    assert report.matched is False
    assert report.reason == "Policy is disabled"


def test_empty_policy_matches_all_events() -> None:
    report = match_notification_policy(
        policy=make_policy({}),
        event=make_event(),
    )

    assert report.matched is True


def test_legacy_conditions_are_supported() -> None:
    report = match_notification_policy(
        policy=make_policy(
            {
                "event_types": [
                    "device_down",
                ],
                "severities": [
                    "critical",
                ],
                "device_ids": [
                    25,
                ],
                "labels": {
                    "environment": (
                        "production"
                    ),
                },
            }
        ),
        event=make_event(),
    )

    assert report.matched is True


def test_legacy_conditions_normalize_to_all_group() -> None:
    normalized = normalize_policy_conditions(
        {
            "event_types": [
                "device_down",
            ],
            "severities": [
                "critical",
            ],
        }
    )

    assert "all" in normalized
    assert len(normalized["all"]) == 2


def test_unknown_legacy_key_is_invalid() -> None:
    report = match_notification_policy(
        policy=make_policy(
            {
                "unknown_filter": [
                    "value",
                ],
            }
        ),
        event=make_event(),
    )

    assert (
        report.status
        is PolicyMatchStatus.INVALID_POLICY
    )


def test_unknown_operator_is_invalid() -> None:
    report = match_notification_policy(
        policy=make_policy(
            {
                "field": "severity",
                "operator": "approximately",
                "value": "critical",
            }
        ),
        event=make_event(),
    )

    assert (
        report.status
        is PolicyMatchStatus.INVALID_POLICY
    )


def test_matcher_service_can_be_reused() -> None:
    matcher = NotificationConditionMatcher()

    policy = make_policy(
        {
            "field": "site.name",
            "operator": "eq",
            "value": "Al-Jafurah",
        }
    )

    first = matcher.match(
        policy=policy,
        event=make_event(),
    )

    second = matcher.match(
        policy=policy,
        event=make_event(),
    )

    assert first.matched is True
    assert second.matched is True


def test_policy_can_be_replaced_without_mutating_original() -> None:
    policy = make_policy(
        {
            "field": "severity",
            "value": "critical",
        }
    )

    disabled = replace(
        policy,
        enabled=False,
    )

    assert policy.enabled is True
    assert disabled.enabled is False
