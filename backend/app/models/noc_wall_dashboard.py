from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any


DASHBOARD_SCHEMA_VERSION = "1.0"


class NOCWallDashboardStatus(
    str,
    Enum,
):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class NOCWallDashboardTrend(
    str,
    Enum,
):
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    UNKNOWN = "unknown"


class NOCWallDashboardSeverity(
    str,
    Enum,
):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


def _canonical_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _normalize_required_text(
    value: str,
    *,
    field_name: str,
) -> str:
    normalized = str(
        value
    ).strip()

    if not normalized:
        raise ValueError(
            f"{field_name} must not be empty"
        )

    return normalized


def _normalize_datetime(
    value: datetime,
    *,
    field_name: str,
) -> datetime:
    if not isinstance(
        value,
        datetime,
    ):
        raise TypeError(
            f"{field_name} must be a datetime"
        )

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            f"{field_name} must be timezone-aware"
        )

    return value.astimezone(
        timezone.utc
    )


def _normalize_string_tuple(
    values: tuple[str, ...],
) -> tuple[str, ...]:
    if not isinstance(
        values,
        tuple,
    ):
        raise TypeError(
            "collection fields must be tuples"
        )

    normalized = tuple(
        str(
            value
        ).strip()
        for value in values
        if str(
            value
        ).strip()
    )

    if len(
        normalized
    ) != len(
        set(
            normalized
        )
    ):
        raise ValueError(
            "collection fields must not contain duplicates"
        )

    return normalized


@dataclass(
    frozen=True,
    slots=True,
)
class NOCWallDashboardAlert:
    alert_id: str
    title: str
    message: str

    severity: NOCWallDashboardSeverity
    source: str

    created_at: datetime

    site_id: str | None = None
    device_id: str | None = None
    link_id: str | None = None
    service_id: str | None = None

    acknowledged: bool = False

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "alert_id",
            _normalize_required_text(
                self.alert_id,
                field_name="alert_id",
            ),
        )

        object.__setattr__(
            self,
            "title",
            _normalize_required_text(
                self.title,
                field_name="title",
            ),
        )

        object.__setattr__(
            self,
            "message",
            _normalize_required_text(
                self.message,
                field_name="message",
            ),
        )

        object.__setattr__(
            self,
            "source",
            _normalize_required_text(
                self.source,
                field_name="source",
            ),
        )

        object.__setattr__(
            self,
            "created_at",
            _normalize_datetime(
                self.created_at,
                field_name="created_at",
            ),
        )

        if not isinstance(
            self.severity,
            NOCWallDashboardSeverity,
        ):
            raise TypeError(
                "severity must be a "
                "NOCWallDashboardSeverity"
            )

        if not isinstance(
            self.acknowledged,
            bool,
        ):
            raise TypeError(
                "acknowledged must be a bool"
            )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "alert_id":
                self.alert_id,
            "title":
                self.title,
            "message":
                self.message,
            "severity":
                self.severity.value,
            "source":
                self.source,
            "created_at":
                self.created_at.isoformat(),
            "site_id":
                self.site_id,
            "device_id":
                self.device_id,
            "link_id":
                self.link_id,
            "service_id":
                self.service_id,
            "acknowledged":
                self.acknowledged,
        }


