"""
Pydantic schemas for message requests and responses.
Handles validation for message-related API endpoints.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
# UUID import removed - using str for ID types

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.models.message import MessageType, MessageStatusType


def to_camel(string: str) -> str:
    """Convert snake_case to camelCase."""
    components = string.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


# ============================================================================
# Request Schemas
# ============================================================================

class MessageCreate(BaseModel):
    """Schema for creating a new message."""

    conversation_id: str = Field(..., description="Conversation ID")
    content: Optional[str] = Field(None, max_length=10000, description="Message text content")
    type: MessageType = Field(default=MessageType.TEXT, description="Message type")
    metadata_json: Dict[str, Any] = Field(default_factory=dict, description="Message metadata")
    reply_to_id: Optional[str] = Field(None, description="ID of message being replied to")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: Optional[str], info) -> Optional[str]:
        """Validate content based on message type."""
        message_type = info.data.get("type")

        if message_type == MessageType.TEXT and not v:
            raise ValueError("Text messages must have content")

        if v and len(v.strip()) == 0:
            raise ValueError("Content cannot be empty or whitespace only")

        return v

    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
                "content": "Hello, how are you?",
                "type": "text",
                "metadata_json": {},
                "reply_to_id": None
            }
        }


class MessageUpdate(BaseModel):
    """Schema for updating a message."""

    content: str = Field(..., min_length=1, max_length=10000, description="Updated message content")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Ensure content is not empty or whitespace."""
        if len(v.strip()) == 0:
            raise ValueError("Content cannot be empty or whitespace only")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "content": "Updated message content"
            }
        }


class MessageReactionCreate(BaseModel):
    """Schema for adding a reaction to a message."""

    emoji: str = Field(..., min_length=1, max_length=10, description="Emoji reaction")

    @field_validator("emoji")
    @classmethod
    def validate_emoji(cls, v: str) -> str:
        """Basic emoji validation."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Emoji cannot be empty")
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {
                "emoji": "👍"
            }
        }


class MessageMarkReadRequest(BaseModel):
    """Schema for marking messages as read."""

    message_ids: List[str] = Field(..., min_items=1, max_items=100, description="List of message IDs to mark as read")
    conversation_id: str = Field(..., description="Conversation ID")

    class Config:
        json_schema_extra = {
            "example": {
                "message_ids": ["123e4567-e89b-12d3-a456-426614174000"],
                "conversation_id": "123e4567-e89b-12d3-a456-426614174001"
            }
        }


class MessageSearchRequest(BaseModel):
    """Schema for searching messages."""

    query: str = Field(..., min_length=1, max_length=200, description="Search query")
    conversation_id: Optional[str] = Field(None, description="Filter by conversation")
    sender_id: Optional[str] = Field(None, description="Filter by sender")
    message_type: Optional[MessageType] = Field(None, description="Filter by message type")
    start_date: Optional[datetime] = Field(None, description="Filter messages after this date")
    end_date: Optional[datetime] = Field(None, description="Filter messages before this date")
    limit: int = Field(default=50, ge=1, le=100, description="Number of results")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "meeting",
                "conversation_id": None,
                "limit": 50
            }
        }


# ============================================================================
# Response Schemas
# ============================================================================

class MessageReactionResponse(BaseModel):
    """Schema for message reaction response."""

    id: str
    message_id: str = Field(serialization_alias="messageId")
    user_id: str = Field(serialization_alias="userId")
    emoji: str
    created_at: datetime = Field(serialization_alias="createdAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class MessageStatusResponse(BaseModel):
    """Schema for message status response."""

    message_id: str = Field(serialization_alias="messageId")
    user_id: str = Field(serialization_alias="userId")
    status: MessageStatusType
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class UserBasicInfo(BaseModel):
    """Basic user information for message responses."""

    id: str
    tms_user_id: str = Field(serialization_alias="tmsUserId")
    # Additional user fields will be fetched from TMS and merged

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class MessageResponse(BaseModel):
    """Schema for message response with full details."""

    id: str
    conversation_id: str = Field(serialization_alias="conversationId")
    sender_id: str = Field(serialization_alias="senderId")
    content: Optional[str]
    type: MessageType
    metadata_json: Dict[str, Any] = Field(default_factory=dict, serialization_alias="metadata")
    reply_to_id: Optional[str] = Field(None, serialization_alias="replyToId")
    is_edited: bool = Field(serialization_alias="isEdited")
    sequence_number: int = Field(..., serialization_alias="sequenceNumber", description="Monotonically increasing sequence number per conversation")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: Optional[datetime] = Field(None, serialization_alias="updatedAt")
    deleted_at: Optional[datetime] = Field(None, serialization_alias="deletedAt")

    # Related data (optional, loaded based on request)
    sender: Optional[Dict[str, Any]] = None
    reactions: List[MessageReactionResponse] = Field(default_factory=list)
    statuses: List[MessageStatusResponse] = Field(default_factory=list)
    reply_to: Optional["MessageResponse"] = Field(None, serialization_alias="replyTo")
    poll: Optional[Dict[str, Any]] = Field(None, description="Poll data if message type is 'poll'")

    # Computed aggregated status field (Telegram/Messenger pattern)
    # This is computed by the service layer and represents the overall message status
    status: Optional[str] = Field(None, description="Aggregated message status: sent, delivered, or read")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        ser_json_by_alias=True,  # Serialize using aliases (camelCase for frontend)
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "conversationId": "123e4567-e89b-12d3-a456-426614174001",
                "senderId": "123e4567-e89b-12d3-a456-426614174002",
                "content": "Hello, how are you?",
                "type": "text",
                "metadata": {},
                "replyToId": None,
                "isEdited": False,
                "sequenceNumber": 42,
                "createdAt": "2025-10-10T10:00:00Z",
                "updatedAt": None,
                "deletedAt": None,
                "reactions": [],
                "statuses": [],
                "poll": None,
                "status": "sent"
            }
        }
    )


class MessageListResponse(BaseModel):
    """Schema for paginated message list response."""

    data: List[MessageResponse]
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
                    "total": 150
                }
            }
        }


class MessageStatusUpdateResponse(BaseModel):
    """Response for message status update."""

    success: bool
    updated_count: int
    message: str

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "updated_count": 5,
                "message": "Messages marked as read"
            }
        }


class MessageDeleteResponse(BaseModel):
    """Response for message deletion."""

    success: bool
    message: str
    deleted_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Message deleted successfully",
                "deleted_at": "2025-10-10T10:00:00Z"
            }
        }
