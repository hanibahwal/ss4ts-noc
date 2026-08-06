from __future__ import annotations

from typing import Any

from fastapi import (
    APIRouter,
    HTTPException,
)
from pydantic import (
    BaseModel,
    Field,
)

from app.api.v1.decision_audits import (
    get_audit_store,
)
from app.api.v1.execution_authorizations import (
    get_authorization_store,
)
from app.models.decision_action import (
    DecisionActionCommand,
    DecisionActionExecutionMode,
    DecisionActionRiskLevel,
    DecisionActionStatus,
    DecisionActionTarget,
)
from app.models.execution_authorization import (
    ApprovalIdentity,
    ApprovalRole,
    AuthorizationStatus,
)
from app.models.execution_lease import (
    LeaseConflict,
)
from app.models.execution_plan import (
    ExecutionPlan,
)
from app.services.decision_approval_gateway import (
    DecisionApprovalGateway,
)
from app.services.decision_execution_evidence import (
    DecisionExecutionEvidenceBuilder,
)
from app.services.decision_execution_runtime import (
    DecisionExecutionRuntimeNotFound,
    runtime,
)
from app.services.execution_lease_store import (
    ExecutionLeaseStore,
)
from app.services.safe_decision_execution_bridge import (
    SafeDecisionExecutionBindingError,
    SafeDecisionExecutionBridge,
    SafeDecisionExecutionBridgeError,
    SafeDecisionExecutionNotAllowed,
    SafeDecisionExecutionNotFound,
)


router = APIRouter(
    prefix="/decision-executions",
    tags=["decision-executions"],
)


class IdentityPayload(BaseModel):
    identity_id: str = Field(
        min_length=1,
        max_length=200,
    )

    display_name: str = Field(
        min_length=1,
        max_length=200,
    )

    role: ApprovalRole

    email: str | None = Field(
        default=None,
        max_length=320,
    )


class TargetPayload(BaseModel):
    router_ip: str = Field(
        min_length=1,
        max_length=200,
    )

    interface_name: str | None = Field(
        default=None,
        max_length=200,
    )

    site_id: str | None = Field(
        default=None,
        max_length=200,
    )

    device_id: str | None = Field(
        default=None,
        max_length=200,
    )


class CommandPayload(BaseModel):
    action_type: str = Field(
        min_length=1,
        max_length=200,
    )

    parameters: dict[str, Any] = Field(
        default_factory=dict
    )

    rollback_action_type: str | None = Field(
        default=None,
        max_length=200,
    )

    rollback_parameters: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    verification_steps: list[str] = Field(
        default_factory=list
    )

class PrepareDecisionExecutionPayload(
    BaseModel
):
    incident_id: str | None = Field(
        default=None,
        max_length=200,
    )

    problem: str = Field(
        min_length=1,
        max_length=2000,
    )

    recommendation: str = Field(
        min_length=1,
        max_length=4000,
    )

    confidence_percent: float = Field(
        ge=0,
        le=100,
    )

    risk_level: DecisionActionRiskLevel

    execution_mode: (
        DecisionActionExecutionMode
    )

    target: TargetPayload
    command: CommandPayload
    requester: IdentityPayload

    plan: dict[str, Any]

    requested_by: str = Field(
        default="decision-execution-api",
        min_length=1,
        max_length=200,
    )


class SimulateDecisionExecutionPayload(
    BaseModel
):
    owner_id: str = Field(
        default="worker:decision-api",
        min_length=1,
        max_length=200,
    )

    lease_ttl_seconds: int = Field(
        default=60,
        ge=5,
        le=3600,
    )

    fail_step_ids: list[str] = Field(
        default_factory=list
    )

    trace_id: str | None = Field(
        default=None,
        max_length=300,
    )


def _identity(
    payload: IdentityPayload,
) -> ApprovalIdentity:
    return ApprovalIdentity(
        identity_id=payload.identity_id,
        display_name=payload.display_name,
        role=payload.role,
        email=payload.email,
    )


