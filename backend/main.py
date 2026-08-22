"""
EdgeMind KAVACH API — main entry point.
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import tasks, auth, agent, rag, vision, documents, artifacts
from database.session import create_tables

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="EdgeMind KAVACH API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Phase 9 will restrict this to the actual frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(tasks.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(agent.router, prefix="/api")
app.include_router(rag.router, prefix="/api")
app.include_router(vision.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(artifacts.router, prefix="/api")


@app.on_event("startup")
def on_startup():
    logger.info("Creating DB tables if they don't exist...")
    create_tables()
    logger.info("DB ready.")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def read_root():
    return {"message": "Welcome to EdgeMind KAVACH API"}
