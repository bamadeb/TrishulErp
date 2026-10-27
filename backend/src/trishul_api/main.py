import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import Engine, text

from trishul_api.auth.identity import IdentityProvider, create_identity_provider
from trishul_api.auth.tokens import TokenVerifier, create_token_verifier
from trishul_api.auth.users import UserDirectory, database_user_loader
from trishul_api.common.errors import STANDARD_ERROR_RESPONSES, install_error_handlers, problem
from trishul_api.common.security import install_security_headers
from trishul_api.config import Settings, get_settings
from trishul_api.db import create_db_engine
from trishul_api.modules.core.router import router as core_router
from trishul_api.modules.core.users.router import router as users_router
from trishul_api.modules.service.router import router as service_router

# One router per module. A new module is added here and nowhere else.
V1_ROUTERS: list[APIRouter] = [core_router, users_router, service_router]


def create_api_v1(settings: Settings) -> FastAPI:
    """Version 1 of the API, mounted at settings.api_prefix. Its OpenAPI paths are relative to that
    prefix (/me, /svc/service-calls), so the generated Angular client uses apiBaseUrl as its root.
    A breaking change goes into a v2 app mounted beside it."""
    api = FastAPI(
        title="Trishul ERP API",
        version="1.0.0",
        docs_url="/docs" if settings.environment != "prod" else None,
        redoc_url=None,
        # Operation ids = function names, so the generated client reads listServiceCalls(), me(), ...
        generate_unique_id_function=lambda route: route.name,
    )
    install_error_handlers(api)
    for router in V1_ROUTERS:
        api.include_router(router, responses=STANDARD_ERROR_RESPONSES)
    return api


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
    token_verifier: TokenVerifier | None = None,
    identity_provider: IdentityProvider | None = None,
) -> FastAPI:
    """Application factory and composition root. Tests pass their own engine, token verifier and
    identity provider."""
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    api = create_api_v1(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db_engine = engine or create_db_engine(settings)
        app.state.engine = db_engine
        # Request dependencies run inside the mounted API and read its state.
        api.state.engine = db_engine
        api.state.token_verifier = token_verifier or create_token_verifier(settings)
        api.state.user_directory = UserDirectory(database_user_loader(db_engine), settings.user_cache_seconds)
        api.state.identity_provider = identity_provider or create_identity_provider(settings)
        yield
        db_engine.dispose()

    app = FastAPI(lifespan=lifespan, openapi_url=None, docs_url=None, redoc_url=None)
    app.state.api_v1 = api
    install_security_headers(app, docs_paths=(f"{settings.api_prefix}/docs", f"{settings.api_prefix}/openapi.json"))
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "If-Match",
            "X-Branch-Id",
            "X-Principal-Id",
            "X-Client-Platform",
        ],
        expose_headers=["ETag", "Location"],
        max_age=600,
    )
    install_error_handlers(app)
    app.mount(settings.api_prefix, api)

    @app.get("/health")
    def health() -> dict[str, str]:
        """Liveness for the load balancer; does not touch the database."""
        return {"status": "ok"}

    @app.get("/health/ready", response_model=None)
    def ready() -> object:
        try:
            with app.state.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception:
            logging.getLogger(__name__).exception("Database not reachable")
            return problem(503, "Database not reachable")
        return {"status": "ok"}

    return app
