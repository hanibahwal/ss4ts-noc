from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.api.v1.assets import router as assets_router
from app.api.v1.asset_intelligence import (
    router as asset_intelligence_router,
)
from app.api.v1.executive_narrative import (
    router as executive_narrative_router,
)

from app.api.v1.remediation_approval import (
    router as remediation_approval_router,
)

from app.core.config import settings

from app.main_legacy import app as legacy_app

from app.services.decision_execution_runtime import (
    runtime as decision_execution_runtime,
)

from app.services.execution_recovery_scheduler_runtime import (
    get_recovery_scheduler_runtime,
    runtime_enabled_from_environment,
)

from app.services.controlled_execution_recovery_runtime import (
    get_controlled_recovery_runtime,
    runtime_enabled_from_environment as controlled_recovery_runtime_enabled,
)


@asynccontextmanager
async def lifespan(application: FastAPI):

    runtime = None
    controlled_recovery_runtime = None

    decision_execution_runtime.initialize()

    application.state.decision_execution_runtime = (
        decision_execution_runtime
    )

    if runtime_enabled_from_environment():

        runtime = get_recovery_scheduler_runtime()

        await runtime.start()

        application.state.recovery_scheduler_runtime = runtime


    if controlled_recovery_runtime_enabled():

        controlled_recovery_runtime = (
            get_controlled_recovery_runtime()
        )

        await controlled_recovery_runtime.start()

        application.state.controlled_recovery_runtime = (
            controlled_recovery_runtime
        )


    try:

        yield

    finally:

        if controlled_recovery_runtime is not None:
            await controlled_recovery_runtime.stop()

        if runtime is not None:
            await runtime.stop()



app = FastAPI(

    title=settings.app_name,

    version=settings.app_version,

    description=(
        "SS4TS Network Operations Center API "
        "with AI Decision and Automated Remediation"
    ),

    lifespan=lifespan,

)



app.add_middleware(

    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=False,

    allow_methods=[
        "GET",
        "POST",
        "OPTIONS",
    ],

    allow_headers=["*"],

)



# =====================================================
# Versioned API
# =====================================================

app.include_router(
    api_router
)



# =====================================================
# Asset Inventory API
# H29.3 Asset Inventory
# =====================================================

app.include_router(
    assets_router
)



# =====================================================
# Asset Intelligence API
# H29.5 Asset Intelligence Engine
# =====================================================

app.include_router(
    asset_intelligence_router
)



# =====================================================
# Executive Narrative API
# H30 Executive AI Intelligence
# =====================================================

app.include_router(
    executive_narrative_router
)



# =====================================================
# Human Approval & Remediation Workflow
# =====================================================

app.include_router(
    remediation_approval_router
)



# =====================================================
# Legacy Compatibility Layer
# Keeps old /api endpoints working
# =====================================================

for route in legacy_app.routes:

    route_path = getattr(
        route,
        "path",
        "",
    )

    if (
        route_path.startswith("/api/")
        and
        not route_path.startswith("/api/v1/")
    ):

        app.router.routes.append(
            route
        )



@app.get("/")
def root() -> dict:

    return {

        "name": settings.app_name,

        "version": settings.app_version,

        "api": "/api/v1",

        "legacy_api": "/api",

        "docs": "/docs",

        "modules": [

            "Network Intelligence",

            "AI Prediction Engine",

            "Pattern Recognition",

            "Failure Forecasting",

            "Executive Decision",

            "Executive Narrative AI",

            "Response Action Planner",

            "Human Approval Workflow",

            "Automated Remediation",

        ],

    }
