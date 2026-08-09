import pytest

from app.models.controlled_rollback_contract import (
    ControlledRollbackContract,
    RollbackOutcome,
    RollbackReadiness,
    RollbackRequirement,
    mutating_rollback_contract,
    read_only_rollback_contract,
)


def test_read_only_contract_never_requires_rollback() -> None:
    contract = read_only_rollback_contract()

    assert contract.rollback_required is False
    assert contract.rollback_ready is False
    assert contract.rollback_attempted is False
    assert contract.rollback_performed is False

    assert (
        contract.effective_status
        == "NOT_REQUIRED_READ_ONLY"
    )

    assert (
        contract.live_execution_allowed
        is False
    )

    assert (
        contract.device_command_executed
        is False
    )


def test_mutating_contract_without_rollback_is_missing() -> None:
    contract = mutating_rollback_contract(
        rollback_available=False
    )

    assert contract.rollback_required is True
    assert contract.rollback_ready is False

    assert (
        contract.effective_status
        == "REQUIRED_MISSING"
    )

    assert contract.rollback_attempted is False


def test_mutating_contract_with_rollback_is_ready() -> None:
    contract = mutating_rollback_contract(
        rollback_available=True
    )

    assert contract.rollback_required is True
    assert contract.rollback_ready is True
    assert contract.rollback_attempted is False

    assert (
        contract.effective_status
        == "READY"
    )


def test_read_only_contract_cannot_claim_rollback_attempt() -> None:
    with pytest.raises(
        ValueError,
        match="cannot attempt rollback",
    ):
        ControlledRollbackContract(
            requirement=(
                RollbackRequirement.NOT_REQUIRED
            ),
            readiness=(
                RollbackReadiness.NOT_APPLICABLE
            ),
            outcome=(
                RollbackOutcome.STARTED
            ),
            read_only=True,
        )


def test_required_rollback_cannot_start_when_missing() -> None:
    with pytest.raises(
        ValueError,
        match="unless readiness is READY",
    ):
        ControlledRollbackContract(
            requirement=(
                RollbackRequirement.REQUIRED
            ),
            readiness=(
                RollbackReadiness.MISSING
            ),
            outcome=(
                RollbackOutcome.STARTED
            ),
            read_only=False,
        )


def test_contract_cannot_enable_live_rollback() -> None:
    with pytest.raises(
        ValueError,
        match="cannot allow live rollback execution",
    ):
        ControlledRollbackContract(
            requirement=(
                RollbackRequirement.REQUIRED
            ),
            readiness=(
                RollbackReadiness.READY
            ),
            outcome=(
                RollbackOutcome.NOT_ATTEMPTED
            ),
            read_only=False,
            live_execution_allowed=True,
        )


def test_contract_cannot_claim_device_command() -> None:
    with pytest.raises(
        ValueError,
        match="cannot claim device command execution",
    ):
        ControlledRollbackContract(
            requirement=(
                RollbackRequirement.REQUIRED
            ),
            readiness=(
                RollbackReadiness.READY
            ),
            outcome=(
                RollbackOutcome.VERIFIED
            ),
            read_only=False,
            device_command_executed=True,
        )


def test_verified_contract_is_evidence_only() -> None:
    contract = ControlledRollbackContract(
        requirement=(
            RollbackRequirement.REQUIRED
        ),
        readiness=(
            RollbackReadiness.READY
        ),
        outcome=(
            RollbackOutcome.VERIFIED
        ),
        read_only=False,
    )

    assert contract.rollback_attempted is True
    assert contract.rollback_performed is True
    assert contract.effective_status == "VERIFIED"

    assert (
        contract.live_execution_allowed
        is False
    )

    assert (
        contract.device_command_executed
        is False
    )
