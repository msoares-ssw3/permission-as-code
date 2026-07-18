"""API da plataforma simbios3."""

from fastapi import FastAPI

from src.api.routes.events import router as eventos_router

app = FastAPI(title="simbios3")
app.include_router(eventos_router)
