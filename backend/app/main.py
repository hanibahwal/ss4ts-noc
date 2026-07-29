from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.main_legacy import app as legacy_app


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="SS4TS Network Operations Center API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

# New versioned API
app.include_router(api_router)

# Temporary compatibility layer for the current frontend.
# This preserves /api/devices, /api/metrics/{ip}, /api/lte/{ip}, etc.
for route in legacy_app.routes:
    route_path = getattr(route, "path", "")

    if route_path.startswith("/api/") and not route_path.startswith("/api/v1/"):
        app.router.routes.append(route)


@app.get("/")
def root() -> dict:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "api": "/api/v1",
        "legacy_api": "/api",
        "docs": "/docs",
    }
