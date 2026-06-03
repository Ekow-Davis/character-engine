from fastapi import APIRouter, HTTPException, Query
from uuid import UUID
from app.models.character import (
    CharacterCreate,
    CharacterUpdate,
    CharacterResponse,
    CharacterSummary,
)
from app.services.character_service import CharacterService

router = APIRouter()


# ─── List characters ──────────────────────────────────────────────────────────
@router.get("", response_model=list[CharacterSummary])
async def list_characters(
    demo: bool = Query(False, description="Return demo characters only")
):
    """Get all characters for the character select grid."""
    return CharacterService.get_all(demo_only=demo)


# ─── Get one character ────────────────────────────────────────────────────────
@router.get("/{character_id}", response_model=CharacterResponse)
async def get_character(character_id: UUID):
    """Get full character details for the profile page."""
    character = CharacterService.get_by_id(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return character


# ─── Create character ─────────────────────────────────────────────────────────
@router.post("", response_model=CharacterResponse, status_code=201)
async def create_character(data: CharacterCreate):
    """Create a new character."""
    try:
        character = CharacterService.create(data)
        return character
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Update character ─────────────────────────────────────────────────────────
@router.put("/{character_id}", response_model=CharacterResponse)
async def update_character(character_id: UUID, data: CharacterUpdate):
    """Update a character's card, state, or display profile."""
    existing = CharacterService.get_by_id(character_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Character not found")

    updated = CharacterService.update(character_id, data)
    if not updated:
        raise HTTPException(status_code=500, detail="Update failed")
    return updated


# ─── Delete character ─────────────────────────────────────────────────────────
@router.delete("/{character_id}", status_code=204)
async def delete_character(character_id: UUID):
    """Delete a character and all associated data."""
    existing = CharacterService.get_by_id(character_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Character not found")

    deleted = CharacterService.delete(character_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Delete failed")
