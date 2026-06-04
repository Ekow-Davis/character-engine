from fastapi import HTTPException, Header
from typing import Optional
from app.core.database import supabase_admin


async def require_auth(authorization: Optional[str] = Header(None)) -> dict:
    """
    Validates the Supabase JWT from the Authorization header.
    Use as a FastAPI dependency on any protected route.

    Usage:
        @router.get("/protected")
        async def protected_route(user: dict = Depends(require_auth)):
            ...
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.removeprefix("Bearer ").strip()

    try:
        response = supabase_admin.auth.get_user(token)
        if not response or not response.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return {"id": response.user.id, "email": response.user.email}
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def require_owner(authorization: Optional[str] = Header(None)) -> dict:
    """
    Same as require_auth but also checks the user is in allowed_users with role=owner.
    Use on admin routes.
    """
    user = await require_auth(authorization)

    result = supabase_admin.table("allowed_users").select("role").eq(
        "email", user["email"]
    ).single().execute()

    if not result.data:
        raise HTTPException(status_code=403, detail="Access denied")

    user["role"] = result.data["role"]
    return user
