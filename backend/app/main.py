from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services.seed import seed_if_empty


def _migrate() -> None:
    """Lightweight column additions for databases created before a column existed."""
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        cols = {c["name"] for c in inspect(conn).get_columns("hang_rails")}
        if "max_active_items" not in cols:
            conn.execute(text("ALTER TABLE hang_rails ADD COLUMN max_active_items INTEGER"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _migrate()
    if settings.seed_on_empty:
        db = SessionLocal()
        try:
            seed_if_empty(db)
        finally:
            db.close()
    yield


app = FastAPI(title="HangRail", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")
