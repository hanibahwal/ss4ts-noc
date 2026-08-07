from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.services.noc_wall_dashboard_store import (
    NOCWallDashboardRecord,
    NOCWallDashboardStore,
)


API_SERVICE_NAME = (
    "SS4TS NOC Wall Dashboard API"
)

API_SERVICE_VERSION = "1.0.0"


class NOCWallDashboardAPIError(
    RuntimeError
):
    pass


class NOCWallDashboardAPINotFound(
    NOCWallDashboardAPIError
):
    pass


class NOCWallDashboardAPIIntegrityError(
    NOCWallDashboardAPIError
):
    pass


def _normalize_generated_at(
    value: datetime | None,
) -> datetime:
    resolved = (
        value
        or datetime.now(
            timezone.utc
        )
    )

    if not isinstance(
        resolved,
        datetime,
    ):
        raise TypeError(
            "generated_at must be a datetime"
        )

    if (
        resolved.tzinfo is None
        or resolved.utcoffset() is None
    ):
        raise ValueError(
            "generated_at must be timezone-aware"
        )

    return resolved.astimezone(
        timezone.utc
    )


@dataclass(
    frozen=True,
    slots=True,
)
class NOCWallDashboardAPIResponse:
    success: bool
    operation: str
    data: dict[str, Any]

    generated_at: datetime

    service_name: str = (
        API_SERVICE_NAME
    )

    service_version: str = (
        API_SERVICE_VERSION
    )

    @property
    def incident_created(
        self,
    ) -> bool:
        return False

    @property
    def recommendation_executed(
        self,
    ) -> bool:
        return False

    @property
    def decision_created(
        self,
    ) -> bool:
        return False

    @property
    def authorization_created(
        self,
    ) -> bool:
        return False

    @property
    def execution_allowed(
        self,
    ) -> bool:
        return False

    @property
    def can_execute(
        self,
    ) -> bool:
        return False

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "success":
                self.success,
            "operation":
                self.operation,
            "data":
                dict(
                    self.data
                ),
            "generated_at":
                self.generated_at.isoformat(),
            "service_name":
                self.service_name,
            "service_version":
                self.service_version,
            "incident_created":
                False,
            "recommendation_executed":
                False,
            "decision_created":
                False,
            "authorization_created":
                False,
            "execution_allowed":
                False,
            "can_execute":
                False,
            "safety": {
                "read_only_api":
                    True,
                "dashboard_store_mutated":
                    False,
                "incident_created":
                    False,
                "recommendation_executed":
                    False,
                "decision_created":
                    False,
                "authorization_created":
                    False,
                "execution_allowed":
                    False,
                "network_device_access":
                    False,
                "command_generated":
                    False,
                "device_command_executed":
                    False,
            },
        }


