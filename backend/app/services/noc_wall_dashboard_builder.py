from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid5

from app.models.noc_wall_dashboard import (
    NOCWallDashboardAlert,
    NOCWallDashboardSeverity,
    NOCWallDashboardSnapshot,
    NOCWallDashboardStatus,
    NOCWallDashboardTrend,
)
from app.services.executive_predictive_report_store import (
    ExecutivePredictiveReportRecord,
    ExecutivePredictiveReportStore,
)
from app.services.executive_predictive_report_store_audit import (
    ExecutivePredictiveReportStoreAuditReport,
    verify_executive_predictive_report_store,
)


BUILDER_SERVICE_NAME = (
    "SS4TS NOC Wall Dashboard Builder"
)

BUILDER_SERVICE_VERSION = "1.0.0"

DASHBOARD_NAMESPACE = UUID(
    "da632342-5f72-4dd1-b682-c9ea378d4e22"
)


@dataclass(
    frozen=True,
    slots=True,
)
class NOCWallDashboardOperationalState:
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

    pending_human_approvals: int
    approved_but_not_executable: int

    affected_sites: tuple[str, ...] = ()
    affected_devices: tuple[str, ...] = ()
    affected_links: tuple[str, ...] = ()
    affected_services: tuple[str, ...] = ()

    metadata: dict[str, Any] | None = None

    def __post_init__(
        self,
    ) -> None:
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
            self.approved_but_not_executable
            > self.pending_human_approvals
        ):
            raise ValueError(
                "approved_but_not_executable exceeds "
                "pending_human_approvals"
            )

        for field_name in (
            "affected_sites",
            "affected_devices",
            "affected_links",
            "affected_services",
        ):
            value = getattr(
                self,
                field_name,
            )

            if not isinstance(
                value,
                tuple,
            ):
                raise TypeError(
                    f"{field_name} must be a tuple"
                )

        if (
            self.metadata is not None
            and not isinstance(
                self.metadata,
                dict,
            )
        ):
            raise TypeError(
                "metadata must be a dictionary"
            )


