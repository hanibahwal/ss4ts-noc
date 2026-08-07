from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from app.models.noc_wall_dashboard import (
    DASHBOARD_SCHEMA_VERSION,
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
    verify_executive_predictive_report_store,
)
from app.services.noc_wall_dashboard_builder import (
    BUILDER_SERVICE_NAME,
    BUILDER_SERVICE_VERSION,
)


VALIDATOR_SERVICE_NAME = (
    "SS4TS NOC Wall Dashboard Validator"
)

VALIDATOR_SERVICE_VERSION = "1.0.0"


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


def _normalize_validated_at(
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
            "validated_at must be a datetime"
        )

    if (
        resolved.tzinfo is None
        or resolved.utcoffset() is None
    ):
        raise ValueError(
            "validated_at must be timezone-aware"
        )

    return resolved.astimezone(
        timezone.utc
    )


@dataclass(
    frozen=True,
    slots=True,
)
class NOCWallDashboardValidationResult:
    validation_id: str

    dashboard_id: str
    dashboard_fingerprint: str

    validation_valid: bool
    dashboard_accepted: bool

    checks: dict[str, bool]
    validation_errors: tuple[str, ...]
    validation_warnings: tuple[str, ...]

    validated_at: datetime

    validator_name: str
    validator_version: str

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
            "validation_id":
                self.validation_id,
            "dashboard_id":
                self.dashboard_id,
            "dashboard_fingerprint":
                self.dashboard_fingerprint,
            "validation_valid":
                self.validation_valid,
            "dashboard_accepted":
                self.dashboard_accepted,
            "checks":
                dict(
                    self.checks
                ),
            "validation_errors":
                list(
                    self.validation_errors
                ),
            "validation_warnings":
                list(
                    self.validation_warnings
                ),
            "validated_at":
                self.validated_at.isoformat(),
            "validator_name":
                self.validator_name,
            "validator_version":
                self.validator_version,
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
                "validation_only":
                    True,
                "read_only":
                    True,
                "dashboard_mutated":
                    False,
                "report_store_mutated":
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


