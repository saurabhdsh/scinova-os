import logging
import os

# Disable ChromaDB anonymous telemetry before any route/service imports chromadb.
os.environ.setdefault("ANONYMIZED_TELEMETRY", "FALSE")
try:
    import posthog

    posthog.disabled = True
except ImportError:
    pass

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, SessionLocal, engine, get_db
from app.db_migrate import run_migrations
from app.routes import admin, api, auth
from app.seed import seed_database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    run_migrations(engine)
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.chroma_persist_dir, exist_ok=True)
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    logger.info("SciAi-Nova OS started (env=%s)", settings.environment)
    yield


app = FastAPI(
    title="SciAi-Nova OS API",
    description="SciFabric AgentOS - AI-native Scientific Data Fabric and Agent Operating System for Pharma R&D",
    version="1.0.0",
    lifespan=lifespan,
)

origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(api.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "healthy", "platform": "SciAi-Nova OS", "version": "1.0.0"}


@app.get("/health/ready")
def health_ready(db: Session = Depends(get_db)):
    checks: dict[str, str] = {}

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    if settings.use_celery:
        try:
            import redis

            client = redis.from_url(settings.redis_url, socket_connect_timeout=2)
            client.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"unavailable: {exc}"
    else:
        checks["redis"] = "skipped"

    if settings.neo4j_enabled:
        try:
            from app.services.neo4j_client import neo4j_client

            neo = neo4j_client.stats()
            checks["neo4j"] = "ok" if neo.get("connected") else "unavailable"
        except Exception as exc:
            checks["neo4j"] = f"error: {exc}"

    status = "ready" if checks.get("database") == "ok" else "degraded"
    return {"status": status, "checks": checks}
