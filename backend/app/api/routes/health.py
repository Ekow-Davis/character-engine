from fastapi import APIRouter
from app.core.database import supabase_admin
from app.core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check — verifies app is running and Supabase is reachable."""
    db_ok = False
    try:
        # Lightweight query to confirm Supabase connection
        supabase_admin.table("characters").select("id").limit(1).execute()
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "env": settings.app_env,
        "database": "connected" if db_ok else "unreachable",
    }
