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
from app.api.v1.health import (
    router as health_router,
)
from app.api.v1.knowledge_graph import (
    router as knowledge_graph_router,
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
    knowledge_graph_router
)
