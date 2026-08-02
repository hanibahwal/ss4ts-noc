from __future__ import annotations

import json
import sqlite3

from contextlib import closing
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.notification import (
    NotificationChannel,
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationEscalationStep,
    NotificationIncident,
    NotificationIncidentStatus,
    NotificationPolicy,
    NotificationRecipient,
    NotificationSuppression,
    NotificationSuppressionKind,
    NotificationType,
)


class NotificationStoreError(
    RuntimeError
):
    """Base notification persistence failure."""


class NotificationNotFound(
    NotificationStoreError
):
    """Requested notification record was not found."""


class NotificationVersionConflict(
    NotificationStoreError
):
    def __init__(
        self,
        *,
        entity_type: str,
        entity_id: str,
        expected_version: int,
        actual_version: int,
    ) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.expected_version = expected_version
        self.actual_version = actual_version

        super().__init__(
            f"{entity_type} version conflict for "
            f"{entity_id}: expected={expected_version}, "
            f"actual={actual_version}"
        )


class NotificationDuplicate(
    NotificationStoreError
):
    """A unique notification record already exists."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _datetime_text(
    value: datetime | None,
) -> str | None:
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    ).isoformat()


def _parse_datetime(
    value: str | None,
) -> datetime | None:
    if not value:
        return None

    parsed = datetime.fromisoformat(
        value.replace(
            "Z",
            "+00:00",
        )
    )

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


def canonical_notification_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _json_dict(
    value: str | None,
) -> dict[str, Any]:
    if not value:
        return {}

    decoded = json.loads(value)

    if not isinstance(decoded, dict):
        raise NotificationStoreError(
            "Stored JSON value is not an object"
        )

    return decoded


def _json_tuple(
    value: str | None,
) -> tuple[str, ...]:
    if not value:
        return ()

    decoded = json.loads(value)

    if not isinstance(decoded, list):
        raise NotificationStoreError(
            "Stored JSON value is not an array"
        )

    return tuple(
        str(item)
        for item in decoded
    )


class NotificationStore:
    """
    Persistent SQLite storage for notification policies,
    incidents, deliveries, recipients, escalations and
    suppressions.

    The store performs persistence only. It does not evaluate
    policies and does not send external notifications.
    """

    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        self.database_path = Path(
            database_path
        )

        if not str(
            self.database_path
        ).strip():
            raise ValueError(
                "Notification database path must not be empty"
            )

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.initialize()

    def _connect(
        self,
    ) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=30,
        )

        connection.row_factory = sqlite3.Row

        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        connection.execute(
            "PRAGMA journal_mode = WAL"
        )

        connection.execute(
            "PRAGMA busy_timeout = 30000"
        )

        return connection

    def initialize(
        self,
    ) -> None:
        with closing(
            self._connect()
        ) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS
                notification_policies (
                    policy_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    priority INTEGER NOT NULL,

                    minimum_duration_seconds
                        INTEGER NOT NULL,

                    cooldown_seconds
                        INTEGER NOT NULL,

                    send_recovery INTEGER NOT NULL,
                    stop_processing INTEGER NOT NULL,

                    conditions_json TEXT NOT NULL,
                    actions_json TEXT NOT NULL,

                    record_version INTEGER
                        NOT NULL DEFAULT 1,

                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS
                notification_recipients (
                    recipient_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    address TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,

                    UNIQUE (
                        channel,
                        address
                    )
                );

                CREATE TABLE IF NOT EXISTS
                notification_escalation_steps (
                    escalation_step_id
                        TEXT PRIMARY KEY,

                    policy_id TEXT NOT NULL,
                    step_order INTEGER NOT NULL,
                    delay_seconds INTEGER NOT NULL,

                    channel TEXT NOT NULL,
                    recipient_id TEXT NOT NULL,

                    repeat_interval_seconds INTEGER,
                    max_repeats INTEGER NOT NULL,

                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,

                    FOREIGN KEY (
                        policy_id
                    )
                    REFERENCES notification_policies (
                        policy_id
                    )
                    ON DELETE CASCADE,

                    FOREIGN KEY (
                        recipient_id
                    )
                    REFERENCES notification_recipients (
                        recipient_id
                    )
                    ON DELETE RESTRICT,

                    UNIQUE (
                        policy_id,
                        step_order
                    )
                );

                CREATE TABLE IF NOT EXISTS
                notification_incidents (
                    incident_id TEXT PRIMARY KEY,
                    fingerprint TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,

                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,

                    title TEXT NOT NULL,
                    message TEXT NOT NULL,

                    device_id TEXT,
                    site_id TEXT,
                    interface_id TEXT,

                    occurrence_count
                        INTEGER NOT NULL DEFAULT 1,

                    current_escalation_level
                        INTEGER NOT NULL DEFAULT 0,

                    acknowledged_by TEXT,
                    acknowledged_at TEXT,

                    resolved_by TEXT,
                    resolved_at TEXT,

                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,

                    metadata_json TEXT NOT NULL,

                    record_version INTEGER
                        NOT NULL DEFAULT 1,

                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE UNIQUE INDEX IF NOT EXISTS
                uq_notification_open_incident
                ON notification_incidents (
                    fingerprint
                )
                WHERE status IN (
                    'open',
                    'acknowledged'
                );

                CREATE TABLE IF NOT EXISTS
                notification_deliveries (
                    delivery_id TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    policy_id TEXT,
                    recipient_id TEXT,

                    channel TEXT NOT NULL,
                    notification_type TEXT NOT NULL,
                    status TEXT NOT NULL,

                    destination TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL,

                    provider_message_id TEXT,
                    error_message TEXT,

                    scheduled_at TEXT,
                    sent_at TEXT,

                    metadata_json TEXT NOT NULL,

                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,

                    FOREIGN KEY (
                        incident_id
                    )
                    REFERENCES notification_incidents (
                        incident_id
                    )
                    ON DELETE CASCADE,

                    FOREIGN KEY (
                        policy_id
                    )
                    REFERENCES notification_policies (
                        policy_id
                    )
                    ON DELETE SET NULL,

                    FOREIGN KEY (
                        recipient_id
                    )
                    REFERENCES notification_recipients (
                        recipient_id
                    )
                    ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS
                notification_suppressions (
                    suppression_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    enabled INTEGER NOT NULL,

                    starts_at TEXT NOT NULL,
                    ends_at TEXT NOT NULL,

                    reason TEXT NOT NULL,

                    event_types_json TEXT NOT NULL,
                    site_ids_json TEXT NOT NULL,
                    device_ids_json TEXT NOT NULL,

                    metadata_json TEXT NOT NULL,

                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS
                notification_history (
                    history_id INTEGER
                        PRIMARY KEY AUTOINCREMENT,

                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    record_version INTEGER,
                    recorded_at TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS
                idx_notification_policy_priority
                ON notification_policies (
                    enabled,
                    priority,
                    name
                );

                CREATE INDEX IF NOT EXISTS
                idx_notification_incident_status
                ON notification_incidents (
                    status,
                    severity,
                    last_seen_at DESC
                );

                CREATE INDEX IF NOT EXISTS
                idx_notification_incident_correlation
                ON notification_incidents (
                    correlation_id
                );

                CREATE INDEX IF NOT EXISTS
                idx_notification_delivery_status
                ON notification_deliveries (
                    status,
                    scheduled_at,
                    created_at
                );

                CREATE INDEX IF NOT EXISTS
                idx_notification_suppression_window
                ON notification_suppressions (
                    enabled,
                    starts_at,
                    ends_at
                );

                CREATE INDEX IF NOT EXISTS
                idx_notification_history_entity
                ON notification_history (
                    entity_type,
                    entity_id,
                    history_id DESC
                );
                """
            )

            connection.commit()

    def _record_history(
        self,
        connection: sqlite3.Connection,
        *,
        entity_type: str,
        entity_id: str,
        action: str,
        record_version: int | None,
        snapshot: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO notification_history (
                entity_type,
                entity_id,
                action,
                record_version,
                recorded_at,
                snapshot_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                entity_type,
                entity_id,
                action,
                record_version,
                _datetime_text(
                    _utc_now()
                ),
                canonical_notification_json(
                    snapshot
                ),
            ),
        )

    @staticmethod
    def _policy_from_row(
        row: sqlite3.Row,
    ) -> NotificationPolicy:
        return NotificationPolicy(
            policy_id=row["policy_id"],
            name=row["name"],
            description=row["description"],
            enabled=bool(row["enabled"]),
            priority=int(row["priority"]),
            minimum_duration_seconds=int(
                row["minimum_duration_seconds"]
            ),
            cooldown_seconds=int(
                row["cooldown_seconds"]
            ),
            send_recovery=bool(
                row["send_recovery"]
            ),
            stop_processing=bool(
                row["stop_processing"]
            ),
            conditions=_json_dict(
                row["conditions_json"]
            ),
            actions=_json_dict(
                row["actions_json"]
            ),
            record_version=int(
                row["record_version"]
            ),
            created_at=_parse_datetime(
                row["created_at"]
            ),
            updated_at=_parse_datetime(
                row["updated_at"]
            ),
        )

    @staticmethod
    def _recipient_from_row(
        row: sqlite3.Row,
    ) -> NotificationRecipient:
        return NotificationRecipient(
            recipient_id=row["recipient_id"],
            name=row["name"],
            channel=NotificationChannel(
                row["channel"]
            ),
            address=row["address"],
            enabled=bool(row["enabled"]),
            metadata=_json_dict(
                row["metadata_json"]
            ),
            created_at=_parse_datetime(
                row["created_at"]
            ),
            updated_at=_parse_datetime(
                row["updated_at"]
            ),
        )

    @staticmethod
    def _escalation_from_row(
        row: sqlite3.Row,
    ) -> NotificationEscalationStep:
        return NotificationEscalationStep(
            escalation_step_id=(
                row["escalation_step_id"]
            ),
            policy_id=row["policy_id"],
            step_order=int(
                row["step_order"]
            ),
            delay_seconds=int(
                row["delay_seconds"]
            ),
            channel=NotificationChannel(
                row["channel"]
            ),
            recipient_id=row["recipient_id"],
            repeat_interval_seconds=(
                int(
                    row[
                        "repeat_interval_seconds"
                    ]
                )
                if row[
                    "repeat_interval_seconds"
                ] is not None
                else None
            ),
            max_repeats=int(
                row["max_repeats"]
            ),
            metadata=_json_dict(
                row["metadata_json"]
            ),
            created_at=_parse_datetime(
                row["created_at"]
            ),
        )

    @staticmethod
    def _incident_from_row(
        row: sqlite3.Row,
    ) -> NotificationIncident:
        return NotificationIncident(
            incident_id=row["incident_id"],
            fingerprint=row["fingerprint"],
            correlation_id=row["correlation_id"],
            event_type=row["event_type"],
            severity=row["severity"],
            status=NotificationIncidentStatus(
                row["status"]
            ),
            title=row["title"],
            message=row["message"],
            device_id=row["device_id"],
            site_id=row["site_id"],
            interface_id=row["interface_id"],
            occurrence_count=int(
                row["occurrence_count"]
            ),
            current_escalation_level=int(
                row[
                    "current_escalation_level"
                ]
            ),
            acknowledged_by=(
                row["acknowledged_by"]
            ),
            acknowledged_at=_parse_datetime(
                row["acknowledged_at"]
            ),
            resolved_by=row["resolved_by"],
            resolved_at=_parse_datetime(
                row["resolved_at"]
            ),
            first_seen_at=_parse_datetime(
                row["first_seen_at"]
            ),
            last_seen_at=_parse_datetime(
                row["last_seen_at"]
            ),
            metadata=_json_dict(
                row["metadata_json"]
            ),
            record_version=int(
                row["record_version"]
            ),
            created_at=_parse_datetime(
                row["created_at"]
            ),
            updated_at=_parse_datetime(
                row["updated_at"]
            ),
        )

    @staticmethod
    def _delivery_from_row(
        row: sqlite3.Row,
    ) -> NotificationDelivery:
        return NotificationDelivery(
            delivery_id=row["delivery_id"],
            incident_id=row["incident_id"],
            policy_id=row["policy_id"],
            recipient_id=row["recipient_id"],
            channel=NotificationChannel(
                row["channel"]
            ),
            notification_type=NotificationType(
                row["notification_type"]
            ),
            status=NotificationDeliveryStatus(
                row["status"]
            ),
            destination=row["destination"],
            attempt_count=int(
                row["attempt_count"]
            ),
            provider_message_id=(
                row["provider_message_id"]
            ),
            error_message=row["error_message"],
            scheduled_at=_parse_datetime(
                row["scheduled_at"]
            ),
            sent_at=_parse_datetime(
                row["sent_at"]
            ),
            metadata=_json_dict(
                row["metadata_json"]
            ),
            created_at=_parse_datetime(
                row["created_at"]
            ),
            updated_at=_parse_datetime(
                row["updated_at"]
            ),
        )

    @staticmethod
    def _suppression_from_row(
        row: sqlite3.Row,
    ) -> NotificationSuppression:
        return NotificationSuppression(
            suppression_id=row["suppression_id"],
            name=row["name"],
            kind=NotificationSuppressionKind(
                row["kind"]
            ),
            enabled=bool(row["enabled"]),
            starts_at=_parse_datetime(
                row["starts_at"]
            ),
            ends_at=_parse_datetime(
                row["ends_at"]
            ),
            reason=row["reason"],
            event_types=_json_tuple(
                row["event_types_json"]
            ),
            site_ids=_json_tuple(
                row["site_ids_json"]
            ),
            device_ids=_json_tuple(
                row["device_ids_json"]
            ),
            metadata=_json_dict(
                row["metadata_json"]
            ),
            created_at=_parse_datetime(
                row["created_at"]
            ),
            updated_at=_parse_datetime(
                row["updated_at"]
            ),
        )

    def create_policy(
        self,
        policy: NotificationPolicy,
    ) -> NotificationPolicy:
        with closing(
            self._connect()
        ) as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO notification_policies (
                        policy_id,
                        name,
                        description,
                        enabled,
                        priority,
                        minimum_duration_seconds,
                        cooldown_seconds,
                        send_recovery,
                        stop_processing,
                        conditions_json,
                        actions_json,
                        record_version,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        policy.policy_id,
                        policy.name,
                        policy.description,
                        int(policy.enabled),
                        policy.priority,
                        policy.minimum_duration_seconds,
                        policy.cooldown_seconds,
                        int(policy.send_recovery),
                        int(policy.stop_processing),
                        canonical_notification_json(
                            policy.conditions
                        ),
                        canonical_notification_json(
                            policy.actions
                        ),
                        policy.record_version,
                        _datetime_text(
                            policy.created_at
                        ),
                        _datetime_text(
                            policy.updated_at
                        ),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise NotificationDuplicate(
                    f"Notification policy already "
                    f"exists: {policy.policy_id}"
                ) from exc

            self._record_history(
                connection,
                entity_type="policy",
                entity_id=policy.policy_id,
                action="created",
                record_version=(
                    policy.record_version
                ),
                snapshot=policy.to_dict(),
            )

            connection.commit()

        return policy

    def get_policy(
        self,
        policy_id: str,
    ) -> NotificationPolicy | None:
        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM notification_policies
                WHERE policy_id = ?
                """,
                (policy_id,),
            ).fetchone()

        if row is None:
            return None

        return self._policy_from_row(row)

    def list_policies(
        self,
        *,
        enabled_only: bool = False,
    ) -> list[NotificationPolicy]:
        where_clause = (
            "WHERE enabled = 1"
            if enabled_only
            else ""
        )

        with closing(
            self._connect()
        ) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM notification_policies
                {where_clause}
                ORDER BY
                    priority ASC,
                    name ASC,
                    policy_id ASC
                """
            ).fetchall()

        return [
            self._policy_from_row(row)
            for row in rows
        ]

    def update_policy(
        self,
        policy: NotificationPolicy,
        *,
        expected_version: int,
    ) -> NotificationPolicy:
        current = self.get_policy(
            policy.policy_id
        )

        if current is None:
            raise NotificationNotFound(
                f"Policy not found: "
                f"{policy.policy_id}"
            )

        if current.record_version != expected_version:
            raise NotificationVersionConflict(
                entity_type="policy",
                entity_id=policy.policy_id,
                expected_version=expected_version,
                actual_version=(
                    current.record_version
                ),
            )

        updated = replace(
            policy,
            record_version=(
                current.record_version + 1
            ),
            created_at=current.created_at,
            updated_at=_utc_now(),
        )

        with closing(
            self._connect()
        ) as connection:
            cursor = connection.execute(
                """
                UPDATE notification_policies
                SET
                    name = ?,
                    description = ?,
                    enabled = ?,
                    priority = ?,
                    minimum_duration_seconds = ?,
                    cooldown_seconds = ?,
                    send_recovery = ?,
                    stop_processing = ?,
                    conditions_json = ?,
                    actions_json = ?,
                    record_version = ?,
                    updated_at = ?
                WHERE
                    policy_id = ?
                    AND record_version = ?
                """,
                (
                    updated.name,
                    updated.description,
                    int(updated.enabled),
                    updated.priority,
                    (
                        updated
                        .minimum_duration_seconds
                    ),
                    updated.cooldown_seconds,
                    int(updated.send_recovery),
                    int(updated.stop_processing),
                    canonical_notification_json(
                        updated.conditions
                    ),
                    canonical_notification_json(
                        updated.actions
                    ),
                    updated.record_version,
                    _datetime_text(
                        updated.updated_at
                    ),
                    updated.policy_id,
                    expected_version,
                ),
            )

            if cursor.rowcount != 1:
                raise NotificationVersionConflict(
                    entity_type="policy",
                    entity_id=updated.policy_id,
                    expected_version=(
                        expected_version
                    ),
                    actual_version=(
                        current.record_version
                    ),
                )

            self._record_history(
                connection,
                entity_type="policy",
                entity_id=updated.policy_id,
                action="updated",
                record_version=(
                    updated.record_version
                ),
                snapshot=updated.to_dict(),
            )

            connection.commit()

        return updated

    def delete_policy(
        self,
        policy_id: str,
    ) -> bool:
        current = self.get_policy(
            policy_id
        )

        if current is None:
            return False

        with closing(
            self._connect()
        ) as connection:
            self._record_history(
                connection,
                entity_type="policy",
                entity_id=policy_id,
                action="deleted",
                record_version=(
                    current.record_version
                ),
                snapshot=current.to_dict(),
            )

            cursor = connection.execute(
                """
                DELETE FROM notification_policies
                WHERE policy_id = ?
                """,
                (policy_id,),
            )

            connection.commit()

        return cursor.rowcount == 1

    def create_recipient(
        self,
        recipient: NotificationRecipient,
    ) -> NotificationRecipient:
        with closing(
            self._connect()
        ) as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO notification_recipients (
                        recipient_id,
                        name,
                        channel,
                        address,
                        enabled,
                        metadata_json,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        recipient.recipient_id,
                        recipient.name,
                        recipient.channel.value,
                        recipient.address,
                        int(recipient.enabled),
                        canonical_notification_json(
                            recipient.metadata
                        ),
                        _datetime_text(
                            recipient.created_at
                        ),
                        _datetime_text(
                            recipient.updated_at
                        ),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise NotificationDuplicate(
                    "Notification recipient "
                    "already exists"
                ) from exc

            self._record_history(
                connection,
                entity_type="recipient",
                entity_id=recipient.recipient_id,
                action="created",
                record_version=None,
                snapshot={
                    "recipient_id": (
                        recipient.recipient_id
                    ),
                    "name": recipient.name,
                    "channel": (
                        recipient.channel.value
                    ),
                    "address": recipient.address,
                    "enabled": recipient.enabled,
                    "metadata": (
                        recipient.metadata
                    ),
                },
            )

            connection.commit()

        return recipient

    def get_recipient(
        self,
        recipient_id: str,
    ) -> NotificationRecipient | None:
        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM notification_recipients
                WHERE recipient_id = ?
                """,
                (recipient_id,),
            ).fetchone()

        if row is None:
            return None

        return self._recipient_from_row(row)

    def add_escalation_step(
        self,
        step: NotificationEscalationStep,
    ) -> NotificationEscalationStep:
        with closing(
            self._connect()
        ) as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO
                    notification_escalation_steps (
                        escalation_step_id,
                        policy_id,
                        step_order,
                        delay_seconds,
                        channel,
                        recipient_id,
                        repeat_interval_seconds,
                        max_repeats,
                        metadata_json,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        step.escalation_step_id,
                        step.policy_id,
                        step.step_order,
                        step.delay_seconds,
                        step.channel.value,
                        step.recipient_id,
                        (
                            step
                            .repeat_interval_seconds
                        ),
                        step.max_repeats,
                        canonical_notification_json(
                            step.metadata
                        ),
                        _datetime_text(
                            step.created_at
                        ),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise NotificationDuplicate(
                    "Escalation step could not "
                    "be created"
                ) from exc

            connection.commit()

        return step

    def list_escalation_steps(
        self,
        policy_id: str,
    ) -> list[NotificationEscalationStep]:
        with closing(
            self._connect()
        ) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM notification_escalation_steps
                WHERE policy_id = ?
                ORDER BY
                    step_order ASC,
                    escalation_step_id ASC
                """,
                (policy_id,),
            ).fetchall()

        return [
            self._escalation_from_row(row)
            for row in rows
        ]

    def create_incident(
        self,
        incident: NotificationIncident,
    ) -> NotificationIncident:
        with closing(
            self._connect()
        ) as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO notification_incidents (
                        incident_id,
                        fingerprint,
                        correlation_id,
                        event_type,
                        severity,
                        status,
                        title,
                        message,
                        device_id,
                        site_id,
                        interface_id,
                        occurrence_count,
                        current_escalation_level,
                        acknowledged_by,
                        acknowledged_at,
                        resolved_by,
                        resolved_at,
                        first_seen_at,
                        last_seen_at,
                        metadata_json,
                        record_version,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        incident.incident_id,
                        incident.fingerprint,
                        incident.correlation_id,
                        incident.event_type,
                        incident.severity,
                        incident.status.value,
                        incident.title,
                        incident.message,
                        incident.device_id,
                        incident.site_id,
                        incident.interface_id,
                        incident.occurrence_count,
                        (
                            incident
                            .current_escalation_level
                        ),
                        incident.acknowledged_by,
                        _datetime_text(
                            incident.acknowledged_at
                        ),
                        incident.resolved_by,
                        _datetime_text(
                            incident.resolved_at
                        ),
                        _datetime_text(
                            incident.first_seen_at
                        ),
                        _datetime_text(
                            incident.last_seen_at
                        ),
                        canonical_notification_json(
                            incident.metadata
                        ),
                        incident.record_version,
                        _datetime_text(
                            incident.created_at
                        ),
                        _datetime_text(
                            incident.updated_at
                        ),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise NotificationDuplicate(
                    "An open incident with this "
                    "fingerprint already exists"
                ) from exc

            self._record_history(
                connection,
                entity_type="incident",
                entity_id=incident.incident_id,
                action="created",
                record_version=(
                    incident.record_version
                ),
                snapshot={
                    "incident_id": (
                        incident.incident_id
                    ),
                    "fingerprint": (
                        incident.fingerprint
                    ),
                    "status": (
                        incident.status.value
                    ),
                    "event_type": (
                        incident.event_type
                    ),
                    "severity": (
                        incident.severity
                    ),
                },
            )

            connection.commit()

        return incident

    def get_incident(
        self,
        incident_id: str,
    ) -> NotificationIncident | None:
        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM notification_incidents
                WHERE incident_id = ?
                """,
                (incident_id,),
            ).fetchone()

        if row is None:
            return None

        return self._incident_from_row(row)

    def get_open_incident_by_fingerprint(
        self,
        fingerprint: str,
    ) -> NotificationIncident | None:
        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM notification_incidents
                WHERE
                    fingerprint = ?
                    AND status IN (
                        'open',
                        'acknowledged'
                    )
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (fingerprint,),
            ).fetchone()

        if row is None:
            return None

        return self._incident_from_row(row)

    def touch_incident(
        self,
        incident_id: str,
        *,
        message: str,
        metadata: dict[str, Any],
        expected_version: int,
    ) -> NotificationIncident:
        current = self.get_incident(
            incident_id
        )

        if current is None:
            raise NotificationNotFound(
                f"Incident not found: {incident_id}"
            )

        if current.record_version != expected_version:
            raise NotificationVersionConflict(
                entity_type="incident",
                entity_id=incident_id,
                expected_version=expected_version,
                actual_version=(
                    current.record_version
                ),
            )

        updated = replace(
            current,
            message=message,
            occurrence_count=(
                current.occurrence_count + 1
            ),
            last_seen_at=_utc_now(),
            metadata=metadata,
            record_version=(
                current.record_version + 1
            ),
            updated_at=_utc_now(),
        )

        self._update_incident(
            updated,
            expected_version=expected_version,
            action="observed",
        )

        return updated

    def acknowledge_incident(
        self,
        incident_id: str,
        *,
        acknowledged_by: str,
        expected_version: int,
    ) -> NotificationIncident:
        current = self.get_incident(
            incident_id
        )

        if current is None:
            raise NotificationNotFound(
                f"Incident not found: {incident_id}"
            )

        if (
            current.status
            is NotificationIncidentStatus.RESOLVED
        ):
            raise NotificationStoreError(
                "Resolved incidents cannot be acknowledged"
            )

        if current.record_version != expected_version:
            raise NotificationVersionConflict(
                entity_type="incident",
                entity_id=incident_id,
                expected_version=expected_version,
                actual_version=(
                    current.record_version
                ),
            )

        now = _utc_now()

        updated = replace(
            current,
            status=(
                NotificationIncidentStatus
                .ACKNOWLEDGED
            ),
            acknowledged_by=acknowledged_by,
            acknowledged_at=now,
            record_version=(
                current.record_version + 1
            ),
            updated_at=now,
        )

        self._update_incident(
            updated,
            expected_version=expected_version,
            action="acknowledged",
        )

        return updated

    def resolve_incident(
        self,
        incident_id: str,
        *,
        resolved_by: str,
        expected_version: int,
    ) -> NotificationIncident:
        current = self.get_incident(
            incident_id
        )

        if current is None:
            raise NotificationNotFound(
                f"Incident not found: {incident_id}"
            )

        if current.record_version != expected_version:
            raise NotificationVersionConflict(
                entity_type="incident",
                entity_id=incident_id,
                expected_version=expected_version,
                actual_version=(
                    current.record_version
                ),
            )

        now = _utc_now()

        updated = replace(
            current,
            status=(
                NotificationIncidentStatus
                .RESOLVED
            ),
            resolved_by=resolved_by,
            resolved_at=now,
            last_seen_at=now,
            record_version=(
                current.record_version + 1
            ),
            updated_at=now,
        )

        self._update_incident(
            updated,
            expected_version=expected_version,
            action="resolved",
        )

        return updated

    def _update_incident(
        self,
        incident: NotificationIncident,
        *,
        expected_version: int,
        action: str,
    ) -> None:
        with closing(
            self._connect()
        ) as connection:
            cursor = connection.execute(
                """
                UPDATE notification_incidents
                SET
                    severity = ?,
                    status = ?,
                    title = ?,
                    message = ?,
                    occurrence_count = ?,
                    current_escalation_level = ?,
                    acknowledged_by = ?,
                    acknowledged_at = ?,
                    resolved_by = ?,
                    resolved_at = ?,
                    last_seen_at = ?,
                    metadata_json = ?,
                    record_version = ?,
                    updated_at = ?
                WHERE
                    incident_id = ?
                    AND record_version = ?
                """,
                (
                    incident.severity,
                    incident.status.value,
                    incident.title,
                    incident.message,
                    incident.occurrence_count,
                    (
                        incident
                        .current_escalation_level
                    ),
                    incident.acknowledged_by,
                    _datetime_text(
                        incident.acknowledged_at
                    ),
                    incident.resolved_by,
                    _datetime_text(
                        incident.resolved_at
                    ),
                    _datetime_text(
                        incident.last_seen_at
                    ),
                    canonical_notification_json(
                        incident.metadata
                    ),
                    incident.record_version,
                    _datetime_text(
                        incident.updated_at
                    ),
                    incident.incident_id,
                    expected_version,
                ),
            )

            if cursor.rowcount != 1:
                actual = self.get_incident(
                    incident.incident_id
                )

                raise NotificationVersionConflict(
                    entity_type="incident",
                    entity_id=incident.incident_id,
                    expected_version=(
                        expected_version
                    ),
                    actual_version=(
                        actual.record_version
                        if actual is not None
                        else -1
                    ),
                )

            self._record_history(
                connection,
                entity_type="incident",
                entity_id=incident.incident_id,
                action=action,
                record_version=(
                    incident.record_version
                ),
                snapshot={
                    "incident_id": (
                        incident.incident_id
                    ),
                    "status": (
                        incident.status.value
                    ),
                    "occurrence_count": (
                        incident.occurrence_count
                    ),
                    "record_version": (
                        incident.record_version
                    ),
                },
            )

            connection.commit()

    def update_incident_escalation_level(
        self,
        incident_id: str,
        *,
        escalation_level: int,
        expected_version: int,
    ) -> NotificationIncident:
        if escalation_level < 0:
            raise ValueError(
                "Escalation level must be "
                "non-negative"
            )

        current = self.get_incident(
            incident_id
        )

        if current is None:
            raise NotificationNotFound(
                f"Incident not found: {incident_id}"
            )

        if (
            current.record_version
            != expected_version
        ):
            raise NotificationVersionConflict(
                entity_type="incident",
                entity_id=incident_id,
                expected_version=expected_version,
                actual_version=(
                    current.record_version
                ),
            )

        if (
            escalation_level
            < current.current_escalation_level
        ):
            raise ValueError(
                "Incident escalation level "
                "cannot decrease"
            )

        now = _utc_now()

        updated = replace(
            current,
            current_escalation_level=(
                escalation_level
            ),
            record_version=(
                current.record_version + 1
            ),
            updated_at=now,
        )

        with closing(
            self._connect()
        ) as connection:
            cursor = connection.execute(
                """
                UPDATE notification_incidents
                SET
                    current_escalation_level = ?,
                    record_version = ?,
                    updated_at = ?
                WHERE
                    incident_id = ?
                    AND record_version = ?
                    AND current_escalation_level = ?
                """,
                (
                    updated.current_escalation_level,
                    updated.record_version,
                    _datetime_text(
                        updated.updated_at
                    ),
                    updated.incident_id,
                    expected_version,
                    (
                        current
                        .current_escalation_level
                    ),
                ),
            )

            if cursor.rowcount != 1:
                actual = self.get_incident(
                    incident_id
                )

                raise NotificationVersionConflict(
                    entity_type="incident",
                    entity_id=incident_id,
                    expected_version=(
                        expected_version
                    ),
                    actual_version=(
                        actual.record_version
                        if actual is not None
                        else -1
                    ),
                )

            self._record_history(
                connection,
                entity_type="incident",
                entity_id=incident_id,
                action="escalated",
                record_version=(
                    updated.record_version
                ),
                snapshot={
                    "incident_id": incident_id,
                    "status": (
                        updated.status.value
                    ),
                    "current_escalation_level": (
                        updated
                        .current_escalation_level
                    ),
                    "record_version": (
                        updated.record_version
                    ),
                },
            )

            connection.commit()

        return updated

    def find_escalation_delivery(
        self,
        *,
        incident_id: str,
        policy_id: str,
        escalation_step_id: str,
    ) -> NotificationDelivery | None:
        with closing(
            self._connect()
        ) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM notification_deliveries
                WHERE
                    incident_id = ?
                    AND policy_id = ?
                    AND notification_type = ?
                ORDER BY created_at DESC
                """,
                (
                    incident_id,
                    policy_id,
                    (
                        NotificationType
                        .ESCALATION.value
                    ),
                ),
            ).fetchall()

        for row in rows:
            delivery = self._delivery_from_row(
                row
            )

            if (
                delivery.metadata.get(
                    "escalation_step_id"
                )
                == escalation_step_id
            ):
                return delivery

        return None

    def create_delivery(
        self,
        delivery: NotificationDelivery,
    ) -> NotificationDelivery:
        with closing(
            self._connect()
        ) as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO notification_deliveries (
                        delivery_id,
                        incident_id,
                        policy_id,
                        recipient_id,
                        channel,
                        notification_type,
                        status,
                        destination,
                        attempt_count,
                        provider_message_id,
                        error_message,
                        scheduled_at,
                        sent_at,
                        metadata_json,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        delivery.delivery_id,
                        delivery.incident_id,
                        delivery.policy_id,
                        delivery.recipient_id,
                        delivery.channel.value,
                        (
                            delivery
                            .notification_type
                            .value
                        ),
                        delivery.status.value,
                        delivery.destination,
                        delivery.attempt_count,
                        (
                            delivery
                            .provider_message_id
                        ),
                        delivery.error_message,
                        _datetime_text(
                            delivery.scheduled_at
                        ),
                        _datetime_text(
                            delivery.sent_at
                        ),
                        canonical_notification_json(
                            delivery.metadata
                        ),
                        _datetime_text(
                            delivery.created_at
                        ),
                        _datetime_text(
                            delivery.updated_at
                        ),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise NotificationStoreError(
                    "Notification delivery could "
                    "not be created"
                ) from exc

            connection.commit()

        return delivery

    def get_delivery(
        self,
        delivery_id: str,
    ) -> NotificationDelivery | None:
        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM notification_deliveries
                WHERE delivery_id = ?
                """,
                (delivery_id,),
            ).fetchone()

        if row is None:
            return None

        return self._delivery_from_row(row)

    def update_delivery_status(
        self,
        delivery_id: str,
        *,
        status: NotificationDeliveryStatus,
        provider_message_id: str | None = None,
        error_message: str | None = None,
    ) -> NotificationDelivery:
        current = self.get_delivery(
            delivery_id
        )

        if current is None:
            raise NotificationNotFound(
                f"Delivery not found: {delivery_id}"
            )

        now = _utc_now()

        updated = replace(
            current,
            status=status,
            attempt_count=(
                current.attempt_count + 1
            ),
            provider_message_id=(
                provider_message_id
            ),
            error_message=error_message,
            sent_at=(
                now
                if status
                is NotificationDeliveryStatus.SENT
                else current.sent_at
            ),
            updated_at=now,
        )

        with closing(
            self._connect()
        ) as connection:
            connection.execute(
                """
                UPDATE notification_deliveries
                SET
                    status = ?,
                    attempt_count = ?,
                    provider_message_id = ?,
                    error_message = ?,
                    sent_at = ?,
                    updated_at = ?
                WHERE delivery_id = ?
                """,
                (
                    updated.status.value,
                    updated.attempt_count,
                    (
                        updated
                        .provider_message_id
                    ),
                    updated.error_message,
                    _datetime_text(
                        updated.sent_at
                    ),
                    _datetime_text(
                        updated.updated_at
                    ),
                    updated.delivery_id,
                ),
            )

            connection.commit()

        return updated

    def begin_delivery_attempt(
        self,
        delivery_id: str,
    ) -> NotificationDelivery:
        current = self.get_delivery(
            delivery_id
        )

        if current is None:
            raise NotificationNotFound(
                f"Delivery not found: {delivery_id}"
            )

        allowed_statuses = {
            NotificationDeliveryStatus.PENDING,
            NotificationDeliveryStatus.FAILED,
        }

        if current.status not in allowed_statuses:
            raise NotificationStoreError(
                "Delivery attempt cannot start "
                f"from status: {current.status.value}"
            )

        now = _utc_now()

        updated = replace(
            current,
            status=(
                NotificationDeliveryStatus.SENDING
            ),
            attempt_count=(
                current.attempt_count + 1
            ),
            provider_message_id=None,
            error_message=None,
            updated_at=now,
        )

        with closing(
            self._connect()
        ) as connection:
            cursor = connection.execute(
                """
                UPDATE notification_deliveries
                SET
                    status = ?,
                    attempt_count = ?,
                    provider_message_id = NULL,
                    error_message = NULL,
                    updated_at = ?
                WHERE
                    delivery_id = ?
                    AND status = ?
                    AND attempt_count = ?
                """,
                (
                    updated.status.value,
                    updated.attempt_count,
                    _datetime_text(
                        updated.updated_at
                    ),
                    updated.delivery_id,
                    current.status.value,
                    current.attempt_count,
                ),
            )

            if cursor.rowcount != 1:
                raise NotificationStoreError(
                    "Delivery attempt could not "
                    "be started because the "
                    "delivery changed concurrently"
                )

            connection.commit()

        return updated

    def complete_delivery_attempt(
        self,
        delivery_id: str,
        *,
        status: NotificationDeliveryStatus,
        provider_message_id: str | None = None,
        error_message: str | None = None,
    ) -> NotificationDelivery:
        if status not in {
            NotificationDeliveryStatus.SENT,
            NotificationDeliveryStatus.FAILED,
        }:
            raise ValueError(
                "Completed delivery status must "
                "be sent or failed"
            )

        current = self.get_delivery(
            delivery_id
        )

        if current is None:
            raise NotificationNotFound(
                f"Delivery not found: {delivery_id}"
            )

        if (
            current.status
            is not NotificationDeliveryStatus.SENDING
        ):
            raise NotificationStoreError(
                "Delivery attempt can only be "
                "completed from sending status"
            )

        if (
            status
            is NotificationDeliveryStatus.FAILED
            and not (
                error_message
                and error_message.strip()
            )
        ):
            raise ValueError(
                "Failed delivery requires an "
                "error message"
            )

        now = _utc_now()

        updated = replace(
            current,
            status=status,
            provider_message_id=(
                provider_message_id
            ),
            error_message=error_message,
            sent_at=(
                now
                if status
                is NotificationDeliveryStatus.SENT
                else current.sent_at
            ),
            updated_at=now,
        )

        with closing(
            self._connect()
        ) as connection:
            cursor = connection.execute(
                """
                UPDATE notification_deliveries
                SET
                    status = ?,
                    provider_message_id = ?,
                    error_message = ?,
                    sent_at = ?,
                    updated_at = ?
                WHERE
                    delivery_id = ?
                    AND status = ?
                    AND attempt_count = ?
                """,
                (
                    updated.status.value,
                    updated.provider_message_id,
                    updated.error_message,
                    _datetime_text(
                        updated.sent_at
                    ),
                    _datetime_text(
                        updated.updated_at
                    ),
                    updated.delivery_id,
                    (
                        NotificationDeliveryStatus
                        .SENDING.value
                    ),
                    current.attempt_count,
                ),
            )

            if cursor.rowcount != 1:
                raise NotificationStoreError(
                    "Delivery attempt could not "
                    "be completed because the "
                    "delivery changed concurrently"
                )

            connection.commit()

        return updated

    def cancel_delivery(
        self,
        delivery_id: str,
        *,
        reason: str | None = None,
    ) -> NotificationDelivery:
        current = self.get_delivery(
            delivery_id
        )

        if current is None:
            raise NotificationNotFound(
                f"Delivery not found: {delivery_id}"
            )

        if current.status in {
            NotificationDeliveryStatus.SENT,
            NotificationDeliveryStatus.CANCELLED,
        }:
            raise NotificationStoreError(
                "Completed delivery cannot be "
                "cancelled"
            )

        now = _utc_now()

        updated = replace(
            current,
            status=(
                NotificationDeliveryStatus.CANCELLED
            ),
            error_message=reason,
            updated_at=now,
        )

        with closing(
            self._connect()
        ) as connection:
            cursor = connection.execute(
                """
                UPDATE notification_deliveries
                SET
                    status = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE
                    delivery_id = ?
                    AND status = ?
                    AND attempt_count = ?
                """,
                (
                    updated.status.value,
                    updated.error_message,
                    _datetime_text(
                        updated.updated_at
                    ),
                    updated.delivery_id,
                    current.status.value,
                    current.attempt_count,
                ),
            )

            if cursor.rowcount != 1:
                raise NotificationStoreError(
                    "Delivery could not be "
                    "cancelled because it changed "
                    "concurrently"
                )

            connection.commit()

        return updated

    def schedule_delivery_retry(
        self,
        delivery_id: str,
        *,
        scheduled_at: datetime,
    ) -> NotificationDelivery:
        current = self.get_delivery(
            delivery_id
        )

        if current is None:
            raise NotificationNotFound(
                f"Delivery not found: {delivery_id}"
            )

        if (
            current.status
            is not NotificationDeliveryStatus.FAILED
        ):
            raise NotificationStoreError(
                "Only failed deliveries can be "
                "scheduled for retry"
            )

        retry_time = scheduled_at

        if retry_time.tzinfo is None:
            raise ValueError(
                "Retry scheduled time must be "
                "timezone-aware"
            )

        now = _utc_now()

        updated = replace(
            current,
            status=(
                NotificationDeliveryStatus.PENDING
            ),
            scheduled_at=retry_time,
            provider_message_id=None,
            updated_at=now,
        )

        with closing(
            self._connect()
        ) as connection:
            cursor = connection.execute(
                """
                UPDATE notification_deliveries
                SET
                    status = ?,
                    scheduled_at = ?,
                    provider_message_id = NULL,
                    updated_at = ?
                WHERE
                    delivery_id = ?
                    AND status = ?
                    AND attempt_count = ?
                """,
                (
                    updated.status.value,
                    _datetime_text(
                        updated.scheduled_at
                    ),
                    _datetime_text(
                        updated.updated_at
                    ),
                    updated.delivery_id,
                    (
                        NotificationDeliveryStatus
                        .FAILED.value
                    ),
                    current.attempt_count,
                ),
            )

            if cursor.rowcount != 1:
                raise NotificationStoreError(
                    "Delivery retry could not be "
                    "scheduled because the "
                    "delivery changed concurrently"
                )

            connection.commit()

        return updated

    def list_due_deliveries(
        self,
        *,
        at: datetime | None = None,
        limit: int = 100,
    ) -> list[NotificationDelivery]:
        if limit < 1:
            raise ValueError(
                "Due delivery limit must be "
                "positive"
            )

        check_time = at or _utc_now()

        if check_time.tzinfo is None:
            raise ValueError(
                "Due delivery check time must be "
                "timezone-aware"
            )

        with closing(
            self._connect()
        ) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM notification_deliveries
                WHERE
                    status = ?
                    AND (
                        scheduled_at IS NULL
                        OR scheduled_at <= ?
                    )
                ORDER BY
                    scheduled_at ASC,
                    created_at ASC,
                    delivery_id ASC
                LIMIT ?
                """,
                (
                    (
                        NotificationDeliveryStatus
                        .PENDING.value
                    ),
                    _datetime_text(check_time),
                    limit,
                ),
            ).fetchall()

        return [
            self._delivery_from_row(row)
            for row in rows
        ]

    def create_suppression(
        self,
        suppression: NotificationSuppression,
    ) -> NotificationSuppression:
        with closing(
            self._connect()
        ) as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO notification_suppressions (
                        suppression_id,
                        name,
                        kind,
                        enabled,
                        starts_at,
                        ends_at,
                        reason,
                        event_types_json,
                        site_ids_json,
                        device_ids_json,
                        metadata_json,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        suppression.suppression_id,
                        suppression.name,
                        suppression.kind.value,
                        int(suppression.enabled),
                        _datetime_text(
                            suppression.starts_at
                        ),
                        _datetime_text(
                            suppression.ends_at
                        ),
                        suppression.reason,
                        canonical_notification_json(
                            list(
                                suppression.event_types
                            )
                        ),
                        canonical_notification_json(
                            list(
                                suppression.site_ids
                            )
                        ),
                        canonical_notification_json(
                            list(
                                suppression.device_ids
                            )
                        ),
                        canonical_notification_json(
                            suppression.metadata
                        ),
                        _datetime_text(
                            suppression.created_at
                        ),
                        _datetime_text(
                            suppression.updated_at
                        ),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise NotificationDuplicate(
                    "Notification suppression "
                    "already exists"
                ) from exc

            connection.commit()

        return suppression

    def list_active_suppressions(
        self,
        *,
        at: datetime | None = None,
    ) -> list[NotificationSuppression]:
        check_time = at or _utc_now()

        with closing(
            self._connect()
        ) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM notification_suppressions
                WHERE
                    enabled = 1
                    AND starts_at <= ?
                    AND ends_at >= ?
                ORDER BY
                    starts_at ASC,
                    suppression_id ASC
                """,
                (
                    _datetime_text(check_time),
                    _datetime_text(check_time),
                ),
            ).fetchall()

        return [
            self._suppression_from_row(row)
            for row in rows
        ]

    def find_latest_delivery(
        self,
        *,
        incident_id: str,
        policy_id: str | None = None,
        notification_type: NotificationType
        | str
        | None = None,
        statuses: tuple[
            NotificationDeliveryStatus | str,
            ...,
        ] = (
            NotificationDeliveryStatus.SENT,
        ),
    ) -> NotificationDelivery | None:
        conditions = [
            "incident_id = ?",
        ]

        parameters: list[Any] = [
            incident_id,
        ]

        if policy_id is None:
            conditions.append(
                "policy_id IS NULL"
            )
        else:
            conditions.append(
                "policy_id = ?"
            )
            parameters.append(policy_id)

        if notification_type is not None:
            type_value = (
                notification_type.value
                if isinstance(
                    notification_type,
                    NotificationType,
                )
                else str(notification_type)
            )

            conditions.append(
                "notification_type = ?"
            )
            parameters.append(type_value)

        normalized_statuses = tuple(
            item.value
            if isinstance(
                item,
                NotificationDeliveryStatus,
            )
            else str(item)
            for item in statuses
        )

        if normalized_statuses:
            placeholders = ", ".join(
                "?"
                for _ in normalized_statuses
            )

            conditions.append(
                f"status IN ({placeholders})"
            )

            parameters.extend(
                normalized_statuses
            )

        where_clause = " AND ".join(
            conditions
        )

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                f"""
                SELECT *
                FROM notification_deliveries
                WHERE {where_clause}
                ORDER BY
                    COALESCE(
                        sent_at,
                        scheduled_at,
                        updated_at,
                        created_at
                    ) DESC,
                    created_at DESC,
                    delivery_id DESC
                LIMIT 1
                """,
                tuple(parameters),
            ).fetchone()

        if row is None:
            return None

        return self._delivery_from_row(row)

    def has_active_delivery(
        self,
        *,
        incident_id: str,
        policy_id: str | None,
        notification_type: NotificationType
        | str,
    ) -> bool:
        delivery = self.find_latest_delivery(
            incident_id=incident_id,
            policy_id=policy_id,
            notification_type=notification_type,
            statuses=(
                NotificationDeliveryStatus.PENDING,
                NotificationDeliveryStatus.SENDING,
            ),
        )

        return delivery is not None

    def find_latest_delivery(
        self,
        *,
        incident_id: str,
        policy_id: str | None = None,
        notification_type: NotificationType
        | str
        | None = None,
        statuses: tuple[
            NotificationDeliveryStatus | str,
            ...,
        ] = (
            NotificationDeliveryStatus.SENT,
        ),
    ) -> NotificationDelivery | None:
        conditions = [
            "incident_id = ?",
        ]

        parameters: list[Any] = [
            incident_id,
        ]

        if policy_id is None:
            conditions.append(
                "policy_id IS NULL"
            )
        else:
            conditions.append(
                "policy_id = ?"
            )
            parameters.append(policy_id)

        if notification_type is not None:
            type_value = (
                notification_type.value
                if isinstance(
                    notification_type,
                    NotificationType,
                )
                else str(notification_type)
            )

            conditions.append(
                "notification_type = ?"
            )
            parameters.append(type_value)

        normalized_statuses = tuple(
            item.value
            if isinstance(
                item,
                NotificationDeliveryStatus,
            )
            else str(item)
            for item in statuses
        )

        if normalized_statuses:
            placeholders = ", ".join(
                "?"
                for _ in normalized_statuses
            )

            conditions.append(
                f"status IN ({placeholders})"
            )

            parameters.extend(
                normalized_statuses
            )

        where_clause = " AND ".join(
            conditions
        )

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                f"""
                SELECT *
                FROM notification_deliveries
                WHERE {where_clause}
                ORDER BY
                    COALESCE(
                        sent_at,
                        scheduled_at,
                        updated_at,
                        created_at
                    ) DESC,
                    created_at DESC,
                    delivery_id DESC
                LIMIT 1
                """,
                tuple(parameters),
            ).fetchone()

        if row is None:
            return None

        return self._delivery_from_row(row)

    def has_active_delivery(
        self,
        *,
        incident_id: str,
        policy_id: str | None,
        notification_type: NotificationType
        | str,
    ) -> bool:
        delivery = self.find_latest_delivery(
            incident_id=incident_id,
            policy_id=policy_id,
            notification_type=notification_type,
            statuses=(
                NotificationDeliveryStatus.PENDING,
                NotificationDeliveryStatus.SENDING,
            ),
        )

        return delivery is not None

    def find_latest_delivery(
        self,
        *,
        incident_id: str,
        policy_id: str | None = None,
        notification_type: NotificationType
        | str
        | None = None,
        statuses: tuple[
            NotificationDeliveryStatus | str,
            ...,
        ] = (
            NotificationDeliveryStatus.SENT,
        ),
    ) -> NotificationDelivery | None:
        conditions = [
            "incident_id = ?",
        ]

        parameters: list[Any] = [
            incident_id,
        ]

        if policy_id is None:
            conditions.append(
                "policy_id IS NULL"
            )
        else:
            conditions.append(
                "policy_id = ?"
            )
            parameters.append(policy_id)

        if notification_type is not None:
            type_value = (
                notification_type.value
                if isinstance(
                    notification_type,
                    NotificationType,
                )
                else str(notification_type)
            )

            conditions.append(
                "notification_type = ?"
            )
            parameters.append(type_value)

        normalized_statuses = tuple(
            item.value
            if isinstance(
                item,
                NotificationDeliveryStatus,
            )
            else str(item)
            for item in statuses
        )

        if normalized_statuses:
            placeholders = ", ".join(
                "?"
                for _ in normalized_statuses
            )

            conditions.append(
                f"status IN ({placeholders})"
            )

            parameters.extend(
                normalized_statuses
            )

        where_clause = " AND ".join(
            conditions
        )

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                f"""
                SELECT *
                FROM notification_deliveries
                WHERE {where_clause}
                ORDER BY
                    COALESCE(
                        sent_at,
                        scheduled_at,
                        updated_at,
                        created_at
                    ) DESC,
                    created_at DESC,
                    delivery_id DESC
                LIMIT 1
                """,
                tuple(parameters),
            ).fetchone()

        if row is None:
            return None

        return self._delivery_from_row(row)

    def has_active_delivery(
        self,
        *,
        incident_id: str,
        policy_id: str | None,
        notification_type: NotificationType
        | str,
    ) -> bool:
        delivery = self.find_latest_delivery(
            incident_id=incident_id,
            policy_id=policy_id,
            notification_type=notification_type,
            statuses=(
                NotificationDeliveryStatus.PENDING,
                NotificationDeliveryStatus.SENDING,
            ),
        )

        return delivery is not None

    def history_count(
        self,
        *,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> int:
        conditions: list[str] = []
        parameters: list[Any] = []

        if entity_type is not None:
            conditions.append(
                "entity_type = ?"
            )
            parameters.append(entity_type)

        if entity_id is not None:
            conditions.append(
                "entity_id = ?"
            )
            parameters.append(entity_id)

        where_clause = (
            "WHERE " + " AND ".join(conditions)
            if conditions
            else ""
        )

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                f"""
                SELECT COUNT(*) AS total
                FROM notification_history
                {where_clause}
                """,
                tuple(parameters),
            ).fetchone()

        return int(row["total"])
