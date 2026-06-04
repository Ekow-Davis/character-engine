from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from app.core.database import supabase, supabase_admin
from app.core.auth import require_auth
from app.core.config import settings

router = APIRouter()


# ─── Request Schemas ──────────────────────────────────────────────────────────
class MagicLinkRequest(BaseModel):
    email: EmailStr


# ─── Send magic link ──────────────────────────────────────────────────────────
@router.post("/login")
async def request_magic_link(body: MagicLinkRequest):
    """
    Check if email is whitelisted, then send a magic link via Supabase Auth.
    Always returns 200 to avoid leaking which emails are allowed.
    """
    # Check whitelist
    result = supabase_admin.table("allowed_users").select("id").eq(
        "email", body.email
    ).execute()

    if not result.data:
        # Return 200 anyway — don't reveal that the email isn't whitelisted
        return {"message": "If that email is registered, a login link is on its way."}

    try:
        supabase.auth.sign_in_with_otp({
            "email": body.email,
            "options": {
                "should_create_user": False,
                "email_redirect_to": f"{settings.frontend_url}/auth/callback",
            }
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send login link: {str(e)}")

    return {"message": "If that email is registered, a login link is on its way."}


# ─── Verify session ───────────────────────────────────────────────────────────
@router.get("/me")
async def get_current_user(user: dict = Depends(require_auth)):
    """
    Returns the current authenticated user.
    Frontend calls this on load to check if the session is still valid.
    """
    return {
        "id": user["id"],
        "email": user["email"],
    }


# ─── Logout ───────────────────────────────────────────────────────────────────
@router.post("/logout")
async def logout(user: dict = Depends(require_auth)):
    """
    Invalidates the current session token.
    """
    try:
        supabase_admin.auth.admin.sign_out(user["id"])
    except Exception:
        pass  # Session may already be expired — still return success
    return {"message": "Logged out"}