from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import sources, web
from app.config import NAME, PROJECT, ROOT, RULE_VERSION, database_path
from app.errors import BusinessError, response_for_error
from app.store import Ledger

from app.modules.m1_intake.handler import router as intake
from app.modules.m2_calibration.handler import router as calibration
from app.modules.m3_alignment.handler import router as alignment
from app.modules.m4_soak.handler import router as soak
from app.modules.m5_gaps.handler import router as gaps
from app.modules.m6_reconcile.handler import router as reconcile
from app.modules.m7_archive.handler import router as archive


def create_app(db_path=None):
    @asynccontextmanager
    async def lifespan(api):
        api.state.ledger = Ledger(db_path if db_path is not None else database_path())
        yield

    api = FastAPI(
        title=NAME,
        lifespan=lifespan,
        swagger_ui_parameters={"defaultModelsExpandDepth": -1},
    )
    api.add_exception_handler(BusinessError, response_for_error)
    api.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")
    for router in (
        web.router,
        sources.router,
        intake,
        calibration,
        alignment,
        soak,
        gaps,
        reconcile,
        archive,
    ):
        api.include_router(router)

    @api.get("/api/health", tags=["服务状态"])
    def health():
        with api.state.ledger.connect() as conn:
            conn.execute("SELECT count(*) FROM runs").fetchone()
        return {"status": "ok", "project": PROJECT, "rules": RULE_VERSION}

    return api


app = create_app()
