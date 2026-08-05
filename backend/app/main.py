from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from app.api.v1.router import api_router


from app.api.v1.remediation_approval import (
    router as remediation_approval_router,
)


from app.core.config import settings


from app.main_legacy import app as legacy_app


from app.services.execution_recovery_scheduler_runtime import (
    get_recovery_scheduler_runtime,
    runtime_enabled_from_environment,
)



@asynccontextmanager
async def lifespan(
    application: FastAPI,
):

    runtime = None


    if runtime_enabled_from_environment():

        runtime = get_recovery_scheduler_runtime()


        await runtime.start()


        application.state.recovery_scheduler_runtime = runtime



    try:

        yield



    finally:

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
# Human Approval & Remediation Workflow
# H23.4.5.5.12.X.4.6
# =====================================================

app.include_router(
    remediation_approval_router
)





# =====================================================
# Legacy Compatibility Layer
#
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

            "Response Action Planner",

            "Human Approval Workflow",

            "Automated Remediation",

        ],

    }
