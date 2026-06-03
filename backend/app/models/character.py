from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


# ─── Base Card ────────────────────────────────────────────────────────────────
class BaseCard(BaseModel):
    scenario: str = ""
    personality: str = ""
    initial_message: str = ""
    example_dialogues: str = ""
    speech_style: str = ""
    backstory: str = ""
    never_does: str = ""


# ─── Current State ────────────────────────────────────────────────────────────
class CurrentState(BaseModel):
    occupation: str = ""
    relationship_stage: str = ""
    location: str = ""
    mood: str = ""
    notes: str = ""


# ─── Display Profile ──────────────────────────────────────────────────────────
class DisplayProfile(BaseModel):
    avatar_url: Optional[str] = None
    banner_url: Optional[str] = None
    accent_colour: str = "#7C5CBF"
    html_bio: str = ""


# ─── Request Schemas ──────────────────────────────────────────────────────────
class CharacterCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    tagline: Optional[str] = Field(None, max_length=200)
    base_card: BaseCard = Field(default_factory=BaseCard)
    current_state: CurrentState = Field(default_factory=CurrentState)
    display_profile: DisplayProfile = Field(default_factory=DisplayProfile)
    preferred_model: str = "claude-sonnet-4-6"
    is_demo: bool = False


class CharacterUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    tagline: Optional[str] = Field(None, max_length=200)
    base_card: Optional[BaseCard] = None
    current_state: Optional[CurrentState] = None
    display_profile: Optional[DisplayProfile] = None
    preferred_model: Optional[str] = None


# ─── Response Schemas ─────────────────────────────────────────────────────────
class CharacterResponse(BaseModel):
    id: UUID
    name: str
    tagline: Optional[str]
    base_card: BaseCard
    current_state: CurrentState
    display_profile: DisplayProfile
    preferred_model: str
    is_demo: bool
    total_chats: int
    total_messages: int
    created_at: datetime
    updated_at: datetime


class CharacterSummary(BaseModel):
    """Lightweight version for the character select grid."""
    id: UUID
    name: str
    tagline: Optional[str]
    display_profile: DisplayProfile
    preferred_model: str
    is_demo: bool
    total_chats: int
    total_messages: int
    updated_at: datetime
