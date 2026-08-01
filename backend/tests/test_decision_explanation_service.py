from __future__ import annotations

import pytest

from app.models.decision_explanation import (
    DecisionExplanation,
)
from app.services.decision_explanation import (
    DecisionExplanationService,
    build_decision_explanation,
)
from tests.test_decision_fusion import (
    make_graph,
)


def test_service_returns_explanation() -> None:
    explanation = (
        build_decision_explanation(
            make_graph(),
            "device:core",
        )
    )

    assert isinstance(
        explanation,
        DecisionExplanation,
    )

    assert explanation.decision_id
    assert explanation.summary
    assert explanation.why


def test_power_alarm_is_explained_first() -> None:
    explanation = (
        build_decision_explanation(
            make_graph(
                power_alarm=True
            ),
            "device:core",
        )
    )

    root_items = [
        item
        for item in explanation.why
        if (
            item.metadata.get(
                "explanation_type"
            )
            == "root_cause"
        )
    ]

    assert root_items

    assert (
        root_items[0]
        .metadata["cause_id"]
        .startswith("cause:power:")
    )


def test_upstream_failure_is_explained() -> None:
    explanation = (
        build_decision_explanation(
            make_graph(
                upstream_failed=True
            ),
            "device:core",
        )
    )

    cause_ids = {
        item.metadata.get(
            "cause_id"
        )
        for item in explanation.why
        if (
            item.metadata.get(
                "explanation_type"
            )
            == "root_cause"
        )
    }

    assert any(
        str(cause_id).startswith(
            "cause:upstream:"
        )
        for cause_id in cause_ids
    )


def test_explanation_contains_impact() -> None:
    explanation = (
        build_decision_explanation(
            make_graph(),
            "device:core",
        )
    )

    impact = next(
        item
        for item in explanation.why
        if (
            item.metadata.get(
                "explanation_type"
            )
            == "impact"
        )
    )

    assert (
        impact.metadata["affected_count"]
        == 3
    )

    assert "dependent entities" in (
        impact.description
    )


def test_explanation_contains_resilience() -> None:
    explanation = (
        build_decision_explanation(
            make_graph(
                with_backup=True
            ),
            "device:core",
        )
    )

    resilience = next(
        item
        for item in explanation.why
        if (
            item.metadata.get(
                "explanation_type"
            )
            == "resilience"
        )
    )

    assert (
        resilience.metadata
        ["backup_available"]
        is True
    )


def test_explanation_contains_decision() -> None:
    explanation = (
        build_decision_explanation(
            make_graph(),
            "device:core",
        )
    )

    decision = next(
        item
        for item in explanation.why
        if (
            item.metadata.get(
                "explanation_type"
            )
            == "decision"
        )
    )

    assert decision.metadata["action"]
    assert decision.metadata["rollback_plan"]


def test_explanation_contains_recommendations() -> None:
    explanation = (
        build_decision_explanation(
            make_graph(),
            "device:core",
        )
    )

    assert explanation.recommendations
    assert ":" in explanation.recommendations[0]


def test_explanation_is_safe_and_read_only() -> None:
    explanation = (
        build_decision_explanation(
            make_graph(),
            "device:core",
        )
    )

    assert (
        explanation.metadata
        ["network_io_performed"]
        is False
    )

    assert (
        explanation.metadata
        ["device_command_executed"]
        is False
    )


def test_explanation_serializes() -> None:
    explanation = (
        build_decision_explanation(
            make_graph(),
            "device:core",
        )
    )

    payload = explanation.to_dict()

    assert payload["decision_id"]
    assert payload["confidence"] >= 0
    assert payload["why"]
    assert payload["metadata"]["risk_level"]


def test_invalid_depth_rejected() -> None:
    service = DecisionExplanationService(
        make_graph()
    )

    with pytest.raises(
        ValueError,
        match="max_depth",
    ):
        service.build(
            "device:core",
            max_depth=0,
        )


def test_unknown_node_rejected() -> None:
    service = DecisionExplanationService(
        make_graph()
    )

    with pytest.raises(
        KeyError,
        match="Unknown graph node",
    ):
        service.build(
            "device:missing"
        )


def test_invalid_result_type_rejected() -> None:
    service = DecisionExplanationService(
        make_graph()
    )

    with pytest.raises(
        TypeError,
        match="DecisionIntelligenceResult",
    ):
        service.build_from_result(
            {}
        )  # type: ignore[arg-type]
