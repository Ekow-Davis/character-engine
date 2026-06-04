import json
import anthropic
from uuid import UUID
from app.core.database import supabase_admin
from app.core.config import settings
from app.services.memory_service import MemoryService

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

EXTRACTION_PROMPT = """You are a memory archivist for an AI character system.

Analyze the following roleplay conversation and extract meaningful information to store as long-term memories.

Extract:
- Key events that occurred (with approximate in-world timing if mentioned)
- Facts learned about either party (the character or the user)
- Relationship developments or changes
- Emotional moments of significance
- Any character state changes (job, relationship status, location, major life events)

For each memory, assign an importance score from 1-10:
- 8-10: Major events, first meetings, significant emotional moments, milestones
- 5-7: Shared activities, relationship developments, meaningful exchanges
- 1-4: Casual conversation, minor details, filler scenes

Also detect any state mutations — changes to the character's factual situation that should update their profile.

Return ONLY valid JSON in this exact format, no other text:
{
  "memories": [
    {
      "content": "Brief but specific memory description in past tense, as the character would recall it",
      "importance": 7,
      "type": "event|fact|relationship|emotional|state_change"
    }
  ],
  "state_mutations": {
    "occupation": "new value or null if unchanged",
    "relationship_stage": "new value or null if unchanged",
    "location": "new value or null if unchanged",
    "mood": "new value or null if unchanged",
    "notes": "new value or null if unchanged"
  }
}

If there are no meaningful memories to extract, return an empty memories array.
Only include state_mutations fields that actually changed — set unchanged fields to null.
"""


async def run_extraction(character_id: UUID) -> dict:
    """
    Main extraction job. Reads unprocessed conversations for a character,
    sends them to Claude, extracts memories, saves them, and detects state changes.

    Returns a summary of what was extracted.
    """

    # ── 1. Fetch unprocessed conversations ────────────────────────────────
    response = supabase_admin.table("conversations").select(
        "id, role, content, created_at"
    ).eq(
        "character_id", str(character_id)
    ).eq(
        "processed", False
    ).order("created_at").execute()

    conversations = response.data

    if not conversations:
        return {"extracted": 0, "state_mutations": {}}

    # ── 2. Format as readable dialogue ────────────────────────────────────
    dialogue_lines = []
    conversation_ids = []

    for msg in conversations:
        speaker = "User" if msg["role"] == "user" else "Character"
        dialogue_lines.append(f"{speaker}: {msg['content']}")
        conversation_ids.append(msg["id"])

    dialogue_text = "\n".join(dialogue_lines)

    # ── 3. Send to Claude for extraction ──────────────────────────────────
    try:
        result = _client.messages.create(
            model="claude-haiku-4-5-20251001",  # Use Haiku for cost efficiency
            max_tokens=1500,
            system=EXTRACTION_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Extract memories from this conversation:\n\n{dialogue_text}"
            }]
        )

        raw = result.content[0].text.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        extracted = json.loads(raw)

    except (json.JSONDecodeError, Exception) as e:
        # Don't fail silently — mark conversations processed anyway to avoid reprocessing
        supabase_admin.table("conversations").update({
            "processed": True
        }).in_("id", conversation_ids).execute()
        return {"extracted": 0, "error": str(e), "state_mutations": {}}

    # ── 4. Save extracted memories ────────────────────────────────────────
    memories_saved = 0
    for memory in extracted.get("memories", []):
        if not memory.get("content"):
            continue
        MemoryService.save_memory(
            character_id=character_id,
            content=memory["content"],
            importance=memory.get("importance", 5),
            source_ids=conversation_ids,
        )
        memories_saved += 1

    # ── 5. Apply state mutations ──────────────────────────────────────────
    mutations = extracted.get("state_mutations", {})
    applied_mutations = {}

    if mutations:
        # Fetch current state
        char_response = supabase_admin.table("characters").select(
            "current_state"
        ).eq("id", str(character_id)).single().execute()

        current_state = char_response.data.get("current_state", {})
        new_state = dict(current_state)

        for field, new_value in mutations.items():
            if new_value and new_value != current_state.get(field):
                old_value = current_state.get(field, "")
                new_state[field] = new_value
                applied_mutations[field] = {"old": old_value, "new": new_value}

                # Log the state change
                supabase_admin.table("character_state_log").insert({
                    "character_id": str(character_id),
                    "field": field,
                    "old_value": old_value,
                    "new_value": new_value,
                    "triggered_by": conversation_ids[-1] if conversation_ids else None,
                }).execute()

        if applied_mutations:
            supabase_admin.table("characters").update({
                "current_state": new_state
            }).eq("id", str(character_id)).execute()

    # ── 6. Mark conversations as processed ────────────────────────────────
    supabase_admin.table("conversations").update({
        "processed": True
    }).in_("id", conversation_ids).execute()

    return {
        "extracted": memories_saved,
        "state_mutations": applied_mutations,
        "conversations_processed": len(conversation_ids),
    }


async def run_compression(character_id: UUID) -> dict:
    """
    Compression job — finds eligible memories and compresses them.
    Eligible: not locked, active tier, not accessed within compression window.
    """
    from datetime import datetime, timezone, timedelta

    # Get compression config
    config_response = supabase_admin.table("config").select("key, value").in_(
        "key", ["compression_low_days", "compression_mid_days"]
    ).execute()
    config = {row["key"]: int(row["value"]) for row in config_response.data}
    low_days = config.get("compression_low_days", 7)
    mid_days = config.get("compression_mid_days", 30)

    now = datetime.now(timezone.utc)
    compressed_count = 0

    # Fetch candidates — low importance
    low_cutoff = (now - timedelta(days=low_days)).isoformat()
    mid_cutoff = (now - timedelta(days=mid_days)).isoformat()

    for importance_range, cutoff in [
        ((1, 4), low_cutoff),
        ((5, 7), mid_cutoff),
    ]:
        response = supabase_admin.table("memories").select(
            "id, content"
        ).eq(
            "character_id", str(character_id)
        ).eq(
            "tier", "active"
        ).eq(
            "locked", False
        ).gte(
            "importance", importance_range[0]
        ).lte(
            "importance", importance_range[1]
        ).lt(
            "last_accessed", cutoff
        ).execute()

        for memory in response.data:
            try:
                result = _client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=200,
                    messages=[{
                        "role": "user",
                        "content": (
                            "Compress this memory to its essential facts only. "
                            "Preserve: who, what, emotional tone, any established facts. "
                            "Remove: dialogue, description, scene detail. "
                            "Return only the compressed text, nothing else.\n\n"
                            f"Memory: {memory['content']}"
                        )
                    }]
                )
                compressed = result.content[0].text.strip()
                MemoryService.compress(memory["id"], compressed)
                compressed_count += 1
            except Exception:
                continue

    return {"compressed": compressed_count}
