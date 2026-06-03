-- ─────────────────────────────────────────────────────────────────────────────
-- Character Engine — Counter Functions
-- Run this in Supabase SQL Editor
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION increment_character_chats(p_character_id UUID)
RETURNS VOID
LANGUAGE SQL
AS $$
    UPDATE characters
    SET total_chats = total_chats + 1
    WHERE id = p_character_id;
$$;

CREATE OR REPLACE FUNCTION increment_character_messages(p_character_id UUID, p_count INT DEFAULT 1)
RETURNS VOID
LANGUAGE SQL
AS $$
    UPDATE characters
    SET total_messages = total_messages + p_count
    WHERE id = p_character_id;
$$;
