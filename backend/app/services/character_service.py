from uuid import UUID
from typing import Optional
from app.core.database import supabase_admin
from app.models.character import CharacterCreate, CharacterUpdate


class CharacterService:

    @staticmethod
    def _table():
        return supabase_admin.table("characters")

    # ─── Create ───────────────────────────────────────────────────────────────
    @staticmethod
    def create(data: CharacterCreate) -> dict:
        payload = {
            "name": data.name,
            "tagline": data.tagline,
            "base_card": data.base_card.model_dump(),
            "current_state": data.current_state.model_dump(),
            "display_profile": data.display_profile.model_dump(),
            "preferred_model": data.preferred_model,
            "is_demo": data.is_demo,
        }
        response = supabase_admin.table("characters").insert(payload).execute()
        return response.data[0]

    # ─── Get all ──────────────────────────────────────────────────────────────
    @staticmethod
    def get_all(demo_only: bool = False) -> list[dict]:
        query = supabase_admin.table("characters").select(
            "id, name, tagline, display_profile, preferred_model, "
            "is_demo, total_chats, total_messages, updated_at"
        ).order("updated_at", desc=True)

        if demo_only:
            query = query.eq("is_demo", True)
        else:
            query = query.eq("is_demo", False)

        response = query.execute()
        return response.data

    # ─── Get one ──────────────────────────────────────────────────────────────
    @staticmethod
    def get_by_id(character_id: UUID) -> Optional[dict]:
        response = supabase_admin.table("characters").select("*").eq(
            "id", str(character_id)
        ).single().execute()
        return response.data

    # ─── Update ───────────────────────────────────────────────────────────────
    @staticmethod
    def update(character_id: UUID, data: CharacterUpdate) -> Optional[dict]:
        # Only include fields that were actually provided
        payload = {}

        if data.name is not None:
            payload["name"] = data.name
        if data.tagline is not None:
            payload["tagline"] = data.tagline
        if data.base_card is not None:
            payload["base_card"] = data.base_card.model_dump()
        if data.current_state is not None:
            payload["current_state"] = data.current_state.model_dump()
        if data.display_profile is not None:
            payload["display_profile"] = data.display_profile.model_dump()
        if data.preferred_model is not None:
            payload["preferred_model"] = data.preferred_model

        if not payload:
            # Nothing to update — just return current record
            return CharacterService.get_by_id(character_id)

        response = supabase_admin.table("characters").update(payload).eq(
            "id", str(character_id)
        ).execute()

        return response.data[0] if response.data else None

    # ─── Delete ───────────────────────────────────────────────────────────────
    @staticmethod
    def delete(character_id: UUID) -> bool:
        response = supabase_admin.table("characters").delete().eq(
            "id", str(character_id)
        ).execute()
        return len(response.data) > 0

    # ─── Increment counters ───────────────────────────────────────────────────
    @staticmethod
    def increment_chats(character_id: UUID) -> None:
        supabase_admin.rpc("increment_character_chats", {
            "p_character_id": str(character_id)
        }).execute()

    @staticmethod
    def increment_messages(character_id: UUID, count: int = 1) -> None:
        supabase_admin.rpc("increment_character_messages", {
            "p_character_id": str(character_id),
            "p_count": count
        }).execute()
