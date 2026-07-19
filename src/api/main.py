"""API da plataforma simbios3."""

from fastapi import FastAPI

from src.api.routes.cases import router as cases_router
from src.api.routes.events import router as eventos_router
from src.api.routes.painel import router as painel_router
from src.api.routes.verify import router as verify_router
from src.api.routes.watchlist import router as watchlist_router
from src.api.routes.webhooks import router as webhooks_router

app = FastAPI(title="simbios3")
app.include_router(eventos_router)
app.include_router(verify_router)
app.include_router(watchlist_router)
app.include_router(webhooks_router)
app.include_router(cases_router)
app.include_router(painel_router)
