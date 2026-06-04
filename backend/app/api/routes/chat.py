from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from uuid import UUID
from typing import Optional
import json
import asyncio

from app.core.auth import require_auth
from app.services.character_service import CharacterService
from app.services.chat_service import ChatService
from app.services.prompt_builder import build_system_prompt, build_messages
from app.services.memory_service import MemoryService
from app.services.extraction_job import run_extraction
from app.adapters.claude_adapter import get_adapter

router = APIRouter()


# ─── Request schema ───────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    model_override: Optional[str] = None


# ─── Chat endpoint ────────────────────────────────────────────────────────────
@router.post("/{character_id}")
async def chat(
    character_id: UUID,
    body: ChatRequest,
):
    # ── 1. Load character ──────────────────────────────────────────────────
    character = CharacterService.get_by_id(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    # ── 2. Get or create session ───────────────────────────────────────────
    session_id = ChatService.get_or_create_session(character_id, body.session_id)

    # ── 3. Fetch recent conversation history ──────────────────────────────
    recent_messages = ChatService.get_recent_messages(character_id, session_id)

    # ── 4. Retrieve relevant memories ─────────────────────────────────────
    injected_memories = []
    try:
        injected_memories = MemoryService.retrieve_relevant(
            character_id=character_id,
            query_text=body.message,
        )
    except Exception:
        pass  # Memory retrieval failure should not block chat

    # ── 5. Build prompt ────────────────────────────────────────────────────
    system_prompt = build_system_prompt(
        name=character["name"],
        base_card=character["base_card"],
        current_state=character["current_state"],
        injected_memories=injected_memories if injected_memories else None,
    )

    messages = build_messages(
        recent_conversations=recent_messages,
        new_user_message=body.message,
    )

    # ── 6. Select model ────────────────────────────────────────────────────
    model = (
        body.model_override
        or character.get("preferred_model")
        or "claude-sonnet-4-6"
    )
    adapter = get_adapter(model)

    # ── 7. Stream response ─────────────────────────────────────────────────
    async def generate():
        full_response = ""
        is_first_chunk = True

        try:
            async for chunk in adapter.chat(
                messages=messages,
                system_prompt=system_prompt,
            ):
                full_response += chunk

                if is_first_chunk:
                    yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
                    is_first_chunk = False

                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"

            # ── 8. Check for refusal ───────────────────────────────────────
            if adapter.is_refusal(full_response):
                yield f"data: {json.dumps({'type': 'error', 'code': 'CONTENT_FILTERED', 'message': 'Character could not continue — edit your message and try again.'})}\n\n"
                return

            # ── 9. Save both messages ──────────────────────────────────────
            token_estimate = adapter.count_tokens(body.message + full_response)

            ChatService.save_message(
                character_id=character_id,
                session_id=session_id,
                role="user",
                content=body.message,
                model_used=model,
                tokens_used=0,
            )
            ChatService.save_message(
                character_id=character_id,
                session_id=session_id,
                role="assistant",
                content=full_response,
                model_used=model,
                tokens_used=token_estimate,
            )

            CharacterService.increment_messages(character_id, count=2)

            # ── 10. Trigger memory extraction if threshold reached ─────────
            should_extract = ChatService.should_extract_memories(character_id)
            if should_extract:
                # Run in background — don't block the response
                asyncio.create_task(run_extraction(character_id))

            yield f"data: {json.dumps({'type': 'done', 'should_extract': should_extract})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'code': 'STREAM_ERROR', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ─── Manual memory extraction trigger ────────────────────────────────────────
@router.post("/{character_id}/extract")
async def trigger_extraction(character_id: UUID):
    """Manually trigger memory extraction for a character."""
    character = CharacterService.get_by_id(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    result = await run_extraction(character_id)
    return result


# ─── Get conversation history ─────────────────────────────────────────────────
@router.get("/{character_id}/history")
async def get_history(
    character_id: UUID,
    session_id: str,
):
    character = CharacterService.get_by_id(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    messages = ChatService.get_recent_messages(
        character_id=character_id,
        session_id=session_id,
        limit=100,
    )
    return {"session_id": session_id, "messages": messages}
