"""
Pydantic schemas for poll requests and responses.
Handles validation for poll-related API endpoints.
"""
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
# UUID import removed - using str for ID types

from pydantic import BaseModel, Field, field_validator, ConfigDict
from app.schemas.message import MessageResponse


def to_camel(string: str) -> str:
    """Convert snake_case to camelCase."""
    components = string.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


# ============================================================================
# Request Schemas
# ============================================================================

class PollOptionCreate(BaseModel):
    """Schema for creating a poll option."""

    option_text: str = Field(..., min_length=1, max_length=500, description="Poll option text")
    position: int = Field(..., ge=0, description="Display position of option")

    @field_validator("option_text")
    @classmethod
    def validate_option_text(cls, v: str) -> str:
        """Ensure option text is not empty or whitespace."""
        if len(v.strip()) == 0:
            raise ValueError("Option text cannot be empty or whitespace only")
        return v.strip()

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "option_text": "Pizza",
                "position": 0
            }
        }
    )


class PollCreate(BaseModel):
    """Schema for creating a poll."""

    conversation_id: str = Field(..., description="Conversation ID where poll will be sent")
    question: str = Field(..., min_length=1, max_length=255, description="Poll question")
    options: List[PollOptionCreate] = Field(
        ...,
        min_length=2,
        max_length=10,
        description="Poll options (2-10)"
    )
    multiple_choice: bool = Field(
        default=False,
        description="Allow multiple answers"
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="When the poll expires (null for no expiration)"
    )

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        """Ensure question is not empty or whitespace."""
        if len(v.strip()) == 0:
            raise ValueError("Question cannot be empty or whitespace only")
        return v.strip()

    @field_validator("options")
    @classmethod
    def validate_options(cls, v: List[PollOptionCreate]) -> List[PollOptionCreate]:
        """Validate options have unique texts and proper positions."""
        if len(v) < 2:
            raise ValueError("Poll must have at least 2 options")
        if len(v) > 10:
            raise ValueError("Poll cannot have more than 10 options")

        # Check for duplicate option texts
        option_texts = [opt.option_text.lower() for opt in v]
        if len(option_texts) != len(set(option_texts)):
            raise ValueError("Poll options must have unique texts")

        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
                "question": "What's for lunch?",
                "options": [
                    {"option_text": "Pizza", "position": 0},
                    {"option_text": "Burgers", "position": 1},
                    {"option_text": "Salad", "position": 2}
                ],
                "multiple_choice": False,
                "expires_at": None
            }
        }
    )


class PollVoteCreate(BaseModel):
    """Schema for voting on a poll."""

    option_ids: List[str] = Field(
        ...,
        min_length=1,
        description="Option ID(s) to vote for"
    )

    @field_validator("option_ids")
    @classmethod
    def validate_option_ids(cls, v: List[str]) -> List[str]:
        """Ensure no duplicate option IDs."""
        if len(v) != len(set(v)):
            raise ValueError("Cannot vote for the same option multiple times")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "option_ids": ["123e4567-e89b-12d3-a456-426614174000"]
            }
        }
    )


# ============================================================================
# Response Schemas
# ============================================================================

class PollOptionResponse(BaseModel):
    """Schema for poll option response with vote data."""

    id: str
    poll_id: str = Field(serialization_alias="pollId")
    option_text: str = Field(serialization_alias="optionText")
    position: int
    vote_count: int = Field(serialization_alias="voteCount")
    voters: List[str] = Field(default_factory=list, description="User IDs who voted for this option")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "pollId": "123e4567-e89b-12d3-a456-426614174001",
                "optionText": "Pizza",
                "position": 0,
                "voteCount": 5,
                "voters": []
            }
        }
    )


class PollResponse(BaseModel):
    """Schema for poll response with full details and results."""

    id: str
    message_id: str = Field(serialization_alias="messageId")
    question: str
    multiple_choice: bool = Field(serialization_alias="multipleChoice")
    is_closed: bool = Field(default=False, serialization_alias="isClosed")
    expires_at: Optional[datetime] = Field(None, serialization_alias="expiresAt")
    created_at: datetime = Field(serialization_alias="createdAt")

    # Poll results
    options: List[PollOptionResponse]
    total_votes: int = Field(serialization_alias="totalVotes")
    user_votes: List[str] = Field(
        default_factory=list,
        serialization_alias="userVotes",
        description="Option IDs the current user voted for"
    )

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        ser_json_by_alias=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "messageId": "123e4567-e89b-12d3-a456-426614174001",
                "question": "What's for lunch?",
                "multipleChoice": False,
                "isClosed": False,
                "expiresAt": None,
                "createdAt": "2025-10-27T10:00:00Z",
                "options": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174002",
                        "pollId": "123e4567-e89b-12d3-a456-426614174000",
                        "optionText": "Pizza",
                        "position": 0,
                        "voteCount": 5,
                        "voters": []
                    }
                ],
                "totalVotes": 10,
                "userVotes": ["123e4567-e89b-12d3-a456-426614174002"]
            }
        }
    )


class PollVoteResponse(BaseModel):
    """Response after voting on a poll."""

    success: bool
    poll: PollResponse
    message: str = "Vote recorded successfully"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Vote recorded successfully",
                "poll": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "messageId": "123e4567-e89b-12d3-a456-426614174001",
                    "question": "What's for lunch?",
                    "multipleChoice": False,
                    "isClosed": False,
                    "totalVotes": 11,
                    "userVotes": ["123e4567-e89b-12d3-a456-426614174002"]
                }
            }
        }
    )


class CreatePollResponse(BaseModel):
    """Response when creating a new poll."""

    poll: PollResponse
    message: MessageResponse

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "poll": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "messageId": "123e4567-e89b-12d3-a456-426614174001",
                    "question": "What's for lunch?",
                    "multipleChoice": False,
                    "isClosed": False,
                    "totalVotes": 0,
                    "options": [
                        {
                            "id": "123e4567-e89b-12d3-a456-426614174002",
                            "pollId": "123e4567-e89b-12d3-a456-426614174000",
                            "optionText": "Pizza",
                            "position": 0,
                            "voteCount": 0,
                            "voters": []
                        }
                    ],
                    "userVotes": []
                },
                "message": {
                    "id": "123e4567-e89b-12d3-a456-426614174001",
                    "conversationId": "123e4567-e89b-12d3-a456-426614174003",
                    "senderId": "123e4567-e89b-12d3-a456-426614174004",
                    "content": "What's for lunch?",
                    "type": "POLL",
                    "createdAt": "2025-10-27T10:00:00Z"
                }
            }
        }
    )
