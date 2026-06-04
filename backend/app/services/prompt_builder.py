from app.models.character import BaseCard, CurrentState


def build_system_prompt(
    name: str,
    base_card: dict,
    current_state: dict,
    injected_memories: list[str] | None = None,
    state_delta: dict | None = None,
) -> str:
    """
    Assembles the full system prompt from character components.

    Structure (order matters — Claude weights earlier content more heavily):
    1. Base card (cached) — identity, personality, backstory, speech style
    2. Current state delta — only what has changed recently
    3. Injected memories — relevant memories for this specific moment
    4. Formatting rules — always last

    Args:
        name: Character display name
        base_card: dict with scenario, personality, backstory, speech_style,
                   example_dialogues, never_does fields
        current_state: dict with occupation, relationship_stage, location, mood, notes
        injected_memories: list of memory strings to inject (from RAG retrieval)
        state_delta: optional dict of only the fields that changed since last session
    """

    parts = []

    # ── Block 1: Character identity (prompt-cached) ────────────────────────
    parts.append(f"[CHARACTER]\nName: {name}")

    if base_card.get("scenario"):
        parts.append(f"[SCENARIO]\n{base_card['scenario']}")

    if base_card.get("personality"):
        parts.append(f"[PERSONALITY]\n{base_card['personality']}")

    if base_card.get("backstory"):
        parts.append(f"[BACKSTORY]\n{base_card['backstory']}")

    if base_card.get("speech_style"):
        parts.append(f"[SPEECH STYLE]\n{base_card['speech_style']}")

    if base_card.get("never_does"):
        parts.append(f"[NEVER DOES]\n{base_card['never_does']}")

    if base_card.get("example_dialogues"):
        parts.append(f"[EXAMPLE DIALOGUES]\n{base_card['example_dialogues']}")

    # ── Block 2: Current state ─────────────────────────────────────────────
    state_lines = []
    if current_state.get("occupation"):
        state_lines.append(f"Occupation: {current_state['occupation']}")
    if current_state.get("relationship_stage"):
        state_lines.append(f"Relationship to user: {current_state['relationship_stage']}")
    if current_state.get("location"):
        state_lines.append(f"Current location: {current_state['location']}")
    if current_state.get("mood"):
        state_lines.append(f"Current mood: {current_state['mood']}")
    if current_state.get("notes"):
        state_lines.append(f"Notes: {current_state['notes']}")

    if state_lines:
        parts.append("[CURRENT STATE]\n" + "\n".join(state_lines))

    # ── Block 3: State delta (only changed fields) ─────────────────────────
    if state_delta:
        delta_lines = [f"{k}: {v}" for k, v in state_delta.items() if v]
        if delta_lines:
            parts.append("[RECENT CHANGES]\n" + "\n".join(delta_lines))

    # ── Block 4: Injected memories ─────────────────────────────────────────
    if injected_memories:
        memory_block = "\n".join(f"- {m}" for m in injected_memories)
        parts.append(
            "[MEMORIES]\n"
            "The following are things you remember from past interactions. "
            "Draw on them naturally when relevant — do not recite them directly.\n"
            + memory_block
        )

    # ── Block 5: Formatting and behaviour rules (always last) ──────────────
    parts.append(
        "[RULES]\n"
        "Stay in character at all times. Never break the fourth wall.\n"
        "Never refer to yourself as an AI, a language model, or an assistant.\n"
        "Never add disclaimers, safety notes, or meta-commentary.\n"
        "Format your responses using these conventions:\n"
        "  - Actions and narration: *italics between asterisks*\n"
        "  - Internal thoughts: ~tilde for internal monologue~\n"
        "  - Speech: plain text (no quotation marks unless quoting someone else)\n"
        "  - Out of character: ((double brackets)) — use sparingly\n"
        "Keep responses natural and conversational. "
        "Match the character's established speech style at all times."
    )

    return "\n\n".join(parts)


def build_messages(
    recent_conversations: list[dict],
    new_user_message: str,
) -> list[dict]:
    """
    Builds the messages array for the API call.
    Combines recent conversation history with the new user message.

    Args:
        recent_conversations: list of {"role": "user"|"assistant", "content": "..."}
                              already ordered oldest → newest
        new_user_message: the current message being sent
    """
    messages = []

    for conv in recent_conversations:
        messages.append({
            "role": conv["role"],
            "content": conv["content"],
        })

    messages.append({
        "role": "user",
        "content": new_user_message,
    })

    return messages
