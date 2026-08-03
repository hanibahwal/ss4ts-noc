from fastapi import APIRouter


from app.api.v1.ai import (
    router as ai_router,
)


from app.api.v1.dashboard import (
    router as dashboard_router,
)


from app.api.v1.decision_intelligence import (
    router as decision_intelligence_router,
)


from app.api.v1.decision_audits import (
    router as decision_audits_router,
)


from app.api.v1.execution_authorizations import (
    router as execution_authorizations_router,
)


from app.api.v1.execution_leases import (
    router as execution_leases_router,
)


from app.api.v1.execution_heartbeats import (
    router as execution_heartbeats_router,
)


from app.api.v1.execution_recovery import (
    router as execution_recovery_router,
)


from app.api.v1.execution_recovery_scheduler import (
    router as execution_recovery_scheduler_router,
)


from app.api.v1.execution_recovery_runtime import (
    router as execution_recovery_runtime_router,
)


from app.api.v1.execution_runtime_observability import (
    router as execution_runtime_observability_router,
)


from app.api.v1.execution_runtime_prometheus import (
    router as execution_runtime_prometheus_router,
)


from app.api.v1.health import (
    router as health_router,
)


from app.api.v1.knowledge_graph import (
    router as knowledge_graph_router,
)


from app.api.v1.notification import (
    router as notification_router,
)


from app.api.v1.notification_audit import (
    router as notification_audit_router,
)


from app.api.v1.notification_audit_search import (
    router as notification_audit_search_router,
)


from app.api.v1.routeros import (
    router as routeros_router,
)


from app.api.v1.traffic import (
    router as traffic_router,
)



api_router = APIRouter(
    prefix="/api/v1"
)



api_router.include_router(
    health_router
)



api_router.include_router(
    dashboard_router
)



api_router.include_router(
    traffic_router
)



api_router.include_router(
    routeros_router
)



api_router.include_router(
    ai_router
)



api_router.include_router(
    decision_intelligence_router
)



api_router.include_router(
    decision_audits_router
)



api_router.include_router(
    execution_authorizations_router
)



api_router.include_router(
    execution_leases_router
)



api_router.include_router(
    execution_heartbeats_router
)



api_router.include_router(
    execution_recovery_router
)



api_router.include_router(
    execution_recovery_scheduler_router
)



api_router.include_router(
    execution_recovery_runtime_router
)



api_router.include_router(
    execution_runtime_observability_router
)



api_router.include_router(
    execution_runtime_prometheus_router
)



api_router.include_router(
    knowledge_graph_router
)



api_router.include_router(
    notification_router
)



api_router.include_router(
    notification_audit_router
)



# H23.4.5.5.12.16
# Notification Audit Query & Filtering Engine

api_router.include_router(
    notification_audit_search_router
)
