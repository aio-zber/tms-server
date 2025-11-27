"""
Notification schemas for API request/response validation.
Handles notification preferences and muted conversations.
"""
from datetime import datetime, time as Time
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


class NotificationPreferencesBase(BaseModel):
    """Base schema for notification preferences."""

    sound_enabled: bool = Field(
        default=True,
        description="Whether notification sounds are enabled"
    )
    sound_volume: int = Field(
        default=75,
        ge=0,
        le=100,
        description="Volume level for notification sounds (0-100)"
    )
    browser_notifications_enabled: bool = Field(
        default=False,
        description="Whether browser push notifications are enabled"
    )
    enable_message_notifications: bool = Field(
        default=True,
        description="Enable notifications for new messages"
    )
    enable_mention_notifications: bool = Field(
        default=True,
        description="Enable notifications when mentioned (@username)"
    )
    enable_reaction_notifications: bool = Field(
        default=True,
        description="Enable notifications for message reactions"
    )
    enable_member_activity_notifications: bool = Field(
        default=False,
        description="Enable notifications for member join/leave events"
    )
    dnd_enabled: bool = Field(
        default=False,
        description="Whether Do Not Disturb mode is enabled"
    )
    dnd_start: Optional[str] = Field(
        default=None,
        description="DND start time (HH:MM format, e.g., '22:00')"
    )
    dnd_end: Optional[str] = Field(
        default=None,
        description="DND end time (HH:MM format, e.g., '08:00')"
    )

    @field_validator('dnd_start', 'dnd_end')
    @classmethod
    def validate_time_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate time format is HH:MM."""
        if v is None:
            return v

        try:
            # Parse the time string to validate format
            Time.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError("Time must be in HH:MM format (e.g., '22:00')")

    model_config = ConfigDict(from_attributes=True)


class NotificationPreferencesUpdate(BaseModel):
    """Schema for updating notification preferences (all fields optional)."""

    sound_enabled: Optional[bool] = None
    sound_volume: Optional[int] = Field(None, ge=0, le=100)
    browser_notifications_enabled: Optional[bool] = None
    enable_message_notifications: Optional[bool] = None
    enable_mention_notifications: Optional[bool] = None
    enable_reaction_notifications: Optional[bool] = None
    enable_member_activity_notifications: Optional[bool] = None
    dnd_enabled: Optional[bool] = None
    dnd_start: Optional[str] = None
    dnd_end: Optional[str] = None

    @field_validator('dnd_start', 'dnd_end')
    @classmethod
    def validate_time_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate time format is HH:MM."""
        if v is None:
            return v

        try:
            Time.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError("Time must be in HH:MM format (e.g., '22:00')")


class NotificationPreferencesResponse(NotificationPreferencesBase):
    """Schema for notification preferences response."""

    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MutedConversationBase(BaseModel):
    """Base schema for muted conversation."""

    conversation_id: str = Field(
        description="ID of the conversation to mute"
    )


class MutedConversationResponse(BaseModel):
    """Schema for muted conversation response."""

    id: str
    user_id: str
    conversation_id: str
    muted_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MutedConversationListResponse(BaseModel):
    """Schema for list of muted conversations."""

    muted_conversations: list[MutedConversationResponse]
    total: int
