from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.models.notification_audit import (
    NotificationAuditResult,
)

from app.models.notification_audit_stats import (
    NotificationAuditStats,
)

from app.services.notification_audit import (
    NotificationAuditStore,
)


class NotificationAuditAnalytics:


    def __init__(
        self,
        store: NotificationAuditStore | None = None,
    ):

        self.store = (
            store
            or NotificationAuditStore(
                Path(
                    "notifications.sqlite3"
                )
            )
        )


    def generate_stats(
        self,
    ) -> NotificationAuditStats:


        records = (
            self.store.list_audits()
        )


        total_events = len(records)


        success_count = sum(
            1
            for item in records
            if item.result
            == NotificationAuditResult.SUCCESS
        )


        failed_count = sum(
            1
            for item in records
            if item.result
            == NotificationAuditResult.FAILED
        )


        denied_count = sum(
            1
            for item in records
            if item.result
            == NotificationAuditResult.DENIED
        )


        action_distribution: dict[str, int] = {}


        for item in records:

            action = item.action.value

            action_distribution[action] = (
                action_distribution.get(
                    action,
                    0,
                )
                + 1
            )


        identity_counter: dict[str, int] = {}


        for item in records:

            identity_counter[
                item.identity_id
            ] = (
                identity_counter.get(
                    item.identity_id,
                    0,
                )
                + 1
            )


        top_identities = [
            {
                "identity_id": identity,
                "count": count,
            }
            for identity, count
            in sorted(
                identity_counter.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:10]
        ]


        return NotificationAuditStats(

            total_events=total_events,

            success_count=success_count,

            failed_count=failed_count,

            denied_count=denied_count,

            action_distribution=(
                action_distribution
            ),

            top_identities=(
                top_identities
            ),

            generated_at=(
                datetime.now(
                    timezone.utc
                )
            ),
        )