@dataclass(
    frozen=True,
    slots=True,
)
class NOCWallDashboardSnapshot:
    dashboard_id: str
    generated_at: datetime

    overall_status: NOCWallDashboardStatus
    overall_health_score: float
    overall_trend: NOCWallDashboardTrend

    total_sites: int
    healthy_sites: int
    degraded_sites: int
    critical_sites: int
    unknown_sites: int

    total_devices: int
    online_devices: int
    offline_devices: int
    degraded_devices: int

    total_links: int
    healthy_links: int
    degraded_links: int
    down_links: int

    active_incidents: int
    critical_incidents: int
    high_priority_incidents: int

    active_predictions: int
    critical_predictions: int
    high_risk_predictions: int

    pending_human_approvals: int
    approved_but_not_executable: int

    latest_report_id: str | None = None
    latest_report_fingerprint: str | None = None
    latest_report_health_score: float | None = None

    affected_sites: tuple[str, ...] = ()
    affected_devices: tuple[str, ...] = ()
    affected_links: tuple[str, ...] = ()
    affected_services: tuple[str, ...] = ()

    alerts: tuple[NOCWallDashboardAlert, ...] = ()

    source_audit_ids: tuple[str, ...] = ()
    source_record_hashes: tuple[str, ...] = ()

    generated_by: str = (
        "SS4TS NOC Wall Dashboard Builder"
    )

    schema_version: str = (
        DASHBOARD_SCHEMA_VERSION
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    dashboard_fingerprint: str = ""

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "dashboard_id",
            _normalize_required_text(
                self.dashboard_id,
                field_name="dashboard_id",
            ),
        )

        object.__setattr__(
            self,
            "generated_at",
            _normalize_datetime(
                self.generated_at,
                field_name="generated_at",
            ),
        )

        if not isinstance(
            self.overall_status,
            NOCWallDashboardStatus,
        ):
            raise TypeError(
                "overall_status must be a "
                "NOCWallDashboardStatus"
            )

        if not isinstance(
            self.overall_trend,
            NOCWallDashboardTrend,
        ):
            raise TypeError(
                "overall_trend must be a "
                "NOCWallDashboardTrend"
            )

        if (
            isinstance(
                self.overall_health_score,
                bool,
            )
            or not isinstance(
                self.overall_health_score,
                (
                    int,
                    float,
                ),
            )
        ):
            raise TypeError(
                "overall_health_score must be numeric"
            )

        if not (
            0
            <= float(
                self.overall_health_score
            )
            <= 100
        ):
            raise ValueError(
                "overall_health_score must be "
                "between 0 and 100"
            )

        object.__setattr__(
            self,
            "overall_health_score",
            round(
                float(
                    self.overall_health_score
                ),
                2,
            ),
        )

        counter_fields = (
            "total_sites",
            "healthy_sites",
            "degraded_sites",
            "critical_sites",
            "unknown_sites",
            "total_devices",
            "online_devices",
            "offline_devices",
            "degraded_devices",
            "total_links",
            "healthy_links",
            "degraded_links",
            "down_links",
            "active_incidents",
            "critical_incidents",
            "high_priority_incidents",
            "active_predictions",
            "critical_predictions",
            "high_risk_predictions",
            "pending_human_approvals",
            "approved_but_not_executable",
        )

        for field_name in counter_fields:
            value = getattr(
                self,
                field_name,
            )

            if (
                isinstance(
                    value,
                    bool,
                )
                or not isinstance(
                    value,
                    int,
                )
            ):
                raise TypeError(
                    f"{field_name} must be an integer"
                )

            if value < 0:
                raise ValueError(
                    f"{field_name} must not be negative"
                )

        if (
            self.healthy_sites
            + self.degraded_sites
            + self.critical_sites
            + self.unknown_sites
            != self.total_sites
        ):
            raise ValueError(
                "site counters must equal total_sites"
            )

        if (
            self.online_devices
            + self.offline_devices
            + self.degraded_devices
            != self.total_devices
        ):
            raise ValueError(
                "device counters must equal total_devices"
            )

        if (
            self.healthy_links
            + self.degraded_links
            + self.down_links
            != self.total_links
        ):
            raise ValueError(
                "link counters must equal total_links"
            )

        if (
            self.critical_incidents
            + self.high_priority_incidents
            > self.active_incidents
        ):
            raise ValueError(
                "incident severity counters exceed "
                "active_incidents"
            )

        if (
            self.critical_predictions
            + self.high_risk_predictions
            > self.active_predictions
        ):
            raise ValueError(
                "prediction severity counters exceed "
                "active_predictions"
            )

        if (
            self.approved_but_not_executable
            > self.pending_human_approvals
        ):
            raise ValueError(
                "approved_but_not_executable exceeds "
                "pending_human_approvals"
            )

        if (
            self.latest_report_health_score
            is not None
        ):
            score = float(
                self.latest_report_health_score
            )

            if not (
                0
                <= score
                <= 100
            ):
                raise ValueError(
                    "latest_report_health_score must be "
                    "between 0 and 100"
                )

            object.__setattr__(
                self,
                "latest_report_health_score",
                round(
                    score,
                    2,
                ),
            )

        for field_name in (
            "affected_sites",
            "affected_devices",
            "affected_links",
            "affected_services",
            "source_audit_ids",
            "source_record_hashes",
        ):
            object.__setattr__(
                self,
                field_name,
                _normalize_string_tuple(
                    getattr(
                        self,
                        field_name,
                    )
                ),
            )

        if not isinstance(
            self.alerts,
            tuple,
        ):
            raise TypeError(
                "alerts must be a tuple"
            )

        if not all(
            isinstance(
                alert,
                NOCWallDashboardAlert,
            )
            for alert in self.alerts
        ):
            raise TypeError(
                "alerts must contain only "
                "NOCWallDashboardAlert values"
            )

        alert_ids = tuple(
            alert.alert_id
            for alert in self.alerts
        )

        if len(
            alert_ids
        ) != len(
            set(
                alert_ids
            )
        ):
            raise ValueError(
                "alerts must not contain duplicate IDs"
            )

        object.__setattr__(
            self,
            "generated_by",
            _normalize_required_text(
                self.generated_by,
                field_name="generated_by",
            ),
        )

        object.__setattr__(
            self,
            "schema_version",
            _normalize_required_text(
                self.schema_version,
                field_name="schema_version",
            ),
        )

        if not isinstance(
            self.metadata,
            dict,
        ):
            raise TypeError(
                "metadata must be a dictionary"
            )

        calculated = (
            self.calculate_fingerprint()
        )

        if self.dashboard_fingerprint:
            if (
                self.dashboard_fingerprint
                != calculated
            ):
                raise ValueError(
                    "dashboard_fingerprint is invalid"
                )
        else:
            object.__setattr__(
                self,
                "dashboard_fingerprint",
                calculated,
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

    def fingerprint_payload(
        self,
    ) -> dict[str, Any]:
        return {
            "dashboard_id":
                self.dashboard_id,
            "generated_at":
                self.generated_at.isoformat(),
            "overall_status":
                self.overall_status.value,
            "overall_health_score":
                self.overall_health_score,
            "overall_trend":
                self.overall_trend.value,
            "total_sites":
                self.total_sites,
            "healthy_sites":
                self.healthy_sites,
            "degraded_sites":
                self.degraded_sites,
            "critical_sites":
                self.critical_sites,
            "unknown_sites":
                self.unknown_sites,
            "total_devices":
                self.total_devices,
            "online_devices":
                self.online_devices,
            "offline_devices":
                self.offline_devices,
            "degraded_devices":
                self.degraded_devices,
            "total_links":
                self.total_links,
            "healthy_links":
                self.healthy_links,
            "degraded_links":
                self.degraded_links,
            "down_links":
                self.down_links,
            "active_incidents":
                self.active_incidents,
            "critical_incidents":
                self.critical_incidents,
            "high_priority_incidents":
                self.high_priority_incidents,
            "active_predictions":
                self.active_predictions,
            "critical_predictions":
                self.critical_predictions,
            "high_risk_predictions":
                self.high_risk_predictions,
            "pending_human_approvals":
                self.pending_human_approvals,
            "approved_but_not_executable":
                self.approved_but_not_executable,
            "latest_report_id":
                self.latest_report_id,
            "latest_report_fingerprint":
                self.latest_report_fingerprint,
            "latest_report_health_score":
                self.latest_report_health_score,
            "affected_sites":
                list(
                    self.affected_sites
                ),
            "affected_devices":
                list(
                    self.affected_devices
                ),
            "affected_links":
                list(
                    self.affected_links
                ),
            "affected_services":
                list(
                    self.affected_services
                ),
            "alerts": [
                alert.to_dict()
                for alert in self.alerts
            ],
            "source_audit_ids":
                list(
                    self.source_audit_ids
                ),
            "source_record_hashes":
                list(
                    self.source_record_hashes
                ),
            "generated_by":
                self.generated_by,
            "schema_version":
                self.schema_version,
            "metadata":
                self.metadata,
        }

    def calculate_fingerprint(
        self,
    ) -> str:
        return hashlib.sha256(
            _canonical_json(
                self.fingerprint_payload()
            ).encode(
                "utf-8"
            )
        ).hexdigest()

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            **self.fingerprint_payload(),
            "dashboard_fingerprint":
                self.dashboard_fingerprint,
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
                "display_only":
                    True,
                "read_only_snapshot":
                    True,
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
                "network_io_performed":
                    False,
                "device_access_performed":
                    False,
                "command_generated":
                    False,
                "device_command_executed":
                    False,
            },
        }
