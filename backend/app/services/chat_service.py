from uuid import UUID, uuid4
from app.core.database import supabase_admin
from app.core.config import settings


class ChatService:

    @staticmethod
    def get_or_create_session(character_id: UUID, session_id: str | None) -> str:
        """
        Returns existing session_id or creates a new one.
        A new session starts if no session_id is provided.
        """
        if session_id:
            return session_id
        return str(uuid4())

    @staticmethod
    def get_recent_messages(
        character_id: UUID,
        session_id: str,
        limit: int | None = None,
    ) -> list[dict]:
        """
        Fetches recent messages for a session, ordered oldest → newest.
        Limit defaults to the config value (recent_messages_limit).
        """
        if limit is None:
            config = supabase_admin.table("config").select("value").eq(
                "key", "recent_messages_limit"
            ).single().execute()
            limit = int(config.data["value"]) if config.data else 15

        response = supabase_admin.table("conversations").select(
            "role, content"
        ).eq(
            "character_id", str(character_id)
        ).eq(
            "session_id", session_id
        ).order(
            "created_at", desc=True
        ).limit(limit).execute()

        # Reverse so oldest is first (correct order for the API)
        messages = list(reversed(response.data))
        return messages

    @staticmethod
    def save_message(
        character_id: UUID,
        session_id: str,
        role: str,
        content: str,
        model_used: str | None = None,
        tokens_used: int = 0,
    ) -> dict:
        """Persist a single message to the conversations table."""
        payload = {
            "character_id": str(character_id),
            "session_id": session_id,
            "role": role,
            "content": content,
            "model_used": model_used,
            "tokens_used": tokens_used,
            "processed": False,
        }
        response = supabase_admin.table("conversations").insert(payload).execute()
        return response.data[0]

    @staticmethod
    def get_unprocessed_count(character_id: UUID) -> int:
        """
        Returns the count of unprocessed messages for a character.
        Used to check if the memory extraction threshold has been reached.
        """
        response = supabase_admin.table("conversations").select(
            "id", count="exact"
        ).eq(
            "character_id", str(character_id)
        ).eq(
            "processed", False
        ).execute()
        return response.count or 0

    @staticmethod
    def should_extract_memories(character_id: UUID) -> bool:
        """
        Returns True if the unprocessed message count has hit the threshold.
        """
        config = supabase_admin.table("config").select("value").eq(
            "key", "extraction_threshold"
        ).single().execute()
        threshold = int(config.data["value"]) if config.data else 20

        return ChatService.get_unprocessed_count(character_id) >= threshold
