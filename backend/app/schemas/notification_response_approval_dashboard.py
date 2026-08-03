from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel



class ApprovalDashboardSummary(BaseModel):

    total_pending: int

    high_risk: int

    medium_risk: int

    low_risk: int

    approved_today: int

    rejected_today: int




class ApprovalDashboardItem(BaseModel):

    approval_id: str

    action_id: str

    action_type: str

    risk_level: str

    risk_score: int

    decision: str

    reason: str

    requires_approval: bool

    created_at: datetime




class ApprovalExecutionView(BaseModel):

    approval_id: str

    status: str

    execution_id: str | None

    execution_status: str

    approved_by: str | None

    approved_at: datetime | None




class ApprovalTimelineEvent(BaseModel):

    type: str

    status: str

    timestamp: datetime