class NOCWallDashboardAPI:
    def __init__(
        self,
        *,
        store: NOCWallDashboardStore,
    ) -> None:
        if not isinstance(
            store,
            NOCWallDashboardStore,
        ):
            raise TypeError(
                "store must be a "
                "NOCWallDashboardStore"
            )

        self.store = store

    def _verify_store(
        self,
    ) -> None:
        if not self.store.verify_chain():
            raise NOCWallDashboardAPIIntegrityError(
                "NOC wall dashboard store "
                "integrity verification failed"
            )

    @staticmethod
    def _summary(
        record: NOCWallDashboardRecord,
    ) -> dict[str, Any]:
        return {
            "sequence_number":
                record.sequence_number,
            "dashboard_id":
                record.dashboard_id,
            "dashboard_fingerprint":
                record.dashboard_fingerprint,
            "generated_at":
                record.generated_at,
            "overall_status":
                record.overall_status,
            "overall_health_score":
                record.overall_health_score,
            "overall_trend":
                record.overall_trend,
            "total_sites":
                record.total_sites,
            "total_devices":
                record.total_devices,
            "total_links":
                record.total_links,
            "active_incidents":
                record.active_incidents,
            "active_predictions":
                record.active_predictions,
            "pending_human_approvals":
                record.pending_human_approvals,
            "latest_report_id":
                record.latest_report_id,
            "validation_valid":
                record.validation_valid,
            "dashboard_accepted":
                record.dashboard_accepted,
            "stored_at":
                record.stored_at,
            "record_hash":
                record.record_hash,
        }

    def latest(
        self,
        *,
        generated_at: datetime | None = None,
    ) -> NOCWallDashboardAPIResponse:
        resolved_generated_at = (
            _normalize_generated_at(
                generated_at
            )
        )

        self._verify_store()

        records = self.store.list_records(
            limit=1_000_000
        )

        if not records:
            raise NOCWallDashboardAPINotFound(
                "No dashboard snapshots "
                "are available"
            )

        record = records[-1]

        return NOCWallDashboardAPIResponse(
            success=True,
            operation="latest",
            data={
                "dashboard":
                    record.to_dict(),
                "store_record_count":
                    len(
                        records
                    ),
                "store_chain_valid":
                    True,
            },
            generated_at=(
                resolved_generated_at
            ),
        )

    def history(
        self,
        *,
        limit: int = 100,
        status: str | None = None,
        generated_at: datetime | None = None,
    ) -> NOCWallDashboardAPIResponse:
        resolved_generated_at = (
            _normalize_generated_at(
                generated_at
            )
        )

        if (
            isinstance(
                limit,
                bool,
            )
            or not isinstance(
                limit,
                int,
            )
        ):
            raise TypeError(
                "limit must be an integer"
            )

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero"
            )

        normalized_status = None

        if status is not None:
            normalized_status = str(
                status
            ).strip().lower()

            if normalized_status not in {
                "healthy",
                "degraded",
                "critical",
                "unknown",
            }:
                raise ValueError(
                    "status is invalid"
                )

        self._verify_store()

        records = self.store.list_records(
            limit=1_000_000
        )

        if normalized_status is not None:
            records = tuple(
                record
                for record in records
                if record.overall_status
                == normalized_status
            )

        selected = records[
            -limit:
        ]

        return NOCWallDashboardAPIResponse(
            success=True,
            operation="history",
            data={
                "dashboards": [
                    self._summary(
                        record
                    )
                    for record in selected
                ],
                "returned_count":
                    len(
                        selected
                    ),
                "matching_count":
                    len(
                        records
                    ),
                "status_filter":
                    normalized_status,
                "store_chain_valid":
                    True,
            },
            generated_at=(
                resolved_generated_at
            ),
        )

    def get_snapshot(
        self,
        *,
        dashboard_id: str,
        generated_at: datetime | None = None,
    ) -> NOCWallDashboardAPIResponse:
        resolved_generated_at = (
            _normalize_generated_at(
                generated_at
            )
        )

        normalized_dashboard_id = str(
            dashboard_id
        ).strip()

        if not normalized_dashboard_id:
            raise ValueError(
                "dashboard_id must not be empty"
            )

        self._verify_store()

        record = self.store.get(
            normalized_dashboard_id
        )

        if record is None:
            raise NOCWallDashboardAPINotFound(
                "Dashboard snapshot "
                "was not found"
            )

        if not record.verify_hash():
            raise NOCWallDashboardAPIIntegrityError(
                "Dashboard record hash "
                "is invalid"
            )

        return NOCWallDashboardAPIResponse(
            success=True,
            operation="get_snapshot",
            data={
                "dashboard":
                    record.to_dict(),
                "store_chain_valid":
                    True,
            },
            generated_at=(
                resolved_generated_at
            ),
        )

    def get_by_fingerprint(
        self,
        *,
        dashboard_fingerprint: str,
        generated_at: datetime | None = None,
    ) -> NOCWallDashboardAPIResponse:
        resolved_generated_at = (
            _normalize_generated_at(
                generated_at
            )
        )

        normalized = str(
            dashboard_fingerprint
        ).strip()

        if not normalized:
            raise ValueError(
                "dashboard_fingerprint "
                "must not be empty"
            )

        self._verify_store()

        record = self.store.get_by_fingerprint(
            normalized
        )

        if record is None:
            raise NOCWallDashboardAPINotFound(
                "Dashboard snapshot "
                "was not found"
            )

        return NOCWallDashboardAPIResponse(
            success=True,
            operation="get_by_fingerprint",
            data={
                "dashboard":
                    record.to_dict(),
                "store_chain_valid":
                    True,
            },
            generated_at=(
                resolved_generated_at
            ),
        )

    def health(
        self,
        *,
        generated_at: datetime | None = None,
    ) -> NOCWallDashboardAPIResponse:
        resolved_generated_at = (
            _normalize_generated_at(
                generated_at
            )
        )

        chain_valid = (
            self.store.verify_chain()
        )

        record_count = (
            self.store.count()
        )

        latest_status = None
        latest_health_score = None
        latest_dashboard_id = None

        if chain_valid and record_count:
            records = self.store.list_records(
                limit=1_000_000
            )

            latest_record = records[-1]

            latest_status = (
                latest_record.overall_status
            )

            latest_health_score = (
                latest_record
                .overall_health_score
            )

            latest_dashboard_id = (
                latest_record.dashboard_id
            )

        return NOCWallDashboardAPIResponse(
            success=chain_valid,
            operation="health",
            data={
                "service_status": (
                    "healthy"
                    if chain_valid
                    else "integrity_failure"
                ),
                "store_chain_valid":
                    chain_valid,
                "store_record_count":
                    record_count,
                "latest_dashboard_id":
                    latest_dashboard_id,
                "latest_status":
                    latest_status,
                "latest_health_score":
                    latest_health_score,
                "read_only":
                    True,
            },
            generated_at=(
                resolved_generated_at
            ),
        )


def get_latest_noc_wall_dashboard(
    *,
    store: NOCWallDashboardStore,
    generated_at: datetime | None = None,
) -> NOCWallDashboardAPIResponse:
    return NOCWallDashboardAPI(
        store=store
    ).latest(
        generated_at=generated_at
    )


def list_noc_wall_dashboard_history(
    *,
    store: NOCWallDashboardStore,
    limit: int = 100,
    status: str | None = None,
    generated_at: datetime | None = None,
) -> NOCWallDashboardAPIResponse:
    return NOCWallDashboardAPI(
        store=store
    ).history(
        limit=limit,
        status=status,
        generated_at=generated_at,
    )


def get_noc_wall_dashboard_snapshot(
    *,
    store: NOCWallDashboardStore,
    dashboard_id: str,
    generated_at: datetime | None = None,
) -> NOCWallDashboardAPIResponse:
    return NOCWallDashboardAPI(
        store=store
    ).get_snapshot(
        dashboard_id=dashboard_id,
        generated_at=generated_at,
    )


def get_noc_wall_dashboard_health(
    *,
    store: NOCWallDashboardStore,
    generated_at: datetime | None = None,
) -> NOCWallDashboardAPIResponse:
    return NOCWallDashboardAPI(
        store=store
    ).health(
        generated_at=generated_at
    )
