from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.decision_action import (
    DecisionAction,
    DecisionActionStatus,
)
from app.models.execution_authorization import (
    ApprovalIdentity,
    AuthorizationStatus,
    ExecutionAuthorization,
)
from app.models.execution_concurrency import (
    AuthorizationMutationResult,
)
from app.models.execution_plan import (
    ExecutionPlan,
)
from app.services.decision_action_service import (
    DecisionActionConflict,
    DecisionActionService,
)
from app.services.execution_authorization import (
    ExecutionAuthorizationService,
)
from app.services.execution_authorization_store import (
    ExecutionAuthorizationStore,
)


class DecisionApprovalGatewayError(RuntimeError):
    """Base gateway error."""


class DecisionApprovalBindingError(
    DecisionApprovalGatewayError
):
    """Raised when decision and execution plan do not match."""


class DecisionApprovalNotFound(
    DecisionApprovalGatewayError
):
    """Raised when an authorization cannot be found."""


@dataclass(slots=True)
class DecisionApprovalRequest:
    action: DecisionAction
    authorization: ExecutionAuthorization

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.to_dict(),
            "authorization": (
                self.authorization.to_dict()
            ),
        }


@dataclass(slots=True)
class DecisionApprovalResult:
    action: DecisionAction
    authorization: ExecutionAuthorization
    mutation: AuthorizationMutationResult | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "action": self.action.to_dict(),
            "authorization": (
                self.authorization.to_dict()
            ),
        }

        if self.mutation is not None:
            payload["mutation"] = (
                self.mutation.to_dict()
            )

        return payload


class DecisionApprovalGateway:
    """
    Coordinates DecisionAction approval with the existing
    execution authorization engine.

    This gateway performs no network I/O and never executes
    commands on managed devices.
    """

    def __init__(
        self,
        *,
        action_service: DecisionActionService,
        authorization_store: ExecutionAuthorizationStore,
        authorization_service: (
            ExecutionAuthorizationService | None
        ) = None,
    ) -> None:
        if not isinstance(
            action_service,
            DecisionActionService,
        ):
            raise TypeError(
                "action_service must be a "
                "DecisionActionService"
            )

        if not isinstance(
            authorization_store,
            ExecutionAuthorizationStore,
        ):
            raise TypeError(
                "authorization_store must be an "
                "ExecutionAuthorizationStore"
            )

        self.action_service = action_service
        self.authorization_store = (
            authorization_store
        )
        self.authorization_service = (
            authorization_service
            or ExecutionAuthorizationService()
        )

    @staticmethod
    def _validate_binding(
        action: DecisionAction,
        plan: ExecutionPlan,
    ) -> None:
        if not isinstance(
            action,
            DecisionAction,
        ):
            raise TypeError(
                "action must be a DecisionAction"
            )

        if not isinstance(
            plan,
            ExecutionPlan,
        ):
            raise TypeError(
                "plan must be an ExecutionPlan"
            )

        if (
            plan.decision_id
            != action.decision_id
        ):
            raise DecisionApprovalBindingError(
                "Execution plan decision_id does not "
                "match DecisionAction decision_id"
            )

        if (
            action.status
            in {
                DecisionActionStatus.REJECTED,
                DecisionActionStatus.COMPLETED,
                DecisionActionStatus.FAILED,
                DecisionActionStatus.CANCELLED,
            }
        ):
            raise DecisionActionConflict(
                "Closed decision actions cannot create "
                "new authorization requests"
            )

    def request_authorization(
        self,
        *,
        action: DecisionAction,
        plan: ExecutionPlan,
        requester: ApprovalIdentity,
    ) -> DecisionApprovalRequest:
        self._validate_binding(
            action,
            plan,
        )

        if not isinstance(
            requester,
            ApprovalIdentity,
        ):
            raise TypeError(
                "requester must be an ApprovalIdentity"
            )

        authorization = (
            self.authorization_service.build(
                plan,
                requester=requester,
            )
        )

        authorization.metadata.update({
            "decision_action_id":
                action.decision_id,
            "incident_id":
                action.incident_id,
            "decision_action_status":
                action.status.value,
            "target":
                action.target.to_dict(),
            "command":
                action.command.to_dict(),
            "gateway":
                "decision_approval_gateway",
            "network_io_performed":
                False,
            "device_command_executed":
                False,
        })

        authorization = (
            self.authorization_store.create(
                authorization
            )
        )

        synchronized_action = action

        if (
            authorization.status
            is AuthorizationStatus.APPROVED
            and action.status
            is DecisionActionStatus.PENDING_APPROVAL
        ):
            synchronized_action = (
                self.action_service.approve(
                    action.decision_id,
                    approved_by=(
                        authorization.requester
                        .identity_id
                    ),
                )
            )

        return DecisionApprovalRequest(
            action=synchronized_action,
            authorization=authorization,
        )

    def approve(
        self,
        authorization_id: str,
        *,
        approver: ApprovalIdentity,
        expected_version: int,
        idempotency_key: str,
    ) -> DecisionApprovalResult:
        authorization = (
            self.authorization_store.get(
                authorization_id
            )
        )

        if authorization is None:
            raise DecisionApprovalNotFound(
                "Execution authorization not found: "
                f"{authorization_id}"
            )

        mutation = (
            self.authorization_store
            .approve_atomic(
                authorization_id,
                approver=approver,
                expected_version=(
                    expected_version
                ),
                idempotency_key=(
                    idempotency_key
                ),
            )
        )

        updated_authorization = (
            self.authorization_store.get(
                authorization_id
            )
        )

        if updated_authorization is None:
            raise DecisionApprovalNotFound(
                "Authorization disappeared after "
                "approval mutation"
            )

        action = self.action_service.get_action(
            updated_authorization.decision_id
        )

        if (
            action.status
            is DecisionActionStatus.PENDING_APPROVAL
        ):
            action = self.action_service.approve(
                action.decision_id,
                approved_by=(
                    approver.identity_id
                ),
            )

        return DecisionApprovalResult(
            action=action,
            authorization=updated_authorization,
            mutation=mutation,
        )

    def reject(
        self,
        authorization_id: str,
        *,
        approver: ApprovalIdentity,
        reason: str,
    ) -> DecisionApprovalResult:
        authorization = (
            self.authorization_store.get(
                authorization_id
            )
        )

        if authorization is None:
            raise DecisionApprovalNotFound(
                "Execution authorization not found: "
                f"{authorization_id}"
            )

        rejected = (
            self.authorization_store.reject(
                authorization_id,
                approver=approver,
                reason=reason,
            )
        )

        action = self.action_service.get_action(
            rejected.decision_id
        )

        if action.status in {
            DecisionActionStatus.PROPOSED,
            DecisionActionStatus.PENDING_APPROVAL,
            DecisionActionStatus.APPROVED,
        }:
            action = self.action_service.reject(
                action.decision_id,
                rejected_by=(
                    approver.identity_id
                ),
                reason=reason,
            )

        return DecisionApprovalResult(
            action=action,
            authorization=rejected,
        )

    def get_authorization(
        self,
        authorization_id: str,
    ) -> ExecutionAuthorization:
        authorization = (
            self.authorization_store.get(
                authorization_id
            )
        )

        if authorization is None:
            raise DecisionApprovalNotFound(
                "Execution authorization not found: "
                f"{authorization_id}"
            )

        return authorization
