from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from app.models.notification_audit import (
    NotificationAuditResult,
)

from app.models.notification_audit_timeline import (
    NotificationAuditTimeline,
    NotificationAuditTimelinePoint,
)

from app.services.notification_audit import (
    NotificationAuditStore,
)


class NotificationAuditTimelineAnalytics:


    def __init__(
        self,
        store: NotificationAuditStore,
    ):

        self.store = store



    def generate(
        self,
        period: str = "hour",
    ) -> NotificationAuditTimeline:


        records = (
            self.store.list_audits()
        )


        buckets = defaultdict(
            lambda: {
                "total": 0,
                "success": 0,
                "failed": 0,
                "denied": 0,
            }
        )


        for record in records:

            timestamp = (
                record.created_at
            )


            if period == "day":

                bucket = timestamp.replace(
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )

            else:

                bucket = timestamp.replace(
                    minute=0,
                    second=0,
                    microsecond=0,
                )


            data = buckets[bucket]


            data["total"] += 1


            if (
                record.result
                == NotificationAuditResult.SUCCESS
            ):

                data["success"] += 1


            elif (
                record.result
                == NotificationAuditResult.FAILED
            ):

                data["failed"] += 1


            elif (
                record.result
                == NotificationAuditResult.DENIED
            ):

                data["denied"] += 1



        points = [

            NotificationAuditTimelinePoint(

                timestamp=timestamp,

                total=data["total"],

                success=data["success"],

                failed=data["failed"],

                denied=data["denied"],
            )

            for timestamp, data
            in sorted(
                buckets.items()
            )
        ]



        return NotificationAuditTimeline(

            period=period,

            points=points,

            generated_at=datetime.now(
                timezone.utc
            ),
        )
