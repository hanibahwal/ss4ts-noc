from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.executive_predictive_report_pdf import (
    ExecutivePredictiveReportPDFExport,
    export_executive_predictive_report_pdf,
)
from app.services.executive_predictive_report_store import (
    ExecutivePredictiveReportRecord,
    ExecutivePredictiveReportStore,
)
from app.services.executive_predictive_report_store_audit import (
    ExecutivePredictiveReportStoreAuditReport,
    verify_executive_predictive_report_store,
)


API_SERVICE_NAME = (
    "SS4TS Executive Predictive Report API"
)

API_SERVICE_VERSION = "1.0.0"


class ExecutivePredictiveReportAPIError(
    RuntimeError
):
    pass


class ExecutivePredictiveReportAPINotFound(
    ExecutivePredictiveReportAPIError
):
    pass


class ExecutivePredictiveReportAPIIntegrityError(
    ExecutivePredictiveReportAPIError
):
    pass


@dataclass(
    frozen=True,
    slots=True,
)
class ExecutivePredictiveReportAPIResponse:
    success: bool
    operation: str
    data: dict[str, Any]

    service_name: str
    service_version: str

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
                "network_device_access":
                    False,
                "command_generated":
                    False,
                "device_command_executed":
                    False,
            },
        }


class ExecutivePredictiveReportAPI:
    def __init__(
        self,
        *,
        store: ExecutivePredictiveReportStore,
    ) -> None:
        if not isinstance(
            store,
            ExecutivePredictiveReportStore,
        ):
            raise TypeError(
                "store must be an "
                "ExecutivePredictiveReportStore"
            )

        self.store = store

    def _verify_store(
        self,
        *,
        audited_at: datetime | None = None,
    ) -> ExecutivePredictiveReportStoreAuditReport:
        audit = (
            verify_executive_predictive_report_store(
                store=self.store,
                audited_at=audited_at,
            )
        )

        if not audit.audit_valid:
            raise ExecutivePredictiveReportAPIIntegrityError(
                "Executive predictive report "
                "store audit failed"
            )

        return audit

    @staticmethod
    def _record_summary(
        record: ExecutivePredictiveReportRecord,
    ) -> dict[str, Any]:
        return {
            "sequence_number":
                record.sequence_number,
            "report_id":
                record.report_id,
            "report_fingerprint":
                record.report_fingerprint,
            "report_type":
                record.report_type,
            "report_title":
                record.report_title,
            "report_period_start":
                record.report_period_start,
            "report_period_end":
                record.report_period_end,
            "generated_at":
                record.generated_at,
            "overall_risk_class":
                record.overall_risk_class,
            "overall_health_score":
                record.overall_health_score,
            "service_outlook":
                record.service_outlook,
            "prediction_count":
                record.prediction_count,
            "critical_prediction_count":
                record.critical_prediction_count,
            "high_risk_prediction_count":
                record.high_risk_prediction_count,
            "source_audit_id":
                record.source_audit_id,
            "source_audit_valid":
                record.source_audit_valid,
            "validation_valid":
                record.validation_valid,
            "stored_at":
                record.stored_at,
            "record_hash":
                record.record_hash,
        }

    def list_reports(
        self,
        *,
        limit: int = 100,
        audited_at: datetime | None = None,
    ) -> ExecutivePredictiveReportAPIResponse:
        audit = self._verify_store(
            audited_at=audited_at
        )

        records = self.store.list_records(
            limit=limit
        )

        return ExecutivePredictiveReportAPIResponse(
            success=True,
            operation="list_reports",
            data={
                "reports": [
                    self._record_summary(
                        record
                    )
                    for record in records
                ],
                "returned_count":
                    len(
                        records
                    ),
                "store_record_count":
                    audit.record_count,
                "store_audit_id":
                    audit.audit_id,
                "store_audit_valid":
                    audit.audit_valid,
            },
            service_name=(
                API_SERVICE_NAME
            ),
            service_version=(
                API_SERVICE_VERSION
            ),
        )

    def get_report(
        self,
        *,
        report_id: str,
        audited_at: datetime | None = None,
    ) -> ExecutivePredictiveReportAPIResponse:
        normalized_report_id = str(
            report_id
        ).strip()

        if not normalized_report_id:
            raise ValueError(
                "report_id must not be empty"
            )

        audit = self._verify_store(
            audited_at=audited_at
        )

        record = self.store.get(
            normalized_report_id
        )

        if record is None:
            raise ExecutivePredictiveReportAPINotFound(
                "Executive predictive report "
                "was not found"
            )

        if not record.verify_hash():
            raise ExecutivePredictiveReportAPIIntegrityError(
                "Executive predictive report "
                "record hash is invalid"
            )

        return ExecutivePredictiveReportAPIResponse(
            success=True,
            operation="get_report",
            data={
                "report":
                    record.to_dict(),
                "store_audit_id":
                    audit.audit_id,
                "store_audit_valid":
                    audit.audit_valid,
            },
            service_name=(
                API_SERVICE_NAME
            ),
            service_version=(
                API_SERVICE_VERSION
            ),
        )

    def export_pdf(
        self,
        *,
        report_id: str,
        output_path: str | Path,
        exported_at: datetime | None = None,
        audited_at: datetime | None = None,
        overwrite: bool = False,
    ) -> ExecutivePredictiveReportAPIResponse:
        audit = self._verify_store(
            audited_at=(
                audited_at
                or exported_at
            )
        )

        export = (
            export_executive_predictive_report_pdf(
                store=self.store,
                report_id=report_id,
                output_path=output_path,
                exported_at=exported_at,
                overwrite=overwrite,
            )
        )

        if not isinstance(
            export,
            ExecutivePredictiveReportPDFExport,
        ):
            raise ExecutivePredictiveReportAPIIntegrityError(
                "PDF export result is invalid"
            )

        return ExecutivePredictiveReportAPIResponse(
            success=True,
            operation="export_pdf",
            data={
                "pdf":
                    export.to_dict(),
                "store_audit_id":
                    audit.audit_id,
                "store_audit_valid":
                    audit.audit_valid,
            },
            service_name=(
                API_SERVICE_NAME
            ),
            service_version=(
                API_SERVICE_VERSION
            ),
        )

    def audit_store(
        self,
        *,
        audited_at: datetime | None = None,
    ) -> ExecutivePredictiveReportAPIResponse:
        audit = (
            verify_executive_predictive_report_store(
                store=self.store,
                audited_at=audited_at,
            )
        )

        return ExecutivePredictiveReportAPIResponse(
            success=(
                audit.audit_valid
            ),
            operation="audit_store",
            data={
                "audit":
                    audit.to_dict()
            },
            service_name=(
                API_SERVICE_NAME
            ),
            service_version=(
                API_SERVICE_VERSION
            ),
        )


def list_executive_predictive_reports(
    *,
    store: ExecutivePredictiveReportStore,
    limit: int = 100,
    audited_at: datetime | None = None,
) -> ExecutivePredictiveReportAPIResponse:
    return ExecutivePredictiveReportAPI(
        store=store
    ).list_reports(
        limit=limit,
        audited_at=audited_at,
    )


def get_executive_predictive_report(
    *,
    store: ExecutivePredictiveReportStore,
    report_id: str,
    audited_at: datetime | None = None,
) -> ExecutivePredictiveReportAPIResponse:
    return ExecutivePredictiveReportAPI(
        store=store
    ).get_report(
        report_id=report_id,
        audited_at=audited_at,
    )


def export_executive_predictive_report(
    *,
    store: ExecutivePredictiveReportStore,
    report_id: str,
    output_path: str | Path,
    exported_at: datetime | None = None,
    audited_at: datetime | None = None,
    overwrite: bool = False,
) -> ExecutivePredictiveReportAPIResponse:
    return ExecutivePredictiveReportAPI(
        store=store
    ).export_pdf(
        report_id=report_id,
        output_path=output_path,
        exported_at=exported_at,
        audited_at=audited_at,
        overwrite=overwrite,
    )
