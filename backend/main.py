"""
EdgeMind KAVACH API — main entry point.
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import tasks, auth, agent, rag, vision, documents, artifacts, security
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
app.include_router(security.router, prefix="/api")


@app.on_event("startup")
def on_startup():
    logger.info("Creating DB tables if they don't exist...")
    create_tables()
    logger.info("DB ready.")


@app.get("/health")
def health_check():
    return {"status": "ok"}


from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# Serve the static UI files from the UI directory
ui_dir = os.path.join(os.path.dirname(__file__), "..", "ui")
if os.path.isdir(ui_dir):
    app.mount("/static", StaticFiles(directory=ui_dir), name="static")

@app.get("/")
def read_root():
    ui_path = os.path.join(ui_dir, "edgemind_ui.html")
    if os.path.isfile(ui_path):
        return FileResponse(ui_path)
    return {"message": "Welcome to EdgeMind KAVACH API"}
