from __future__ import annotations

import pytest

from app.models.decision_explanation import (
    DecisionExplanation,
    EvidenceItem,
    ExplanationItem,
)


def test_decision_explanation_serialization() -> None:
    explanation = DecisionExplanation(
        decision_id="decision:1",
        summary="Power failure",
        confidence=96,
        why=[
            ExplanationItem(
                title="Power Alarm",
                description="UPS reported alarm",
                confidence=98,
                evidence=[
                    EvidenceItem(
                        source="UPS",
                        key="battery",
                        value="low",
                    )
                ],
            )
        ],
        recommendations=[
            "Restart power",
        ],
    )

    payload = explanation.to_dict()

    assert (
        payload["decision_id"]
        == "decision:1"
    )

    assert payload["confidence"] == 96.0
    assert len(payload["why"]) == 1

    assert (
        payload["why"][0]["title"]
        == "Power Alarm"
    )

    assert (
        payload["why"][0]
        ["evidence"][0]["key"]
        == "battery"
    )


def test_confidence_is_clamped() -> None:
    evidence = EvidenceItem(
        source="telemetry",
        key="voltage",
        value="low",
        confidence=150,
    )

    assert evidence.confidence == 100.0


def test_explanations_are_sorted_by_confidence() -> None:
    explanation = DecisionExplanation(
        decision_id="decision:1",
        summary="Failure analysis",
        confidence=90,
        why=[
            ExplanationItem(
                title="Secondary cause",
                description="Lower confidence",
                confidence=70,
            ),
            ExplanationItem(
                title="Primary cause",
                description="Higher confidence",
                confidence=95,
            ),
        ],
    )

    assert (
        explanation.why[0].title
        == "Primary cause"
    )


def test_evidence_requires_source() -> None:
    with pytest.raises(
        ValueError,
        match="source",
    ):
        EvidenceItem(
            source="",
            key="voltage",
            value="low",
        )


def test_evidence_requires_key() -> None:
    with pytest.raises(
        ValueError,
        match="key",
    ):
        EvidenceItem(
            source="telemetry",
            key="",
            value="low",
        )


def test_decision_requires_id() -> None:
    with pytest.raises(
        ValueError,
        match="Decision id",
    ):
        DecisionExplanation(
            decision_id="",
            summary="Invalid decision",
            confidence=0,
        )
