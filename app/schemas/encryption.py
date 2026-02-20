"""
Pydantic schemas for E2EE encryption endpoints.
Handles validation for key bundle upload/fetch and sender key distribution.
"""
from typing import Optional, List

from pydantic import BaseModel, Field


class PreKeyData(BaseModel):
    """A single pre-key (one-time or signed)."""

    key_id: int = Field(..., description="Client-assigned key ID")
    public_key: str = Field(..., description="Base64-encoded public key")


class SignedPreKeyData(BaseModel):
    """Signed pre-key with signature for verification."""

    key_id: int = Field(..., description="Client-assigned signed pre-key ID")
    public_key: str = Field(..., description="Base64-encoded signed pre-key public key")
    signature: str = Field(..., description="Base64-encoded Ed25519 signature")


class KeyBundleUpload(BaseModel):
    """Request to upload a user's key bundle."""

    identity_key: str = Field(..., description="Base64-encoded public identity key")
    signed_prekey: SignedPreKeyData = Field(..., description="Signed pre-key with signature")
    one_time_prekeys: List[PreKeyData] = Field(
        default_factory=list,
        description="List of one-time pre-keys",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "identity_key": "base64EncodedIdentityKey==",
                "signed_prekey": {
                    "key_id": 1,
                    "public_key": "base64EncodedSignedPreKey==",
                    "signature": "base64EncodedSignature==",
                },
                "one_time_prekeys": [
                    {"key_id": 1, "public_key": "base64EncodedOPK1=="},
                    {"key_id": 2, "public_key": "base64EncodedOPK2=="},
                ],
            }
        }


class KeyBundleResponse(BaseModel):
    """Response containing a user's public key bundle for session establishment."""

    user_id: str = Field(..., description="User ID")
    identity_key: str = Field(..., description="Base64-encoded public identity key")
    signed_prekey: SignedPreKeyData = Field(..., description="Signed pre-key with signature")
    one_time_prekey: Optional[PreKeyData] = Field(
        None,
        description="One-time pre-key (consumed after fetch)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user-uuid",
                "identity_key": "base64EncodedIdentityKey==",
                "signed_prekey": {
                    "key_id": 1,
                    "public_key": "base64EncodedSignedPreKey==",
                    "signature": "base64EncodedSignature==",
                },
                "one_time_prekey": {
                    "key_id": 1,
                    "public_key": "base64EncodedOPK==",
                },
            }
        }


class PreKeyUpload(BaseModel):
    """Request to replenish one-time pre-keys."""

    prekeys: List[PreKeyData] = Field(
        ...,
        min_length=1,
        description="List of new one-time pre-keys to add",
    )


class SenderKeyDistributionData(BaseModel):
    """Sender key data for group encryption."""

    sender_key_id: str = Field(..., max_length=64, description="Sender key ID")
    public_key: str = Field(..., description="Base64-encoded sender key public data")
    chain_key: Optional[str] = Field(None, description="Base64-encoded initial chain key")
    signature_key: Optional[str] = Field(None, description="Base64-encoded signing public key")


class SenderKeyDistribute(BaseModel):
    """Request to distribute a sender key to group members."""

    conversation_id: str = Field(..., description="Group conversation ID")
    recipients: List[str] = Field(
        ...,
        min_length=1,
        description="User IDs to distribute the key to",
    )
    distribution: SenderKeyDistributionData = Field(
        ...,
        description="Sender key distribution data",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": "conversation-uuid",
                "recipients": ["user-uuid-1", "user-uuid-2"],
                "distribution": {
                    "sender_key_id": "abc123",
                    "public_key": "base64EncodedKey==",
                },
            }
        }


class SenderKeyEntry(BaseModel):
    """A single sender key entry for a group member."""

    sender_id: str
    key_id: str
    public_signing_key: str
    chain_key: Optional[str] = None


class SenderKeysResponse(BaseModel):
    """Response containing all sender keys for a group conversation."""

    sender_keys: List[SenderKeyEntry]


class PreKeyCountResponse(BaseModel):
    """Response with the user's remaining pre-key count."""

    count: int = Field(..., description="Number of remaining one-time pre-keys")


# ==================== Key Backup Schemas ====================


class KeyBackupUpload(BaseModel):
    """Request to upload an encrypted key backup."""

    encrypted_data: str = Field(..., description="Base64 encrypted key blob")
    nonce: str = Field(..., description="Base64 encryption nonce")
    salt: str = Field(..., description="Base64 Argon2id salt")
    key_derivation: str = Field(default="argon2id", description="KDF algorithm")
    version: int = Field(default=1, description="Backup format version")
    identity_key_hash: str = Field(
        ..., max_length=64, description="SHA-256 hex hash of public identity key"
    )


class KeyBackupResponse(BaseModel):
    """Response containing the encrypted key backup."""

    encrypted_data: str
    nonce: str
    salt: str
    key_derivation: str
    version: int
    identity_key_hash: str
    created_at: str


class KeyBackupStatusResponse(BaseModel):
    """Response indicating whether a backup exists."""

    has_backup: bool
    created_at: Optional[str] = None
    identity_key_hash: Optional[str] = None


# ==================== Conversation Key Backup Schemas ====================


class ConversationKeyBackupUpload(BaseModel):
    """Request to upload an encrypted conversation key for multi-device recovery."""

    conversation_id: str = Field(..., description="Conversation ID")
    encrypted_key: str = Field(..., description="Base64 conversation key encrypted with identity key")
    nonce: str = Field(..., description="Base64 nonce")


class ConversationKeyBackupResponse(BaseModel):
    """Response containing an encrypted conversation key."""

    conversation_id: str
    encrypted_key: str
    nonce: str
