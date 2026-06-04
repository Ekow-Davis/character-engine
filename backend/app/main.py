from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

from app.api.routes import health

from app.api.routes import auth
from app.core.auth import require_auth

from app.api.routes import characters
from app.api.routes import chat

# With the other routers


app = FastAPI(
    title="Character Engine API",
    version="1.0.0",
    docs_url="/docs" if settings.is_dev else None,
    redoc_url="/redoc" if settings.is_dev else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])

# Protected
app.include_router(
    characters.router,
    prefix="/api/characters",
    tags=["characters"],
    # dependencies=[Depends(require_auth)],
)

app.include_router(
    chat.router,
    prefix="/api/chat",
    tags=["chat"],
    # dependencies=[Depends(require_auth)],
)

@app.get("/")
async def root():
    return {"message": "Character Engine API", "version": "1.0.0"}