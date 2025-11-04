"""
User schemas for API request/response validation.
Maps TMS user data to internal application structures.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class TMSReportsToSchema(BaseModel):
    """Schema for reports_to relationship from TMS."""
    id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    name: Optional[str] = None
    email: str
    role: str


class TMSCurrentUserSchema(BaseModel):
    """
    Schema for current authenticated user from TMS /api/v1/users/me.
    Contains full user profile with all organizational details.
    """
    id: str
    email: EmailStr
    username: Optional[str] = None
    first_name: Optional[str] = Field(None, alias="firstName")
    last_name: Optional[str] = Field(None, alias="lastName")
    middle_name: Optional[str] = Field(None, alias="middleName")
    name: Optional[str] = None
    contact_number: Optional[str] = Field(None, alias="contactNumber")
    image: Optional[str] = None
    role: str  # 'ADMIN' | 'LEADER' | 'MEMBER'
    hierarchy_level: Optional[str] = Field(None, alias="hierarchyLevel")
    reports_to_id: Optional[str] = Field(None, alias="reportsToId")
    division: Optional[str] = None
    department: Optional[str] = None
    section: Optional[str] = None
    team: Optional[str] = None
    position_title: Optional[str] = Field(None, alias="positionTitle")
    short_name: Optional[str] = Field(None, alias="shortName")
    job_level: Optional[str] = Field(None, alias="jobLevel")
    organizational_path: Optional[str] = Field(None, alias="organizationalPath")
    sector_head_initials: Optional[str] = Field(None, alias="sectorHeadInitials")
    custom_division: Optional[str] = Field(None, alias="customDivision")
    custom_department: Optional[str] = Field(None, alias="customDepartment")
    custom_section: Optional[str] = Field(None, alias="customSection")
    custom_team: Optional[str] = Field(None, alias="customTeam")
    is_leader: bool = Field(alias="isLeader")
    is_active: bool = Field(alias="isActive")
    email_verified: Optional[datetime] = Field(None, alias="emailVerified")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    reports_to: Optional[TMSReportsToSchema] = Field(None, alias="reportsTo")

    class Config:
        populate_by_name = True


class TMSPublicUserSchema(BaseModel):
    """
    Schema for public user profile from TMS /api/v1/users/{id}.
    Contains limited user information for public viewing.
    """
    id: str
    email: EmailStr
    username: Optional[str] = None
    first_name: Optional[str] = Field(None, alias="firstName")
    last_name: Optional[str] = Field(None, alias="lastName")
    name: Optional[str] = None
    image: Optional[str] = None
    role: str  # 'ADMIN' | 'LEADER' | 'MEMBER'
    position_title: Optional[str] = Field(None, alias="positionTitle")
    division: Optional[str] = None
    department: Optional[str] = None
    section: Optional[str] = None
    custom_team: Optional[str] = Field(None, alias="customTeam")
    is_active: bool = Field(alias="isActive")
    created_at: datetime = Field(alias="createdAt")

    class Config:
        populate_by_name = True


class TMSSearchUserSchema(BaseModel):
    """
    Schema for user search results from TMS /api/v1/users/search.
    Optimized schema for search results with essential fields.
    """
    id: str
    name: Optional[str] = None
    first_name: Optional[str] = Field(None, alias="firstName")
    last_name: Optional[str] = Field(None, alias="lastName")
    email: EmailStr
    username: Optional[str] = None
    image: Optional[str] = None
    position_title: Optional[str] = Field(None, alias="positionTitle")
    division: Optional[str] = None
    department: Optional[str] = None
    section: Optional[str] = None
    custom_team: Optional[str] = Field(None, alias="customTeam")
    is_active: bool = Field(alias="isActive")

    class Config:
        populate_by_name = True


class UserSearchResponse(BaseModel):
    """Response schema for user search from TMS."""
    users: list[TMSSearchUserSchema]


class UserResponse(BaseModel):
    """
    Response schema for user data in Team Messaging System.
    Combines TMS data with local settings.

    Note: Uses serialization_alias to output camelCase for frontend compatibility
    while keeping internal snake_case for Python conventions.
    """
    id: str  # Local user ID
    tms_user_id: str = Field(serialization_alias="tmsUserId")
    email: EmailStr
    username: Optional[str] = None
    first_name: Optional[str] = Field(None, serialization_alias="firstName")
    last_name: Optional[str] = Field(None, serialization_alias="lastName")
    middle_name: Optional[str] = Field(None, serialization_alias="middleName")
    name: Optional[str] = None
    display_name: str = Field(serialization_alias="displayName")  # Computed from name/first_name+last_name
    image: Optional[str] = None
    role: str  # Mapped from TMS role
    position_title: Optional[str] = Field(None, serialization_alias="positionTitle")
    division: Optional[str] = None
    department: Optional[str] = None
    section: Optional[str] = None
    custom_team: Optional[str] = Field(None, serialization_alias="customTeam")
    is_active: bool = Field(serialization_alias="isActive")
    is_leader: bool = Field(serialization_alias="isLeader")
    last_synced_at: Optional[datetime] = Field(None, serialization_alias="lastSyncedAt")
    created_at: datetime = Field(serialization_alias="createdAt")

    # Local settings (from messaging system)
    settings: Optional[dict] = None

    class Config:
        populate_by_name = True


class UserSearchRequest(BaseModel):
    """Request schema for user search."""
    query: str = Field(..., min_length=1, max_length=100, description="Search query")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of results")
    filters: Optional[dict] = Field(
        default=None,
        description="Optional filters (division, department, section, role, is_active)"
    )


class UserSyncRequest(BaseModel):
    """Request schema for manual user sync (admin only)."""
    tms_user_ids: Optional[list[str]] = Field(
        default=None,
        description="Specific user IDs to sync. If None, syncs all active users."
    )
    force: bool = Field(
        default=False,
        description="Force sync even if recently synced"
    )


class UserSyncResponse(BaseModel):
    """Response schema for user sync operation."""
    success: bool
    synced_count: int
    failed_count: int
    errors: list[str] = []
