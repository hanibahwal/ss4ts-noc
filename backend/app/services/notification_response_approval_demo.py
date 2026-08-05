from datetime import datetime, timedelta, timezone

from app.models.notification_response_approval import (
    NotificationResponseApproval,
    ApprovalStatus,
)


def generate_demo_approvals():

    now = datetime.now(timezone.utc)

    return [

        NotificationResponseApproval(
            approval_id="demo-1001",
            execution_id="exec-1001",
            action_id="action-1001",
            action_type="notification-send",
            requested_reason="Normal notification approval",
            status=ApprovalStatus.PENDING,
            approved_by=None,
            requested_at=now - timedelta(minutes=20),
            approved_at=None,
        ),


        NotificationResponseApproval(
            approval_id="demo-1002",
            execution_id="exec-1002",
            action_id="action-1002",
            action_type="critical-notification",
            requested_reason="High priority notification approval",
            status=ApprovalStatus.PENDING,
            approved_by=None,
            requested_at=now - timedelta(hours=8),
            approved_at=None,
        ),


        NotificationResponseApproval(
            approval_id="demo-1003",
            execution_id="exec-1003",
            action_id="action-1003",
            action_type="emergency-response",
            requested_reason="Critical escalation approval",
            status=ApprovalStatus.PENDING,
            approved_by=None,
            requested_at=now - timedelta(hours=24),
            approved_at=None,
        ),

    ]
