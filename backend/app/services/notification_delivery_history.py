from __future__ import annotations

import sqlite3

from contextlib import closing
from pathlib import Path

from app.models.notification import (
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationType,
)
from app.services.notification_store import (
    NotificationStore,
)


class NotificationDeliveryHistory:
    """
    Read-only delivery-history queries used by notification
    deduplication and cooldown decisions.

    This repository intentionally remains separate from
    NotificationStore so the existing persistence component
    does not need to be patched or expanded indirectly.
    """

    def __init__(
        self,
        store: NotificationStore,
    ) -> None:
        self.store = store
        self.database_path = Path(
            store.database_path
        )

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

    @staticmethod
    def _enum_value(
        value: NotificationType
        | NotificationDeliveryStatus
        | str,
    ) -> str:
        if hasattr(value, "value"):
            return str(value.value)

        return str(value)

    def find_latest(
        self,
        *,
        incident_id: str,
        policy_id: str | None,
        notification_type: NotificationType | str,
        statuses: tuple[
            NotificationDeliveryStatus | str,
            ...,
        ],
    ) -> NotificationDelivery | None:
        conditions = [
            "incident_id = ?",
        ]

        parameters: list[object] = [
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
            parameters.append(
                policy_id
            )

        conditions.append(
            "notification_type = ?"
        )
        parameters.append(
            self._enum_value(
                notification_type
            )
        )

        normalized_statuses = tuple(
            self._enum_value(item)
            for item in statuses
        )

        if not normalized_statuses:
            return None

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

        return self.store._delivery_from_row(
            row
        )

    def find_latest_sent(
        self,
        *,
        incident_id: str,
        policy_id: str | None,
        notification_type: NotificationType | str,
    ) -> NotificationDelivery | None:
        return self.find_latest(
            incident_id=incident_id,
            policy_id=policy_id,
            notification_type=notification_type,
            statuses=(
                NotificationDeliveryStatus.SENT,
            ),
        )

    def find_latest_active(
        self,
        *,
        incident_id: str,
        policy_id: str | None,
        notification_type: NotificationType | str,
    ) -> NotificationDelivery | None:
        return self.find_latest(
            incident_id=incident_id,
            policy_id=policy_id,
            notification_type=notification_type,
            statuses=(
                NotificationDeliveryStatus.PENDING,
                NotificationDeliveryStatus.SENDING,
            ),
        )

    def has_active(
        self,
        *,
        incident_id: str,
        policy_id: str | None,
        notification_type: NotificationType | str,
    ) -> bool:
        return (
            self.find_latest_active(
                incident_id=incident_id,
                policy_id=policy_id,
                notification_type=notification_type,
            )
            is not None
        )