class NOCWallDashboardBuilder:
    @staticmethod
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

    @staticmethod
    def _latest_report(
        store: ExecutivePredictiveReportStore,
    ) -> ExecutivePredictiveReportRecord | None:
        records = store.list_records(
            limit=1_000_000
        )

        if not records:
            return None

        return records[-1]

    @staticmethod
    def _merge_values(
        *collections: tuple[str, ...],
    ) -> tuple[str, ...]:
        result: list[str] = []
        seen: set[str] = set()

        for collection in collections:
            for value in collection:
                normalized = str(
                    value
                ).strip()

                if (
                    normalized
                    and normalized not in seen
                ):
                    seen.add(
                        normalized
                    )
                    result.append(
                        normalized
                    )

        return tuple(
            result
        )

    @staticmethod
    def _operational_health_score(
        state: NOCWallDashboardOperationalState,
    ) -> float:
        penalty = 0.0

        if state.total_sites:
            penalty += (
                state.degraded_sites
                / state.total_sites
            ) * 15

            penalty += (
                state.critical_sites
                / state.total_sites
            ) * 30

            penalty += (
                state.unknown_sites
                / state.total_sites
            ) * 8

        if state.total_devices:
            penalty += (
                state.degraded_devices
                / state.total_devices
            ) * 12

            penalty += (
                state.offline_devices
                / state.total_devices
            ) * 25

        if state.total_links:
            penalty += (
                state.degraded_links
                / state.total_links
            ) * 15

            penalty += (
                state.down_links
                / state.total_links
            ) * 30

        penalty += min(
            20.0,
            state.critical_incidents * 8.0,
        )

        penalty += min(
            10.0,
            state.high_priority_incidents * 3.0,
        )

        return round(
            max(
                0.0,
                100.0 - penalty,
            ),
            2,
        )

    @staticmethod
    def _overall_health_score(
        *,
        operational_score: float,
        latest_report: (
            ExecutivePredictiveReportRecord
            | None
        ),
    ) -> float:
        if latest_report is None:
            return operational_score

        return round(
            (
                operational_score * 0.6
                + latest_report.overall_health_score
                * 0.4
            ),
            2,
        )

    @staticmethod
    def _overall_status(
        *,
        state: NOCWallDashboardOperationalState,
        latest_report: (
            ExecutivePredictiveReportRecord
            | None
        ),
        health_score: float,
    ) -> NOCWallDashboardStatus:
        report_risk = (
            latest_report.overall_risk_class
            if latest_report is not None
            else "low"
        )

        if any(
            (
                state.critical_sites > 0,
                state.down_links > 0,
                state.critical_incidents > 0,
                report_risk == "critical",
                health_score < 50,
            )
        ):
            return NOCWallDashboardStatus.CRITICAL

        if any(
            (
                state.degraded_sites > 0,
                state.offline_devices > 0,
                state.degraded_devices > 0,
                state.degraded_links > 0,
                state.high_priority_incidents > 0,
                report_risk in {
                    "high",
                    "medium",
                },
                health_score < 85,
            )
        ):
            return NOCWallDashboardStatus.DEGRADED

        if (
            state.total_sites == 0
            and state.total_devices == 0
            and state.total_links == 0
            and latest_report is None
        ):
            return NOCWallDashboardStatus.UNKNOWN

        return NOCWallDashboardStatus.HEALTHY

    @staticmethod
    def _overall_trend(
        *,
        latest_report: (
            ExecutivePredictiveReportRecord
            | None
        ),
        status: NOCWallDashboardStatus,
    ) -> NOCWallDashboardTrend:
        if latest_report is not None:
            outlook = (
                latest_report.service_outlook
            )

            if outlook == "improving":
                return (
                    NOCWallDashboardTrend.IMPROVING
                )

            if outlook in {
                "degrading",
                "critical",
                "watch",
            }:
                return (
                    NOCWallDashboardTrend.DEGRADING
                )

            if outlook == "stable":
                return (
                    NOCWallDashboardTrend.STABLE
                )

        if status is NOCWallDashboardStatus.UNKNOWN:
            return NOCWallDashboardTrend.UNKNOWN

        if status in {
            NOCWallDashboardStatus.CRITICAL,
            NOCWallDashboardStatus.DEGRADED,
        }:
            return NOCWallDashboardTrend.DEGRADING

        return NOCWallDashboardTrend.STABLE

    @staticmethod
    def _alert(
        *,
        alert_id: str,
        title: str,
        message: str,
        severity: NOCWallDashboardSeverity,
        source: str,
        generated_at: datetime,
        site_id: str | None = None,
        device_id: str | None = None,
        link_id: str | None = None,
        service_id: str | None = None,
    ) -> NOCWallDashboardAlert:
        return NOCWallDashboardAlert(
            alert_id=alert_id,
            title=title,
            message=message,
            severity=severity,
            source=source,
            created_at=generated_at,
            site_id=site_id,
            device_id=device_id,
            link_id=link_id,
            service_id=service_id,
        )

    def _build_alerts(
        self,
        *,
        state: NOCWallDashboardOperationalState,
        latest_report: (
            ExecutivePredictiveReportRecord
            | None
        ),
        generated_at: datetime,
    ) -> tuple[NOCWallDashboardAlert, ...]:
        alerts: list[
            NOCWallDashboardAlert
        ] = []

        if state.critical_sites:
            alerts.append(
                self._alert(
                    alert_id=(
                        "dashboard-alert:"
                        "critical-sites"
                    ),
                    title=(
                        "Critical sites detected"
                    ),
                    message=(
                        f"{state.critical_sites} site(s) "
                        "are currently critical."
                    ),
                    severity=(
                        NOCWallDashboardSeverity.CRITICAL
                    ),
                    source=(
                        "operational-state"
                    ),
                    generated_at=generated_at,
                )
            )

        if state.down_links:
            alerts.append(
                self._alert(
                    alert_id=(
                        "dashboard-alert:"
                        "down-links"
                    ),
                    title="Links are down",
                    message=(
                        f"{state.down_links} link(s) "
                        "are currently down."
                    ),
                    severity=(
                        NOCWallDashboardSeverity.CRITICAL
                    ),
                    source=(
                        "operational-state"
                    ),
                    generated_at=generated_at,
                )
            )

        if state.offline_devices:
            alerts.append(
                self._alert(
                    alert_id=(
                        "dashboard-alert:"
                        "offline-devices"
                    ),
                    title="Offline devices detected",
                    message=(
                        f"{state.offline_devices} "
                        "device(s) are offline."
                    ),
                    severity=(
                        NOCWallDashboardSeverity.HIGH
                    ),
                    source=(
                        "operational-state"
                    ),
                    generated_at=generated_at,
                )
            )

        if state.critical_incidents:
            alerts.append(
                self._alert(
                    alert_id=(
                        "dashboard-alert:"
                        "critical-incidents"
                    ),
                    title=(
                        "Critical incidents active"
                    ),
                    message=(
                        f"{state.critical_incidents} "
                        "critical incident(s) are active."
                    ),
                    severity=(
                        NOCWallDashboardSeverity.CRITICAL
                    ),
                    source="incident-state",
                    generated_at=generated_at,
                )
            )

        if (
            state.pending_human_approvals
        ):
            alerts.append(
                self._alert(
                    alert_id=(
                        "dashboard-alert:"
                        "pending-approvals"
                    ),
                    title=(
                        "Human approvals pending"
                    ),
                    message=(
                        f"{state.pending_human_approvals} "
                        "approval request(s) require "
                        "human review."
                    ),
                    severity=(
                        NOCWallDashboardSeverity.WARNING
                    ),
                    source="approval-state",
                    generated_at=generated_at,
                )
            )

        if latest_report is not None:
            if (
                latest_report
                .critical_prediction_count
                > 0
            ):
                alerts.append(
                    self._alert(
                        alert_id=(
                            "dashboard-alert:"
                            "critical-predictions"
                        ),
                        title=(
                            "Critical predictions active"
                        ),
                        message=(
                            f"{latest_report.critical_prediction_count} "
                            "critical predictive warning(s) "
                            "are active."
                        ),
                        severity=(
                            NOCWallDashboardSeverity.CRITICAL
                        ),
                        source=(
                            "executive-predictive-report"
                        ),
                        generated_at=generated_at,
                    )
                )

            elif (
                latest_report
                .high_risk_prediction_count
                > 0
            ):
                alerts.append(
                    self._alert(
                        alert_id=(
                            "dashboard-alert:"
                            "high-risk-predictions"
                        ),
                        title=(
                            "High-risk predictions active"
                        ),
                        message=(
                            f"{latest_report.high_risk_prediction_count} "
                            "high-risk predictive warning(s) "
                            "are active."
                        ),
                        severity=(
                            NOCWallDashboardSeverity.HIGH
                        ),
                        source=(
                            "executive-predictive-report"
                        ),
                        generated_at=generated_at,
                    )
                )

        severity_rank = {
            NOCWallDashboardSeverity.CRITICAL:
                4,
            NOCWallDashboardSeverity.HIGH:
                3,
            NOCWallDashboardSeverity.WARNING:
                2,
            NOCWallDashboardSeverity.INFO:
                1,
        }

        return tuple(
            sorted(
                alerts,
                key=lambda alert: (
                    -severity_rank[
                        alert.severity
                    ],
                    alert.alert_id,
                ),
            )
        )

    @staticmethod
    def _dashboard_id(
        *,
        generated_at: datetime,
        report_id: str | None,
        operational_state: (
            NOCWallDashboardOperationalState
        ),
    ) -> str:
        identity = "|".join(
            (
                generated_at.isoformat(),
                report_id or "no-report",
                str(
                    operational_state.total_sites
                ),
                str(
                    operational_state.total_devices
                ),
                str(
                    operational_state.total_links
                ),
                str(
                    operational_state.active_incidents
                ),
            )
        )

        return (
            "noc-wall-dashboard:"
            f"{uuid5(DASHBOARD_NAMESPACE, identity)}"
        )

    def build(
        self,
        *,
        report_store: (
            ExecutivePredictiveReportStore
        ),
        operational_state: (
            NOCWallDashboardOperationalState
        ),
        generated_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NOCWallDashboardSnapshot:
        if not isinstance(
            report_store,
            ExecutivePredictiveReportStore,
        ):
            raise TypeError(
                "report_store must be an "
                "ExecutivePredictiveReportStore"
            )

        if not isinstance(
            operational_state,
            NOCWallDashboardOperationalState,
        ):
            raise TypeError(
                "operational_state must be an "
                "NOCWallDashboardOperationalState"
            )

        if (
            metadata is not None
            and not isinstance(
                metadata,
                dict,
            )
        ):
            raise TypeError(
                "metadata must be a dictionary"
            )

        resolved_generated_at = (
            self._normalize_generated_at(
                generated_at
            )
        )

        latest_report = self._latest_report(
            report_store
        )

        if latest_report is not None:
            try:
                stored_at = datetime.fromisoformat(
                    latest_report.stored_at
                )

            except (
                TypeError,
                ValueError,
            ) as exc:
                raise ValueError(
                    "Latest report stored_at is invalid"
                ) from exc

            if (
                stored_at.tzinfo is None
                or stored_at.utcoffset() is None
            ):
                raise ValueError(
                    "Latest report stored_at is invalid"
                )

            if (
                resolved_generated_at
                < stored_at.astimezone(
                    timezone.utc
                )
            ):
                raise ValueError(
                    "generated_at must not be earlier "
                    "than latest report stored_at"
                )

        report_audit = (
            verify_executive_predictive_report_store(
                store=report_store,
                audited_at=resolved_generated_at,
            )
        )

        if not isinstance(
            report_audit,
            ExecutivePredictiveReportStoreAuditReport,
        ):
            raise RuntimeError(
                "Report store audit result is invalid"
            )

        if not report_audit.audit_valid:
            raise ValueError(
                "Executive predictive report "
                "store audit is invalid"
            )

        operational_score = (
            self._operational_health_score(
                operational_state
            )
        )

        health_score = (
            self._overall_health_score(
                operational_score=(
                    operational_score
                ),
                latest_report=latest_report,
            )
        )

        status = self._overall_status(
            state=operational_state,
            latest_report=latest_report,
            health_score=health_score,
        )

        trend = self._overall_trend(
            latest_report=latest_report,
            status=status,
        )

        alerts = self._build_alerts(
            state=operational_state,
            latest_report=latest_report,
            generated_at=resolved_generated_at,
        )

        report_payload = (
            latest_report.report_payload
            if latest_report is not None
            else {}
        )

        report_sites = tuple(
            report_payload.get(
                "affected_sites",
                (),
            )
        )

        report_devices = tuple(
            report_payload.get(
                "affected_devices",
                (),
            )
        )

        report_links = tuple(
            report_payload.get(
                "affected_links",
                (),
            )
        )

        report_services = tuple(
            report_payload.get(
                "affected_services",
                (),
            )
        )

        combined_metadata = {
            **(
                operational_state.metadata
                or {}
            ),
            **(
                metadata
                or {}
            ),
            "builder_service":
                BUILDER_SERVICE_NAME,
            "builder_version":
                BUILDER_SERVICE_VERSION,
            "report_store_record_count":
                report_audit.record_count,
            "report_store_audit_valid":
                report_audit.audit_valid,
            "operational_health_score":
                operational_score,
        }

        latest_report_id = (
            latest_report.report_id
            if latest_report is not None
            else None
        )

        return NOCWallDashboardSnapshot(
            dashboard_id=self._dashboard_id(
                generated_at=resolved_generated_at,
                report_id=latest_report_id,
                operational_state=(
                    operational_state
                ),
            ),
            generated_at=(
                resolved_generated_at
            ),
            overall_status=status,
            overall_health_score=(
                health_score
            ),
            overall_trend=trend,
            total_sites=(
                operational_state.total_sites
            ),
            healthy_sites=(
                operational_state.healthy_sites
            ),
            degraded_sites=(
                operational_state.degraded_sites
            ),
            critical_sites=(
                operational_state.critical_sites
            ),
            unknown_sites=(
                operational_state.unknown_sites
            ),
            total_devices=(
                operational_state.total_devices
            ),
            online_devices=(
                operational_state.online_devices
            ),
            offline_devices=(
                operational_state.offline_devices
            ),
            degraded_devices=(
                operational_state.degraded_devices
            ),
            total_links=(
                operational_state.total_links
            ),
            healthy_links=(
                operational_state.healthy_links
            ),
            degraded_links=(
                operational_state.degraded_links
            ),
            down_links=(
                operational_state.down_links
            ),
            active_incidents=(
                operational_state.active_incidents
            ),
            critical_incidents=(
                operational_state.critical_incidents
            ),
            high_priority_incidents=(
                operational_state
                .high_priority_incidents
            ),
            active_predictions=(
                latest_report.prediction_count
                if latest_report is not None
                else 0
            ),
            critical_predictions=(
                latest_report
                .critical_prediction_count
                if latest_report is not None
                else 0
            ),
            high_risk_predictions=(
                latest_report
                .high_risk_prediction_count
                if latest_report is not None
                else 0
            ),
            pending_human_approvals=(
                operational_state
                .pending_human_approvals
            ),
            approved_but_not_executable=(
                operational_state
                .approved_but_not_executable
            ),
            latest_report_id=(
                latest_report_id
            ),
            latest_report_fingerprint=(
                latest_report.report_fingerprint
                if latest_report is not None
                else None
            ),
            latest_report_health_score=(
                latest_report.overall_health_score
                if latest_report is not None
                else None
            ),
            affected_sites=self._merge_values(
                operational_state
                .affected_sites,
                report_sites,
            ),
            affected_devices=self._merge_values(
                operational_state
                .affected_devices,
                report_devices,
            ),
            affected_links=self._merge_values(
                operational_state
                .affected_links,
                report_links,
            ),
            affected_services=self._merge_values(
                operational_state
                .affected_services,
                report_services,
            ),
            alerts=alerts,
            source_audit_ids=(
                report_audit.audit_id,
            ),
            source_record_hashes=(
                (
                    latest_report.record_hash,
                )
                if latest_report is not None
                else ()
            ),
            generated_by=(
                BUILDER_SERVICE_NAME
            ),
            metadata=(
                combined_metadata
            ),
        )


def build_noc_wall_dashboard_snapshot(
    *,
    report_store: ExecutivePredictiveReportStore,
    operational_state: (
        NOCWallDashboardOperationalState
    ),
    generated_at: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> NOCWallDashboardSnapshot:
    return NOCWallDashboardBuilder().build(
        report_store=report_store,
        operational_state=operational_state,
        generated_at=generated_at,
        metadata=metadata,
    )
