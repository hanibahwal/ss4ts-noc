from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.events.notification_enums import (
    EventState,
)
from app.events.notification_event import (
    NotificationEvent,
)
from app.models.notification import (
    NotificationIncident,
    NotificationIncidentStatus,
)
from app.models.notification_incident_lifecycle import (
    IncidentLifecycleAction,
    IncidentLifecycleError,
    IncidentLifecycleResult,
    IncidentLifecycleSummary,
    InvalidIncidentTransition,
)
from app.services.notification_store import (
    NotificationNotFound,
    NotificationStore,
    NotificationVersionConflict,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _incident_id() -> str:
    return f"incident:{uuid4()}"


def _text_id(
    value: int | str | None,
) -> str | None:
    if value is None:
        return None

    return str(value)


def calculate_incident_downtime_seconds(
    incident: NotificationIncident,
    *,
    at: datetime | None = None,
) -> float:
    end_time = (
        incident.resolved_at
        or at
        or incident.last_seen_at
    )

    seconds = (
        end_time
        - incident.first_seen_at
    ).total_seconds()

    return max(
        0.0,
        round(seconds, 3),
    )


class NotificationIncidentLifecycle:
    """
    Converts canonical notification events into persistent
    notification incidents.

    Responsibilities:
      - create one open incident per fingerprint;
      - update repeated observations;
      - acknowledge open incidents;
      - resolve incidents from recovery events;
      - preserve correlation and timing information.

    This service does not evaluate notification policies and
    does not dispatch messages.
    """

    def __init__(
        self,
        store: NotificationStore,
        clock=None,
    ) -> None:
        self.store = store
        self.clock = clock or _utc_now

    @staticmethod
    def _incident_metadata(
        event: NotificationEvent,
    ) -> dict[str, object]:
        return {
            **event.metadata,
            "last_event_id": str(
                event.event_id
            ),
            "last_event_state": (
                event.state.value
            ),
            "last_event_source": (
                event.source.value
            ),
            "last_event_occurred_at": (
                event.occurred_at.isoformat()
            ),
            "labels": dict(event.labels),
        }

    @staticmethod
    def _new_incident(
        event: NotificationEvent,
    ) -> NotificationIncident:
        return NotificationIncident(
            incident_id=_incident_id(),
            fingerprint=event.fingerprint or "",
            correlation_id=str(
                event.correlation_id
                or event.event_id
            ),
            event_type=event.event_type.value,
            severity=event.severity.value,
            status=(
                NotificationIncidentStatus.OPEN
            ),
            title=event.title,
            message=event.message,
            device_id=(
                _text_id(event.device.id)
                if event.device is not None
                else None
            ),
            site_id=(
                _text_id(event.site.id)
                if event.site is not None
                else None
            ),
            interface_id=(
                _text_id(event.interface.id)
                if event.interface is not None
                else None
            ),
            first_seen_at=event.occurred_at,
            last_seen_at=event.occurred_at,
            metadata=(
                NotificationIncidentLifecycle
                ._incident_metadata(event)
            ),
            created_at=event.created_at,
            updated_at=event.created_at,
        )

    def process_event(
        self,
        event: NotificationEvent,
    ) -> IncidentLifecycleResult:
        if event.state in {
            EventState.FIRING,
            EventState.ACTIVE,
        }:
            return self._process_active_event(
                event
            )

        if event.state in {
            EventState.RECOVERED,
            EventState.RESOLVED,
        }:
            return self._process_recovery_event(
                event
            )

        if event.state is EventState.ACKNOWLEDGED:
            incident = (
                self.store
                .get_open_incident_by_fingerprint(
                    event.fingerprint or ""
                )
            )

            if incident is None:
                return IncidentLifecycleResult(
                    action=(
                        IncidentLifecycleAction
                        .IGNORED
                    ),
                    incident=None,
                    reason=(
                        "No open incident exists "
                        "for acknowledgment event"
                    ),
                )

            actor = str(
                event.metadata.get(
                    "acknowledged_by",
                    "event",
                )
            )

            return self.acknowledge(
                incident.incident_id,
                acknowledged_by=actor,
                expected_version=(
                    incident.record_version
                ),
            )

        return IncidentLifecycleResult(
            action=IncidentLifecycleAction.IGNORED,
            incident=None,
            reason=(
                f"Event state '{event.state.value}' "
                "does not change incident lifecycle"
            ),
        )

    def _process_active_event(
        self,
        event: NotificationEvent,
    ) -> IncidentLifecycleResult:
        fingerprint = event.fingerprint or ""

        existing = (
            self.store
            .get_open_incident_by_fingerprint(
                fingerprint
            )
        )

        if existing is None:
            incident = self._new_incident(
                event
            )

            self.store.create_incident(
                incident
            )

            return IncidentLifecycleResult(
                action=(
                    IncidentLifecycleAction
                    .CREATED
                ),
                incident=incident,
                created=True,
                changed=True,
                previous_status=None,
                current_status=(
                    incident.status.value
                ),
                downtime_seconds=0.0,
                reason="New incident created",
            )

        metadata = {
            **existing.metadata,
            **self._incident_metadata(event),
        }

        updated = self.store.touch_incident(
            existing.incident_id,
            message=event.message,
            metadata=metadata,
            expected_version=(
                existing.record_version
            ),
        )

        return IncidentLifecycleResult(
            action=(
                IncidentLifecycleAction
                .OBSERVED
            ),
            incident=updated,
            created=False,
            changed=True,
            previous_status=(
                existing.status.value
            ),
            current_status=(
                updated.status.value
            ),
            downtime_seconds=(
                calculate_incident_downtime_seconds(
                    updated,
                    at=event.occurred_at,
                )
            ),
            reason=(
                "Existing incident observation updated"
            ),
        )

    def _find_recovery_incident(
        self,
        event: NotificationEvent,
    ) -> NotificationIncident | None:
        original_fingerprint = (
            event.metadata.get(
                "recovery_fingerprint"
            )
        )

        if original_fingerprint:
            incident = (
                self.store
                .get_open_incident_by_fingerprint(
                    str(original_fingerprint)
                )
            )

            if incident is not None:
                return incident

        incident_id = event.metadata.get(
            "incident_id"
        )

        if incident_id:
            incident = self.store.get_incident(
                str(incident_id)
            )

            if (
                incident is not None
                and incident.status
                in {
                    NotificationIncidentStatus.OPEN,
                    NotificationIncidentStatus
                    .ACKNOWLEDGED,
                }
            ):
                return incident

        correlation_id = str(
            event.correlation_id
            or ""
        )

        candidate = (
            self.store
            .get_open_incident_by_fingerprint(
                event.fingerprint or ""
            )
        )

        if (
            candidate is not None
            and candidate.correlation_id
            == correlation_id
        ):
            return candidate

        return None

    def _process_recovery_event(
        self,
        event: NotificationEvent,
    ) -> IncidentLifecycleResult:
        incident = self._find_recovery_incident(
            event
        )

        if incident is None:
            return IncidentLifecycleResult(
                action=(
                    IncidentLifecycleAction
                    .IGNORED
                ),
                incident=None,
                reason=(
                    "No matching open incident "
                    "exists for recovery event"
                ),
                metadata={
                    "correlation_id": str(
                        event.correlation_id
                        or ""
                    ),
                },
            )

        resolved_by = str(
            event.metadata.get(
                "resolved_by",
                "recovery-event",
            )
        )

        result = self.resolve(
            incident.incident_id,
            resolved_by=resolved_by,
            expected_version=(
                incident.record_version
            ),
        )

        return IncidentLifecycleResult(
            action=(
                IncidentLifecycleAction
                .RECOVERED
            ),
            incident=result.incident,
            created=False,
            changed=True,
            previous_status=(
                result.previous_status
            ),
            current_status=(
                result.current_status
            ),
            downtime_seconds=(
                result.downtime_seconds
            ),
            reason=(
                "Incident resolved by recovery event"
            ),
            metadata={
                "recovery_event_id": str(
                    event.event_id
                ),
            },
        )

    def acknowledge(
        self,
        incident_id: str,
        *,
        acknowledged_by: str,
        expected_version: int | None = None,
    ) -> IncidentLifecycleResult:
        actor = acknowledged_by.strip()

        if not actor:
            raise IncidentLifecycleError(
                "Acknowledgment actor must not be empty"
            )

        incident = self.store.get_incident(
            incident_id
        )

        if incident is None:
            raise NotificationNotFound(
                f"Incident not found: {incident_id}"
            )

        if (
            incident.status
            is NotificationIncidentStatus.RESOLVED
        ):
            raise InvalidIncidentTransition(
                "Resolved incidents cannot "
                "be acknowledged"
            )

        if (
            incident.status
            is NotificationIncidentStatus
            .ACKNOWLEDGED
        ):
            return IncidentLifecycleResult(
                action=(
                    IncidentLifecycleAction
                    .IGNORED
                ),
                incident=incident,
                created=False,
                changed=False,
                previous_status=(
                    incident.status.value
                ),
                current_status=(
                    incident.status.value
                ),
                downtime_seconds=(
                    calculate_incident_downtime_seconds(
                        incident
                    )
                ),
                reason=(
                    "Incident is already acknowledged"
                ),
            )

        version = (
            expected_version
            if expected_version is not None
            else incident.record_version
        )

        updated = (
            self.store.acknowledge_incident(
                incident_id,
                acknowledged_by=actor,
                expected_version=version,
            )
        )

        return IncidentLifecycleResult(
            action=(
                IncidentLifecycleAction
                .ACKNOWLEDGED
            ),
            incident=updated,
            created=False,
            changed=True,
            previous_status=(
                incident.status.value
            ),
            current_status=(
                updated.status.value
            ),
            downtime_seconds=(
                calculate_incident_downtime_seconds(
                    updated
                )
            ),
            reason="Incident acknowledged",
        )

    def resolve(
        self,
        incident_id: str,
        *,
        resolved_by: str,
        expected_version: int | None = None,
        resolved_at: datetime | None = None,
    ) -> IncidentLifecycleResult:
        actor = resolved_by.strip()

        if not actor:
            raise IncidentLifecycleError(
                "Resolution actor must not be empty"
            )

        incident = self.store.get_incident(
            incident_id
        )

        if incident is None:
            raise NotificationNotFound(
                f"Incident not found: {incident_id}"
            )

        if (
            incident.status
            is NotificationIncidentStatus.RESOLVED
        ):
            return IncidentLifecycleResult(
                action=(
                    IncidentLifecycleAction
                    .IGNORED
                ),
                incident=incident,
                created=False,
                changed=False,
                previous_status=(
                    incident.status.value
                ),
                current_status=(
                    incident.status.value
                ),
                downtime_seconds=(
                    calculate_incident_downtime_seconds(
                        incident
                    )
                ),
                reason=(
                    "Incident is already resolved"
                ),
            )

        version = (
            expected_version
            if expected_version is not None
            else incident.record_version
        )

        try:
            updated = self.store.resolve_incident(
                incident_id,
                resolved_by=actor,
                expected_version=version,
                resolved_at=(
                    resolved_at
                    or incident.last_seen_at
                    or self.clock()
                ),
            )
        except NotificationVersionConflict:
            raise

        return IncidentLifecycleResult(
            action=(
                IncidentLifecycleAction
                .RESOLVED
            ),
            incident=updated,
            created=False,
            changed=True,
            previous_status=(
                incident.status.value
            ),
            current_status=(
                updated.status.value
            ),
            downtime_seconds=(
                calculate_incident_downtime_seconds(
                    updated
                )
            ),
            reason="Incident resolved",
        )

    def summary(
        self,
        incident_id: str,
        *,
        at: datetime | None = None,
    ) -> IncidentLifecycleSummary:
        incident = self.store.get_incident(
            incident_id
        )

        if incident is None:
            raise NotificationNotFound(
                f"Incident not found: {incident_id}"
            )

        return IncidentLifecycleSummary(
            incident_id=incident.incident_id,
            fingerprint=incident.fingerprint,
            status=incident.status.value,
            occurrence_count=(
                incident.occurrence_count
            ),
            escalation_level=(
                incident
                .current_escalation_level
            ),
            first_seen_at=(
                incident.first_seen_at
            ),
            last_seen_at=incident.last_seen_at,
            acknowledged_at=(
                incident.acknowledged_at
            ),
            resolved_at=incident.resolved_at,
            downtime_seconds=(
                calculate_incident_downtime_seconds(
                    incident,
                    at=at,
                )
            ),
        )
