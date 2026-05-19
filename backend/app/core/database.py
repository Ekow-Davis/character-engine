from supabase import create_client, Client
from app.core.config import settings

# Standard client — uses anon key, respects RLS
supabase: Client = create_client(
    settings.supabase_url,
    settings.supabase_anon_key,
)

# Service role client — bypasses RLS, for server-side operations only
supabase_admin: Client = create_client(
    settings.supabase_url,
    settings.supabase_service_role_key,
)
