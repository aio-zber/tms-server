"""
Pydantic schemas for conversation requests and responses.
Handles validation for conversation-related API endpoints.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
# UUID import removed - using str for ID types

from app.utils.datetime_utils import utc_now

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.models.conversation import ConversationType, ConversationRole


# ============================================================================
# Request Schemas
# ============================================================================

class ConversationCreate(BaseModel):
    """Schema for creating a new conversation."""

    type: ConversationType = Field(..., description="Conversation type: 'dm' or 'group'")
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Group name (required for groups)")
    avatar_url: Optional[str] = Field(None, max_length=500, description="Group avatar URL")
    member_ids: List[str] = Field(
        ...,
        min_items=1,
        max_items=100,
        description="List of TMS user IDs to add as members (EXCLUDING yourself - you are automatically added as creator/admin)"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str], info) -> Optional[str]:
        """Validate name is required for groups."""
        conversation_type = info.data.get("type")

        if conversation_type == ConversationType.GROUP and not v:
            raise ValueError("Group conversations must have a name")

        if v and len(v.strip()) == 0:
            raise ValueError("Name cannot be empty or whitespace only")

        return v.strip() if v else v

    @field_validator("member_ids")
    @classmethod
    def validate_member_ids(cls, v: List[str], info) -> List[str]:
        """Validate member count based on conversation type."""
        conversation_type = info.data.get("type")

        if conversation_type == ConversationType.DM and len(v) != 1:
            raise ValueError("DM conversations must have exactly 1 other member (besides creator)")

        if conversation_type == ConversationType.GROUP and len(v) < 1:
            raise ValueError("Group conversations must have at least 1 member (besides creator)")

        # Check for duplicates
        if len(v) != len(set(v)):
            raise ValueError("Duplicate member IDs are not allowed")

        return v

    class Config:
        json_schema_extra = {
            "example": {
                "type": "group",
                "name": "Team Discussion",
                "avatar_url": "https://example.com/avatar.jpg",
                "member_ids": ["123e4567-e89b-12d3-a456-426614174000"]
            }
        }


class ConversationUpdate(BaseModel):
    """Schema for updating a conversation."""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Updated group name")
    avatar_url: Optional[str] = Field(None, max_length=500, description="Updated avatar URL")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Ensure name is not empty if provided."""
        if v and len(v.strip()) == 0:
            raise ValueError("Name cannot be empty or whitespace only")
        return v.strip() if v else v

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Updated Team Name",
                "avatar_url": "https://example.com/new-avatar.jpg"
            }
        }


class ConversationMemberAdd(BaseModel):
    """Schema for adding members to a conversation."""

    user_ids: List[str] = Field(..., min_items=1, max_items=50, description="List of TMS user IDs to add as members")

    @field_validator("user_ids")
    @classmethod
    def validate_user_ids(cls, v: List[str]) -> List[str]:
        """Check for duplicate IDs."""
        if len(v) != len(set(v)):
            raise ValueError("Duplicate user IDs are not allowed")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "user_ids": ["cmgu6bzp70003qy10qnp5xksi"]
            }
        }


class ConversationSettingsUpdate(BaseModel):
    """Schema for updating conversation settings."""

    is_muted: Optional[bool] = Field(None, description="Mute conversation notifications")
    mute_until: Optional[datetime] = Field(None, description="Temporary mute until this time")

    @field_validator("mute_until")
    @classmethod
    def validate_mute_until(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Validate mute_until is in the future if is_muted is True."""
        is_muted = info.data.get("is_muted")

        if is_muted and v and v < utc_now():
            raise ValueError("mute_until must be in the future")

        if is_muted is False and v:
            raise ValueError("Cannot set mute_until when is_muted is False")

        return v

    class Config:
        json_schema_extra = {
            "example": {
                "is_muted": True,
                "mute_until": None
            }
        }


# ============================================================================
# Response Schemas
# ============================================================================

class ConversationMemberResponse(BaseModel):
    """Schema for conversation member response."""

    user_id: str = Field(serialization_alias="userId")
    role: ConversationRole
    joined_at: datetime = Field(serialization_alias="joinedAt")
    last_read_at: Optional[datetime] = Field(None, serialization_alias="lastReadAt")
    is_muted: bool = Field(serialization_alias="isMuted")
    mute_until: Optional[datetime] = Field(None, serialization_alias="muteUntil")

    # User info enriched from TMS
    user: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        ser_json_by_alias=True
    )


class ConversationResponse(BaseModel):
    """Schema for conversation response with full details."""

    id: str
    type: ConversationType
    name: Optional[str]
    display_name: Optional[str] = Field(None, serialization_alias="display_name")  # Computed: DM = other user's name, Group = group name
    avatar_url: Optional[str] = Field(None, serialization_alias="avatarUrl")
    created_by: Optional[str] = Field(None, serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: Optional[datetime] = Field(None, serialization_alias="updatedAt")

    # Related data
    members: List[ConversationMemberResponse] = Field(default_factory=list)
    member_count: Optional[int] = Field(None, serialization_alias="memberCount")
    unread_count: Optional[int] = Field(None, serialization_alias="unreadCount")
    last_message: Optional[Dict[str, Any]] = Field(None, serialization_alias="lastMessage")

    # Creator info enriched from TMS
    creator: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        ser_json_by_alias=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "type": "group",
                "name": "Team Discussion",
                "avatarUrl": "https://example.com/avatar.jpg",
                "createdBy": "123e4567-e89b-12d3-a456-426614174001",
                "createdAt": "2025-10-10T10:00:00Z",
                "updatedAt": "2025-10-10T12:00:00Z",
                "members": [],
                "memberCount": 5,
                "unreadCount": 3
            }
        }
    )


class ConversationListResponse(BaseModel):
    """Schema for paginated conversation list response."""

    data: List[ConversationResponse]
    pagination: Dict[str, Any] = Field(
        description="Pagination metadata with cursor and has_more"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "data": [],
                "pagination": {
                    "next_cursor": "123e4567-e89b-12d3-a456-426614174000",
                    "has_more": True,
                    "limit": 50
                }
            }
        }


class ConversationDeleteResponse(BaseModel):
    """Response for conversation deletion."""

    success: bool
    message: str
    deleted_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Conversation deleted successfully",
                "deleted_at": "2025-10-10T10:00:00Z"
            }
        }


class ConversationMemberUpdateResponse(BaseModel):
    """Response for member operations."""

    success: bool
    message: str
    affected_count: int

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Members added successfully",
                "affected_count": 3
            }
        }
