from uuid import UUID
from datetime import datetime, timezone
from app.core.database import supabase_admin
from app.services.embedding_service import embed_text


class MemoryService:

    # ─── Store a memory ───────────────────────────────────────────────────────
    @staticmethod
    def save_memory(
        character_id: UUID,
        content: str,
        importance: int = 5,
        source_ids: list[str] | None = None,
        tier: str = "active",
    ) -> dict:
        """
        Save a new memory entry with its embedding.
        Called by the extraction job after processing conversations.
        """
        embedding = embed_text(content)

        payload = {
            "character_id": str(character_id),
            "content": content,
            "embedding": embedding,
            "importance": max(1, min(10, importance)),
            "tier": tier,
            "locked": False,
            "retrieval_count": 0,
            "source_ids": source_ids or [],
        }

        response = supabase_admin.table("memories").insert(payload).execute()
        return response.data[0]

    # ─── Retrieve relevant memories ───────────────────────────────────────────
    @staticmethod
    def retrieve_relevant(
        character_id: UUID,
        query_text: str,
        top_k: int = 6,
    ) -> list[str]:
        """
        Find the most relevant memories for a given query using pgvector.

        Steps:
        1. Embed the query
        2. Run cosine similarity search via search_memories()
        3. Re-rank by weighted score: similarity*0.6 + importance*0.3 + recency*0.1
        4. Return top_k memory strings for prompt injection
        """
        # Get config weights
        config_response = supabase_admin.table("config").select(
            "key, value"
        ).in_("key", [
            "retrieval_similarity_weight",
            "retrieval_importance_weight",
            "retrieval_recency_weight",
            "memory_injection_limit",
        ]).execute()

        config = {row["key"]: float(row["value"]) for row in config_response.data}
        sim_weight = config.get("retrieval_similarity_weight", 0.6)
        imp_weight = config.get("retrieval_importance_weight", 0.3)
        rec_weight = config.get("retrieval_recency_weight", 0.1)
        limit = int(config.get("memory_injection_limit", top_k))

        # Embed the query
        query_embedding = embed_text(query_text)

        # Run vector search via our SQL function
        response = supabase_admin.rpc("search_memories", {
            "p_character_id": str(character_id),
            "p_embedding": query_embedding,
            "p_limit": 10,  # fetch top 10, re-rank down to limit
        }).execute()

        if not response.data:
            return []

        # Re-rank with weighted score
        now = datetime.now(timezone.utc)
        scored = []

        for row in response.data:
            similarity = float(row["similarity"])
            importance_score = row["importance"] / 10.0

            # Recency score: 1.0 if accessed today, decays over 90 days
            last_accessed = row["last_accessed"]
            if isinstance(last_accessed, str):
                last_accessed = datetime.fromisoformat(
                    last_accessed.replace("Z", "+00:00")
                )
            days_since = (now - last_accessed).days
            recency_score = max(0.0, 1.0 - (days_since / 90.0))

            weighted = (
                similarity * sim_weight
                + importance_score * imp_weight
                + recency_score * rec_weight
            )
            scored.append((weighted, row))

        # Sort descending, take top limit
        scored.sort(key=lambda x: x[0], reverse=True)
        top_memories = [row for _, row in scored[:limit]]

        # Update retrieval_count and last_accessed for selected memories
        selected_ids = [row["id"] for row in top_memories]
        if selected_ids:
            supabase_admin.table("memories").update({
                "retrieval_count": supabase_admin.table("memories").select(
                    "retrieval_count"
                ),
                "last_accessed": datetime.now(timezone.utc).isoformat(),
            })
            # Update each individually (Supabase doesn't support bulk increment easily)
            for memory_id in selected_ids:
                supabase_admin.rpc("increment_memory_retrieval", {
                    "p_memory_id": memory_id
                }).execute()

        return [row["content"] for row in top_memories]

    # ─── Get all memories for a character ─────────────────────────────────────
    @staticmethod
    def get_all(
        character_id: UUID,
        tier: str | None = None,
        locked_only: bool = False,
    ) -> list[dict]:
        query = supabase_admin.table("memories").select(
            "id, content, importance, tier, locked, retrieval_count, created_at, last_accessed"
        ).eq("character_id", str(character_id)).order("created_at", desc=True)

        if tier:
            query = query.eq("tier", tier)
        if locked_only:
            query = query.eq("locked", True)

        return query.execute().data

    # ─── Lock / unlock a memory ───────────────────────────────────────────────
    @staticmethod
    def set_lock(memory_id: UUID, locked: bool) -> dict:
        response = supabase_admin.table("memories").update({
            "locked": locked
        }).eq("id", str(memory_id)).execute()
        return response.data[0] if response.data else {}

    # ─── Update memory content ────────────────────────────────────────────────
    @staticmethod
    def update_content(memory_id: UUID, content: str) -> dict:
        """Update memory text and regenerate its embedding."""
        new_embedding = embed_text(content)
        response = supabase_admin.table("memories").update({
            "content": content,
            "embedding": new_embedding,
        }).eq("id", str(memory_id)).execute()
        return response.data[0] if response.data else {}

    # ─── Delete a memory (soft delete via archive) ────────────────────────────
    @staticmethod
    def delete(memory_id: UUID) -> bool:
        response = supabase_admin.table("memories").delete().eq(
            "id", str(memory_id)
        ).execute()
        return len(response.data) > 0

    # ─── Compress a memory ────────────────────────────────────────────────────
    @staticmethod
    def compress(memory_id: UUID, compressed_content: str) -> dict:
        """
        Replace memory content with compressed version and move to compressed tier.
        Original content is gone — caller should archive it first if needed.
        """
        new_embedding = embed_text(compressed_content)
        response = supabase_admin.table("memories").update({
            "content": compressed_content,
            "embedding": new_embedding,
            "tier": "compressed",
        }).eq("id", str(memory_id)).execute()
        return response.data[0] if response.data else {}
