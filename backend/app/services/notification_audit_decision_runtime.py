from __future__ import annotations

from pathlib import Path

from app.services.notification_audit import (
    NotificationAuditStore,
)

from app.services.notification_audit_intelligence import (
    NotificationAuditIntelligence,
)

from app.services.notification_audit_decision import (
    NotificationAuditDecisionEngine,
)

from app.services.notification_audit_decision_history import (
    NotificationDecisionHistoryStore,
)



class NotificationDecisionRuntime:


    def __init__(
        self,
        database_path: Path,
    ):

        self.audit_store = (
            NotificationAuditStore(
                database_path
            )
        )

        self.risk_engine = (
            NotificationAuditIntelligence(
                self.audit_store
            )
        )

        self.decision_engine = (
            NotificationAuditDecisionEngine()
        )

        self.history_store = (
            NotificationDecisionHistoryStore(
                database_path
            )
        )



    def execute(self):

        risk = (
            self.risk_engine.calculate()
        )


        decision = (
            self.decision_engine.calculate(
                risk
            )
        )


        history = (
            self.history_store.create_history(
                decision=decision.decision.value,

                confidence=decision.confidence,

                risk_level=decision.risk_level,

                risk_score=decision.risk_score,

                reason=decision.reason,

                actions=decision.actions,
            )
        )


        return history