class NOCWallDashboardValidator:
    REQUIRED_CHECKS = (
        "dashboard_type_valid",
        "fingerprint_valid",
        "schema_version_valid",
        "builder_identity_valid",
        "timestamp_order_valid",
        "site_counters_valid",
        "device_counters_valid",
        "link_counters_valid",
        "incident_counters_valid",
        "prediction_counters_valid",
        "approval_counters_valid",
        "status_consistency_valid",
        "trend_consistency_valid",
        "alerts_valid",
        "affected_entities_valid",
        "source_audit_bindings_valid",
        "source_record_bindings_valid",
        "latest_report_bindings_valid",
        "metadata_valid",
        "safety_guarantees_valid",
    )

    @staticmethod
    def _validation_id(
        *,
        snapshot: NOCWallDashboardSnapshot,
        validated_at: datetime,
    ) -> str:
        payload = {
            "dashboard_id":
                snapshot.dashboard_id,
            "dashboard_fingerprint":
                snapshot.dashboard_fingerprint,
            "validated_at":
                validated_at.isoformat(),
            "validator_name":
                VALIDATOR_SERVICE_NAME,
            "validator_version":
                VALIDATOR_SERVICE_VERSION,
        }

        digest = hashlib.sha256(
            _canonical_json(
                payload
            ).encode(
                "utf-8"
            )
        ).hexdigest()

        return (
            "noc-wall-dashboard-validation:"
            f"{digest}"
        )

    @staticmethod
    def _latest_report(
        report_store: (
            ExecutivePredictiveReportStore
            | None
        ),
    ) -> ExecutivePredictiveReportRecord | None:
        if report_store is None:
            return None

        records = report_store.list_records(
            limit=1_000_000
        )

        if not records:
            return None

        return records[-1]

    @staticmethod
    def _alerts_valid(
        snapshot: NOCWallDashboardSnapshot,
    ) -> bool:
        alert_ids: list[str] = []

        for alert in snapshot.alerts:
            if not alert.alert_id.strip():
                return False

            if not alert.title.strip():
                return False

            if not alert.message.strip():
                return False

            if not alert.source.strip():
                return False

            if not isinstance(
                alert.severity,
                NOCWallDashboardSeverity,
            ):
                return False

            if (
                alert.created_at.tzinfo is None
                or alert.created_at.utcoffset()
                is None
            ):
                return False

            if (
                alert.created_at
                > snapshot.generated_at
            ):
                return False

            alert_ids.append(
                alert.alert_id
            )

        return len(
            alert_ids
        ) == len(
            set(
                alert_ids
            )
        )

    @staticmethod
    def _affected_entities_valid(
        snapshot: NOCWallDashboardSnapshot,
    ) -> bool:
        collections = (
            snapshot.affected_sites,
            snapshot.affected_devices,
            snapshot.affected_links,
            snapshot.affected_services,
        )

        for collection in collections:
            if not isinstance(
                collection,
                tuple,
            ):
                return False

            normalized = tuple(
                str(
                    value
                ).strip()
                for value in collection
            )

            if any(
                not value
                for value in normalized
            ):
                return False

            if len(
                normalized
            ) != len(
                set(
                    normalized
                )
            ):
                return False

        return True

    @staticmethod
    def _safety_guarantees_valid(
        snapshot: NOCWallDashboardSnapshot,
    ) -> bool:
        payload = snapshot.to_dict()

        return all(
            (
                snapshot.incident_created
                is False,
                snapshot.recommendation_executed
                is False,
                snapshot.decision_created
                is False,
                snapshot.authorization_created
                is False,
                snapshot.execution_allowed
                is False,
                snapshot.can_execute
                is False,
                payload.get(
                    "incident_created"
                )
                is False,
                payload.get(
                    "recommendation_executed"
                )
                is False,
                payload.get(
                    "decision_created"
                )
                is False,
                payload.get(
                    "authorization_created"
                )
                is False,
                payload.get(
                    "execution_allowed"
                )
                is False,
                payload.get(
                    "can_execute"
                )
                is False,
                payload.get(
                    "safety",
                    {},
                ).get(
                    "display_only"
                )
                is True,
                payload.get(
                    "safety",
                    {},
                ).get(
                    "read_only_snapshot"
                )
                is True,
                payload.get(
                    "safety",
                    {},
                ).get(
                    "device_command_executed"
                )
                is False,
            )
        )

    @staticmethod
    def _status_consistency_valid(
        snapshot: NOCWallDashboardSnapshot,
    ) -> bool:
        critical_condition = any(
            (
                snapshot.critical_sites > 0,
                snapshot.down_links > 0,
                snapshot.critical_incidents > 0,
                snapshot.critical_predictions > 0,
                snapshot.overall_health_score
                < 50,
            )
        )

        degraded_condition = any(
            (
                snapshot.degraded_sites > 0,
                snapshot.offline_devices > 0,
                snapshot.degraded_devices > 0,
                snapshot.degraded_links > 0,
                snapshot.high_priority_incidents
                > 0,
                snapshot.high_risk_predictions
                > 0,
                snapshot.overall_health_score
                < 85,
            )
        )

        empty_condition = all(
            (
                snapshot.total_sites == 0,
                snapshot.total_devices == 0,
                snapshot.total_links == 0,
                snapshot.latest_report_id
                is None,
            )
        )

        if critical_condition:
            return (
                snapshot.overall_status
                is NOCWallDashboardStatus.CRITICAL
            )

        if degraded_condition:
            return (
                snapshot.overall_status
                in {
                    NOCWallDashboardStatus.DEGRADED,
                    NOCWallDashboardStatus.CRITICAL,
                }
            )

        if empty_condition:
            return (
                snapshot.overall_status
                is NOCWallDashboardStatus.UNKNOWN
            )

        return (
            snapshot.overall_status
            is NOCWallDashboardStatus.HEALTHY
        )

    @staticmethod
    def _trend_consistency_valid(
        snapshot: NOCWallDashboardSnapshot,
    ) -> bool:
        if (
            snapshot.overall_status
            is NOCWallDashboardStatus.UNKNOWN
        ):
            return (
                snapshot.overall_trend
                is NOCWallDashboardTrend.UNKNOWN
            )

        if (
            snapshot.overall_status
            is NOCWallDashboardStatus.HEALTHY
        ):
            return (
                snapshot.overall_trend
                in {
                    NOCWallDashboardTrend.STABLE,
                    NOCWallDashboardTrend.IMPROVING,
                }
            )

        return (
            snapshot.overall_trend
            in {
                NOCWallDashboardTrend.DEGRADING,
                NOCWallDashboardTrend.STABLE,
                NOCWallDashboardTrend.IMPROVING,
            }
        )

    def validate(
        self,
        *,
        snapshot: NOCWallDashboardSnapshot,
        report_store: (
            ExecutivePredictiveReportStore
            | None
        ) = None,
        validated_at: datetime | None = None,
    ) -> NOCWallDashboardValidationResult:
        resolved_validated_at = (
            _normalize_validated_at(
                validated_at
            )
        )

        if not isinstance(
            snapshot,
            NOCWallDashboardSnapshot,
        ):
            raise TypeError(
                "snapshot must be a "
                "NOCWallDashboardSnapshot"
            )

        if (
            report_store is not None
            and not isinstance(
                report_store,
                ExecutivePredictiveReportStore,
            )
        ):
            raise TypeError(
                "report_store must be an "
                "ExecutivePredictiveReportStore"
            )

        checks = {
            check_name: True
            for check_name
            in self.REQUIRED_CHECKS
        }

        errors: list[str] = []
        warnings: list[str] = []

        checks[
            "dashboard_type_valid"
        ] = isinstance(
            snapshot,
            NOCWallDashboardSnapshot,
        )

        checks[
            "fingerprint_valid"
        ] = (
            snapshot.dashboard_fingerprint
            == snapshot.calculate_fingerprint()
        )

        checks[
            "schema_version_valid"
        ] = (
            snapshot.schema_version
            == DASHBOARD_SCHEMA_VERSION
        )

        checks[
            "builder_identity_valid"
        ] = all(
            (
                snapshot.generated_by
                == BUILDER_SERVICE_NAME,
                snapshot.metadata.get(
                    "builder_service"
                )
                == BUILDER_SERVICE_NAME,
                snapshot.metadata.get(
                    "builder_version"
                )
                == BUILDER_SERVICE_VERSION,
            )
        )

        checks[
            "timestamp_order_valid"
        ] = all(
            (
                snapshot.generated_at.tzinfo
                is not None,
                snapshot.generated_at.utcoffset()
                is not None,
                resolved_validated_at
                >= snapshot.generated_at,
            )
        )

        checks[
            "site_counters_valid"
        ] = (
            snapshot.healthy_sites
            + snapshot.degraded_sites
            + snapshot.critical_sites
            + snapshot.unknown_sites
            == snapshot.total_sites
        )

        checks[
            "device_counters_valid"
        ] = (
            snapshot.online_devices
            + snapshot.offline_devices
            + snapshot.degraded_devices
            == snapshot.total_devices
        )

        checks[
            "link_counters_valid"
        ] = (
            snapshot.healthy_links
            + snapshot.degraded_links
            + snapshot.down_links
            == snapshot.total_links
        )

        checks[
            "incident_counters_valid"
        ] = (
            snapshot.critical_incidents
            + snapshot.high_priority_incidents
            <= snapshot.active_incidents
        )

        checks[
            "prediction_counters_valid"
        ] = (
            snapshot.critical_predictions
            + snapshot.high_risk_predictions
            <= snapshot.active_predictions
        )

        checks[
            "approval_counters_valid"
        ] = (
            snapshot.approved_but_not_executable
            <= snapshot.pending_human_approvals
        )

        checks[
            "status_consistency_valid"
        ] = self._status_consistency_valid(
            snapshot
        )

        checks[
            "trend_consistency_valid"
        ] = self._trend_consistency_valid(
            snapshot
        )

        checks[
            "alerts_valid"
        ] = self._alerts_valid(
            snapshot
        )

        checks[
            "affected_entities_valid"
        ] = self._affected_entities_valid(
            snapshot
        )

        checks[
            "metadata_valid"
        ] = all(
            (
                isinstance(
                    snapshot.metadata,
                    dict,
                ),
                snapshot.metadata.get(
                    "report_store_audit_valid"
                )
                is True,
                isinstance(
                    snapshot.metadata.get(
                        "report_store_record_count"
                    ),
                    int,
                ),
                isinstance(
                    snapshot.metadata.get(
                        "operational_health_score"
                    ),
                    (
                        int,
                        float,
                    ),
                ),
            )
        )

        checks[
            "safety_guarantees_valid"
        ] = self._safety_guarantees_valid(
            snapshot
        )

        checks[
            "source_audit_bindings_valid"
        ] = all(
            (
                isinstance(
                    snapshot.source_audit_ids,
                    tuple,
                ),
                len(
                    snapshot.source_audit_ids
                )
                == len(
                    set(
                        snapshot.source_audit_ids
                    )
                ),
                all(
                    str(
                        audit_id
                    ).strip()
                    for audit_id
                    in snapshot.source_audit_ids
                ),
            )
        )

        checks[
            "source_record_bindings_valid"
        ] = all(
            (
                isinstance(
                    snapshot.source_record_hashes,
                    tuple,
                ),
                len(
                    snapshot.source_record_hashes
                )
                == len(
                    set(
                        snapshot.source_record_hashes
                    )
                ),
                all(
                    len(
                        str(
                            record_hash
                        )
                    )
                    == 64
                    for record_hash
                    in snapshot.source_record_hashes
                ),
            )
        )

        latest_report = self._latest_report(
            report_store
        )

        if report_store is not None:
            report_audit = (
                verify_executive_predictive_report_store(
                    store=report_store,
                    audited_at=(
                        resolved_validated_at
                    ),
                )
            )

            if not report_audit.audit_valid:
                checks[
                    "source_audit_bindings_valid"
                ] = False

            if not snapshot.source_audit_ids:
                checks[
                    "source_audit_bindings_valid"
                ] = False

            if (
                snapshot.metadata.get(
                    "report_store_record_count"
                )
                != report_audit.record_count
            ):
                checks[
                    "source_audit_bindings_valid"
                ] = False

            if (
                snapshot.metadata.get(
                    "report_store_audit_valid"
                )
                is not True
            ):
                checks[
                    "source_audit_bindings_valid"
                ] = False

        if latest_report is None:
            checks[
                "latest_report_bindings_valid"
            ] = all(
                (
                    snapshot.latest_report_id
                    is None,
                    snapshot.latest_report_fingerprint
                    is None,
                    snapshot.latest_report_health_score
                    is None,
                    snapshot.active_predictions
                    == 0,
                    snapshot.critical_predictions
                    == 0,
                    snapshot.high_risk_predictions
                    == 0,
                    snapshot.source_record_hashes
                    == (),
                )
            )

            if report_store is None:
                warnings.append(
                    "Report store was not supplied; "
                    "latest report bindings were "
                    "validated from snapshot only"
                )

        else:
            checks[
                "latest_report_bindings_valid"
            ] = all(
                (
                    snapshot.latest_report_id
                    == latest_report.report_id,
                    snapshot.latest_report_fingerprint
                    == latest_report.report_fingerprint,
                    snapshot.latest_report_health_score
                    == latest_report.overall_health_score,
                    snapshot.active_predictions
                    == latest_report.prediction_count,
                    snapshot.critical_predictions
                    == latest_report
                    .critical_prediction_count,
                    snapshot.high_risk_predictions
                    == latest_report
                    .high_risk_prediction_count,
                    latest_report.record_hash
                    in snapshot.source_record_hashes,
                )
            )

        for check_name in self.REQUIRED_CHECKS:
            if not checks.get(
                check_name,
                False,
            ):
                errors.append(
                    f"{check_name} failed"
                )

        validation_valid = (
            not errors
            and all(
                checks.get(
                    check_name,
                    False,
                )
                for check_name
                in self.REQUIRED_CHECKS
            )
        )

        return NOCWallDashboardValidationResult(
            validation_id=(
                self._validation_id(
                    snapshot=snapshot,
                    validated_at=(
                        resolved_validated_at
                    ),
                )
            ),
            dashboard_id=(
                snapshot.dashboard_id
            ),
            dashboard_fingerprint=(
                snapshot.dashboard_fingerprint
            ),
            validation_valid=(
                validation_valid
            ),
            dashboard_accepted=(
                validation_valid
            ),
            checks=checks,
            validation_errors=tuple(
                errors
            ),
            validation_warnings=tuple(
                warnings
            ),
            validated_at=(
                resolved_validated_at
            ),
            validator_name=(
                VALIDATOR_SERVICE_NAME
            ),
            validator_version=(
                VALIDATOR_SERVICE_VERSION
            ),
        )


def validate_noc_wall_dashboard_snapshot(
    *,
    snapshot: NOCWallDashboardSnapshot,
    report_store: (
        ExecutivePredictiveReportStore
        | None
    ) = None,
    validated_at: datetime | None = None,
) -> NOCWallDashboardValidationResult:
    return NOCWallDashboardValidator().validate(
        snapshot=snapshot,
        report_store=report_store,
        validated_at=validated_at,
    )
