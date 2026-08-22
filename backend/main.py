from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import tasks

app = FastAPI(title="EdgeMind KAVACH API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks.router, prefix="/api")

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/")
def read_root():
    return {"message": "Welcome to EdgeMind KAVACH API"}
