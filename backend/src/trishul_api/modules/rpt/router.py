import datetime as dt

from fastapi import APIRouter

from trishul_api.auth import SIGNED_IN_USERS, CurrentUserDep, DbSession, ScopeDep
from trishul_api.modules.rpt.dashboard import build_dashboard
from trishul_api.modules.rpt.schemas import Dashboard

router = APIRouter(prefix="/rpt", tags=["reports"])


@router.get(
    "/dashboard",
    summary="Home dashboard: the sections the user's permissions allow, for the selected branch and brand",
    # Every signed-in user has a home page; what it contains is decided per section by permission.
    openapi_extra=SIGNED_IN_USERS,
)
def get_dashboard(actor: CurrentUserDep, scope: ScopeDep, db: DbSession) -> Dashboard:
    return build_dashboard(db, actor, scope, dt.datetime.now(dt.UTC).replace(tzinfo=None))