@router.post("/prepare")
async def prepare_decision_execution(
    payload: PrepareDecisionExecutionPayload,
) -> dict:
    try:
        action = (
            runtime.action_service.create_action(
                incident_id=
                    payload.incident_id,
                problem=payload.problem,
                recommendation=
                    payload.recommendation,
                confidence_percent=
                    payload.confidence_percent,
                risk_level=
                    payload.risk_level,
                execution_mode=
                    payload.execution_mode,
                target=DecisionActionTarget(
                    router_ip=(
                        payload.target
                        .router_ip
                    ),
                    interface_name=(
                        payload.target
                        .interface_name
                    ),
                    site_id=(
                        payload.target
                        .site_id
                    ),
                    device_id=(
                        payload.target
                        .device_id
                    ),
                ),
                command=DecisionActionCommand(
                    action_type=(
                        payload.command
                        .action_type
                    ),
                    parameters=(
                        payload.command
                        .parameters
                    ),
                    rollback_action_type=(
                        payload.command
                        .rollback_action_type
                    ),
                    rollback_parameters=(
                        payload.command
                        .rollback_parameters
                    ),
                    verification_steps=tuple(
                        payload.command
                        .verification_steps
                    ),
                ),
                requested_by=
                    payload.requested_by,
            )
        )

        plan_data = dict(
            payload.plan
        )

        plan_data["decision_id"] = (
            action.decision_id
        )

        plan = ExecutionPlan.from_dict(
            plan_data
        )

        authorization_store = (
            get_authorization_store()
        )

        gateway = DecisionApprovalGateway(
            action_service=
                runtime.action_service,
            authorization_store=
                authorization_store,
        )

        request = (
            gateway.request_authorization(
                action=action,
                plan=plan,
                requester=_identity(
                    payload.requester
                ),
            )
        )

        item = runtime.register(
            action=request.action,
            plan=plan,
            authorization_id=(
                request.authorization
                .authorization_id
            ),
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except (
        OSError,
        RuntimeError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    return {
        "prepared":
            True,
        "runtime":
            item.to_dict(),
        "authorization":
            request.authorization
            .to_dict(),
        "safety": {
            "dry_run_only":
                True,
            "execution_performed":
                False,
            "network_io_performed":
                False,
            "device_command_executed":
                False,
        },
    }


@router.post(
    "/{authorization_id}/simulate"
)
async def simulate_decision_execution(
    authorization_id: str,
    payload: SimulateDecisionExecutionPayload,
) -> dict:
    try:
        item = runtime.get(
            authorization_id
        )

        authorization_store = (
            get_authorization_store()
        )

        authorization = (
            authorization_store.get(
                authorization_id
            )
        )

        if authorization is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Execution authorization "
                    f"not found: {authorization_id}"
                ),
            )

        if (
            authorization.status
            is AuthorizationStatus.APPROVED
            and item.action.status
            is DecisionActionStatus
            .PENDING_APPROVAL
        ):
            approver_id = (
                authorization.approver
                .identity_id
                if authorization.approver
                is not None
                else "approved-authorization"
            )

            item.action = (
                runtime.action_service.approve(
                    item.action.decision_id,
                    approved_by=approver_id,
                )
            )

        lease_store = ExecutionLeaseStore(
            authorization_store
            .database_path
        )

        bridge = SafeDecisionExecutionBridge(
            action_service=
                runtime.action_service,
            authorization_store=
                authorization_store,
            lease_store=lease_store,
        )

        execution = bridge.execute(
            decision_id=
                item.action.decision_id,
            authorization_id=
                authorization_id,
            plan=item.plan,
            owner_id=payload.owner_id,
            lease_ttl_seconds=(
                payload
                .lease_ttl_seconds
            ),
            fail_step_ids=(
                payload.fail_step_ids
            ),
        )

        evidence_builder = (
            DecisionExecutionEvidenceBuilder(
                audit_store=
                    get_audit_store(),
                authorization_store=
                    authorization_store,
                lease_store=lease_store,
            )
        )

        evidence = evidence_builder.build(
            result=execution,
            plan=item.plan,
            trace_id=payload.trace_id,
            created_by=(
                "decision-execution-api"
            ),
        )

    except HTTPException:
        raise
    except DecisionExecutionRuntimeNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except SafeDecisionExecutionNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except LeaseConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "type":
                    "lease_conflict",
                "message":
                    str(exc),
                "authorization_id":
                    exc.authorization_id,
                "owner_id":
                    exc.owner_id,
            },
        ) from exc
    except (
        SafeDecisionExecutionBindingError,
        SafeDecisionExecutionNotAllowed,
    ) as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "type":
                    "execution_not_allowed",
                "message":
                    str(exc),
            },
        ) from exc
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except (
        SafeDecisionExecutionBridgeError,
        OSError,
        RuntimeError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    return {
        "authorization_id":
            authorization_id,
        "execution":
            execution.to_dict(),
        "evidence":
            evidence.to_dict(),
        "safety": {
            "dry_run_only":
                True,
            "lease_enforced":
                True,
            "audit_verified":
                evidence.verified,
            "lease_token_exposed":
                False,
            "network_io_performed":
                False,
            "device_command_executed":
                False,
        },
    }
