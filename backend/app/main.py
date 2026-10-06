from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app.api.routes import api_router
from app.core.config import settings
from app.core.cors import cors_config
from app.db.session import SessionLocal, create_tables, engine


def _additive_sqlite_migrations() -> None:
    """Add columns introduced after the initial schema without touching
    pre-existing data. SQLite cannot run ALTER COLUMN, but ADD COLUMN is
    cheap and idempotent when guarded by an inspector check.

    Required by the four-layer memory upgrade:
      - chat_sessions: task-state columns (goal / intent / version / reason)
      - chat_messages: per-turn audit metadata (rules_query / evidence / guardrail)
    """
    additions = {
        "chat_sessions": [
            ("current_task_goal", "TEXT NOT NULL DEFAULT ''"),
            ("current_task_intent_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("goal_version", "INTEGER NOT NULL DEFAULT 1"),
            ("goal_reset_reason", "VARCHAR(60) NOT NULL DEFAULT ''"),
        ],
        "chat_messages": [
            ("rules_query", "TEXT NOT NULL DEFAULT ''"),
            ("evidence_ids_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("guardrail_json", "TEXT NOT NULL DEFAULT '{}'"),
        ],
    }
    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
        with engine.begin() as conn:
            for table, cols in additions.items():
                if table not in existing_tables:
                    continue
                existing_cols = {c["name"] for c in inspector.get_columns(table)}
                for col_name, col_def in cols:
                    if col_name in existing_cols:
                        continue
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {col_name} {col_def}'))
    except Exception:
        # Never block startup on a best-effort migration; SQLAlchemy create_all
        # already handles fresh databases.
        pass


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_tables()
    _additive_sqlite_migrations()
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Seed default Core Memory rules on first boot so the new DB-backed
    # core_memory layer has content even before any admin edits.
    try:
        from app.services.memory.core_memory import seed_default_core_rules

        db = SessionLocal()
        try:
            seed_default_core_rules(db)
        finally:
            db.close()
    except Exception:
        # Never block startup on a seed failure; the fallback constants still work.
        pass

    yield


app = FastAPI(
    title="Fire Hazard Detection API",
    description="Upload an image and get AI analysis result.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, **cors_config)

app.mount("/static", StaticFiles(directory=str(settings.UPLOAD_DIR)), name="static")
web_dir = settings.BASE_DIR.parent / "web"
if web_dir.exists():
    app.mount("/web", StaticFiles(directory=str(web_dir), html=True), name="web")

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def root():
    return {
        "message": "Fire Hazard Detection API",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

