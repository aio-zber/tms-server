"""
E2EE encryption models for key bundle storage and sender key distribution.

Stores public keys (identity, signed pre-key, one-time pre-keys) and
group sender keys. Private keys never leave the client device.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserKeyBundle(Base):
    """
    User's public key bundle for X3DH key agreement.

    Contains identity key and signed pre-key (public parts only).
    One-time pre-keys stored separately in OneTimePreKey table.
    """

    __tablename__ = "user_key_bundles"

    user_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        doc="User who owns this key bundle",
    )

    identity_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Base64-encoded public identity key (X25519)",
    )

    signed_prekey: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Base64-encoded signed pre-key public key",
    )

    signed_prekey_signature: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Base64-encoded Ed25519 signature of the signed pre-key",
    )

    signed_prekey_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="ID of the signed pre-key (for rotation tracking)",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="When the key bundle was first uploaded",
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="When the key bundle was last updated",
    )

    def __repr__(self) -> str:
        return f"<UserKeyBundle(user_id={self.user_id})>"


class OneTimePreKey(Base):
    """
    One-time pre-keys for X3DH.

    Each key is consumed once during session establishment and then deleted.
    Clients replenish keys when the count drops below a threshold.
    """

    __tablename__ = "one_time_prekeys"

    id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        doc="Unique ID for this pre-key record",
    )

    user_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="User who owns this pre-key",
    )

    prekey_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Client-assigned pre-key ID",
    )

    public_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Base64-encoded pre-key public key (X25519)",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="When the pre-key was uploaded",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "prekey_id", name="uq_user_prekey_id"),
    )

    def __repr__(self) -> str:
        return f"<OneTimePreKey(user_id={self.user_id}, prekey_id={self.prekey_id})>"


class GroupSenderKey(Base):
    """
    Group sender keys for Sender Key encryption pattern.

    Each group member has a sender key used to encrypt their messages.
    Other members store copies to decrypt those messages.
    """

    __tablename__ = "group_sender_keys"

    id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        doc="Unique ID for this sender key record",
    )

    conversation_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Group conversation this key is for",
    )

    sender_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="User who owns this sender key",
    )

    sender_key_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="Client-assigned sender key ID",
    )

    public_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Base64-encoded sender key public data (signing public key)",
    )

    chain_key: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Base64-encoded initial chain key for decryption",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="When the sender key was distributed",
    )

    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "sender_id",
            name="uq_conversation_sender",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<GroupSenderKey(conversation_id={self.conversation_id}, "
            f"sender_id={self.sender_id})>"
        )


class KeyBackup(Base):
    """
    Encrypted key backup for device recovery.

    Stores PIN-encrypted key material. The server only sees encrypted data —
    the PIN and derived key never leave the client.
    """

    __tablename__ = "key_backups"

    user_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        doc="User who owns this backup",
    )

    encrypted_data: Mapped[str] = mapped_column(
        Text, nullable=False, doc="Base64 encrypted key blob"
    )

    nonce: Mapped[str] = mapped_column(
        Text, nullable=False, doc="Base64 encryption nonce"
    )

    salt: Mapped[str] = mapped_column(
        Text, nullable=False, doc="Base64 Argon2id salt"
    )

    key_derivation: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="argon2id",
        doc="KDF algorithm used",
    )

    version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1",
        doc="Backup format version",
    )

    identity_key_hash: Mapped[str] = mapped_column(
        String(64), nullable=False,
        doc="SHA-256 hex hash of the public identity key",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="When the backup was created",
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="When the backup was last updated",
    )

    def __repr__(self) -> str:
        return f"<KeyBackup(user_id={self.user_id})>"


class ConversationKeyBackup(Base):
    """
    Per-conversation key backup for multi-device support.

    Stores the conversation key encrypted with the user's own identity key,
    so any device that has the identity key can recover conversation sessions.
    The server only stores opaque encrypted blobs — it never sees plaintext keys.
    """

    __tablename__ = "conversation_key_backups"

    id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        doc="Unique ID for this record",
    )

    user_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="User who owns this key backup",
    )

    conversation_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Conversation this key is for",
    )

    encrypted_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Base64 conversation key encrypted with user's identity key",
    )

    nonce: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Base64 nonce used for encryption",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="When the backup was created",
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="When the backup was last updated",
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "conversation_id",
            name="uq_user_conversation_key_backup",
        ),
    )

    def __repr__(self) -> str:
        return f"<ConversationKeyBackup(user_id={self.user_id}, conversation_id={self.conversation_id})>"
