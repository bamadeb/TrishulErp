import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import Engine, text

from trishul_api.auth.cognito_secret import apply_cognito_secret
from trishul_api.auth.identity import IdentityProvider, create_identity_provider
from trishul_api.auth.tokens import TokenVerifier, create_token_verifier
from trishul_api.auth.users import UserDirectory, database_user_loader
from trishul_api.common.errors import STANDARD_ERROR_RESPONSES, install_error_handlers, problem
from trishul_api.common.security import install_security_headers
from trishul_api.config import Settings, get_settings
from trishul_api.db import create_db_engine
from trishul_api.modules.core.customers.router import router as customers_router
from trishul_api.modules.core.devices.router import router as devices_router
from trishul_api.modules.core.employees.router import router as employees_router
from trishul_api.modules.core.router import router as core_router
from trishul_api.modules.core.users.router import router as users_router
from trishul_api.modules.presales.router import router as presales_router
from trishul_api.modules.service.router import router as service_router
from trishul_api.modules.trk.router import router as trk_router
from trishul_api.secrets import SecretProvider, create_secret_provider

# One router per module. A new module is added here and nowhere else.
V1_ROUTERS: list[APIRouter] = [
    core_router,
    users_router,
    employees_router,
    customers_router,
    devices_router,
    service_router,
    presales_router,
    trk_router,
]


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
    secret_provider: SecretProvider | None = None,
) -> FastAPI:
    """Application factory and composition root. Tests pass their own engine, token verifier, identity
    provider and secret provider."""
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    api = create_api_v1(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        secrets = secret_provider or create_secret_provider(settings)
        # Fill the Cognito identifiers from Secrets Manager when configured; env values are the fallback.
        resolved = apply_cognito_secret(settings, secrets)
        db_engine = engine or create_db_engine(resolved, secrets)
        app.state.secret_provider = secrets
        app.state.engine = db_engine
        # Request dependencies run inside the mounted API and read its state.
        api.state.secret_provider = secrets
        api.state.engine = db_engine
        api.state.token_verifier = token_verifier or create_token_verifier(resolved)
        api.state.user_directory = UserDirectory(database_user_loader(db_engine), resolved.user_cache_seconds)
        api.state.identity_provider = identity_provider or create_identity_provider(resolved)

        # Warm the slow first-request costs in the background so they don't land on a user's first click:
        # the initial DB connection (TLS handshake + login + secret fetch) and the Cognito JWKS fetch.
        # Best-effort and non-blocking: if the database is unreachable at boot, startup still succeeds and
        # the connection is made on the first request instead. In production the load balancer's readiness
        # probe already opens a connection, so this mainly helps local dev and the first call after a deploy.
        async def warm_up() -> None:
            def work() -> None:
                log = logging.getLogger(__name__)
                try:
                    with db_engine.connect() as connection:
                        connection.execute(text("SELECT 1"))
                except Exception:
                    log.warning("Database warm-up skipped; will connect on first request", exc_info=True)
                try:
                    api.state.token_verifier.warm()
                except Exception:
                    log.warning("Token key warm-up skipped; will fetch on first sign-in", exc_info=True)

            await asyncio.to_thread(work)

        warm_task = asyncio.create_task(warm_up())
        try:
            yield
        finally:
            warm_task.cancel()
            with suppress(BaseException):
                await warm_task
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
