from __future__ import annotations

import pytest

from app.models.decision_timeline import (
    DecisionTimeline,
    DecisionTimelineEvent,
    TimelineEventStatus,
    TimelineEventType,
    normalize_decision_timeline,
)


def make_event(
    *,
    event_id: str = "event:1",
    sequence: int = 1,
    event_type: TimelineEventType = (
        TimelineEventType.OBSERVATION
    ),
    actionable: bool = False,
    requires_approval: bool = False,
) -> DecisionTimelineEvent:
    return DecisionTimelineEvent(
        event_id=event_id,
        sequence=sequence,
        event_type=event_type,
        title="Network event",
        description="A network condition was observed.",
        status=TimelineEventStatus.DETECTED,
        confidence_percent=90,
        source_id="device:core",
        actionable=actionable,
        requires_approval=requires_approval,
    )


def test_event_serialization() -> None:
    event = make_event()

    payload = event.to_dict()

    assert payload["id"] == "event:1"
    assert payload["type"] == "observation"
    assert payload["status"] == "detected"
    assert payload["confidence"] == 90.0


def test_event_from_dict_aliases() -> None:
    event = DecisionTimelineEvent.from_dict({
        "id": "event:power",
        "order": 2,
        "type": "cause",
        "title": "Power failure",
        "summary": "Power alarm confirmed.",
        "status": "confirmed",
        "confidence": 96,
        "source": "device:core",
        "nodes": [
            "device:core",
            "site:branch",
        ],
    })

    assert event.sequence == 2

    assert (
        event.event_type
        == TimelineEventType.ROOT_CAUSE
    )

    assert event.confidence_percent == 96.0

    assert event.related_node_ids == [
        "device:core",
        "site:branch",
    ]


def test_event_rejects_invalid_sequence() -> None:
    with pytest.raises(
        ValueError,
        match="sequence",
    ):
        make_event(sequence=0)


def test_event_confidence_is_clamped() -> None:
    event = DecisionTimelineEvent(
        event_id="event:1",
        sequence=1,
        event_type="evidence",
        title="Evidence",
        description="Telemetry evidence",
        confidence_percent=150,
    )

    assert event.confidence_percent == 100.0


def test_timeline_sorts_events() -> None:
    timeline = DecisionTimeline(
        timeline_id="timeline:1",
        source_node_id="device:core",
        title="Decision story",
        events=[
            make_event(
                event_id="event:2",
                sequence=2,
            ),
            make_event(
                event_id="event:1",
                sequence=1,
            ),
        ],
    )

    assert [
        event.sequence
        for event in timeline.events
    ] == [1, 2]


def test_timeline_statistics() -> None:
    timeline = DecisionTimeline(
        timeline_id="timeline:1",
        source_node_id="device:core",
        title="Decision story",
        events=[
            make_event(
                event_id="event:1",
                sequence=1,
            ),
            make_event(
                event_id="event:2",
                sequence=2,
                event_type=(
                    TimelineEventType.DECISION
                ),
                actionable=True,
                requires_approval=True,
            ),
        ],
    )

    payload = timeline.to_dict()

    assert (
        payload["statistics"]
        ["event_count"]
        == 2
    )

    assert (
        payload["statistics"]
        ["actionable_event_count"]
        == 1
    )

    assert (
        payload["statistics"]
        ["approval_required"]
        is True
    )


def test_timeline_final_event() -> None:
    timeline = DecisionTimeline(
        timeline_id="timeline:1",
        source_node_id="device:core",
        title="Decision story",
        events=[
            make_event(
                event_id="event:1",
                sequence=1,
            ),
            make_event(
                event_id="event:2",
                sequence=2,
                event_type=(
                    TimelineEventType.DECISION
                ),
            ),
        ],
    )

    assert timeline.final_event is not None

    assert (
        timeline.final_event.event_id
        == "event:2"
    )


def test_duplicate_event_ids_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="duplicate event ids",
    ):
        DecisionTimeline(
            timeline_id="timeline:1",
            source_node_id="device:core",
            title="Decision story",
            events=[
                make_event(
                    event_id="event:1",
                    sequence=1,
                ),
                make_event(
                    event_id="event:1",
                    sequence=2,
                ),
            ],
        )


def test_duplicate_sequences_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="duplicate sequences",
    ):
        DecisionTimeline(
            timeline_id="timeline:1",
            source_node_id="device:core",
            title="Decision story",
            events=[
                make_event(
                    event_id="event:1",
                    sequence=1,
                ),
                make_event(
                    event_id="event:2",
                    sequence=1,
                ),
            ],
        )


def test_normalize_decision_timeline() -> None:
    timeline = normalize_decision_timeline({
        "id": "timeline:1",
        "source": "device:core",
        "title": "Decision story",
        "events": [],
    })

    assert isinstance(
        timeline,
        DecisionTimeline,
    )


def test_normalize_invalid_timeline() -> None:
    assert (
        normalize_decision_timeline(
            "invalid"
        )
        is None
    )
