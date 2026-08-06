# H23.4.5.5.12.X.4
# SS4TS NOC API Router
# Enterprise Fleet Autonomous NOC Platform

from fastapi import APIRouter

from app.api.v1.executive_notification import router as executive_notification_router
from app.api.v1.ai import router as ai_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.decision_intelligence import router as decision_intelligence_router
from app.api.v1.decision_audits import router as decision_audits_router
from app.api.v1.decision_executions import router as decision_executions_router

from app.api.v1.execution_authorizations import router as execution_authorizations_router
from app.api.v1.execution_leases import router as execution_leases_router
from app.api.v1.execution_heartbeats import router as execution_heartbeats_router
from app.api.v1.execution_recovery import router as execution_recovery_router
from app.api.v1.execution_recovery_scheduler import router as execution_recovery_scheduler_router
from app.api.v1.execution_recovery_runtime import router as execution_recovery_runtime_router
from app.api.v1.execution_runtime_observability import router as execution_runtime_observability_router
from app.api.v1.execution_runtime_prometheus import router as execution_runtime_prometheus_router
from app.api.v1.controlled_execution_recovery_runtime import (
    router as controlled_execution_recovery_runtime_router,
)

from app.api.v1.health import router as health_router
from app.api.v1.knowledge_graph import router as knowledge_graph_router

from app.api.v1.notification import router as notification_router
from app.api.v1.notification_audit import router as notification_audit_router
from app.api.v1.notification_audit_search import router as notification_audit_search_router
from app.api.v1.notification_audit_stats import router as notification_audit_stats_router
from app.api.v1.notification_audit_timeline import router as notification_audit_timeline_router
from app.api.v1.notification_audit_intelligence import router as notification_audit_intelligence_router
from app.api.v1.notification_audit_decision import router as notification_audit_decision_router
from app.api.v1.notification_audit_decision_history import router as notification_audit_decision_history_router

from app.api.v1.notification_response import router as notification_response_router
from app.api.v1.notification_response_approval import router as notification_response_approval_router
from app.api.v1.notification_response_approval_dashboard import router as notification_response_approval_dashboard_router
from app.api.v1.notification_response_approval_prometheus import router as notification_response_approval_prometheus_router

from app.api.v1.network_intelligence import router as network_intelligence_router
from app.api.v1.executive_narrative import router as executive_narrative_router
from app.api.v1.executive_prediction import router as executive_prediction_router

from app.api.v1.routeros import router as routeros_router
from app.api.v1.traffic import router as traffic_router

from app.api.v1.remediation_execution import router as remediation_execution_router
from app.api.v1.executive_remediation import router as executive_remediation_router
from app.api.v1.remediation_history import router as remediation_history_router
from app.api.v1.remediation_analytics import router as remediation_analytics_router


# =====================================================
# H23.4.5.5.12.X.4.7.3
# Enterprise Fleet Risk Prediction API
# =====================================================

from app.api.v1.fleet_registry import router as fleet_registry_router
from app.api.v1.fleet_health import router as fleet_health_router
from app.api.v1.fleet_prediction import router as fleet_prediction_router


api_router = APIRouter(
    prefix="/api/v1"
)


for router in [

    ai_router,
    dashboard_router,
    decision_intelligence_router,
    decision_audits_router,
    decision_executions_router,

    execution_authorizations_router,
    execution_leases_router,
    execution_heartbeats_router,

    execution_recovery_router,
    execution_recovery_scheduler_router,
    execution_recovery_runtime_router,

    execution_runtime_observability_router,
    execution_runtime_prometheus_router,
    controlled_execution_recovery_runtime_router,

    health_router,
    knowledge_graph_router,

    notification_router,
    notification_audit_router,
    notification_audit_search_router,
    notification_audit_stats_router,
    notification_audit_timeline_router,
    notification_audit_intelligence_router,
    notification_audit_decision_router,
    notification_audit_decision_history_router,

    notification_response_router,
    notification_response_approval_router,
    notification_response_approval_dashboard_router,
    notification_response_approval_prometheus_router,

    executive_notification_router,

    network_intelligence_router,
    executive_narrative_router,
    executive_prediction_router,

    remediation_execution_router,
    executive_remediation_router,
    remediation_history_router,
    remediation_analytics_router,


    # =================================================
    # Enterprise Fleet Intelligence
    # =================================================

    fleet_registry_router,
    fleet_health_router,
    fleet_prediction_router,

]:


    api_router.include_router(router)
