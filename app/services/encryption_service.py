"""
Encryption service for E2EE key bundle management.

Handles CRUD operations for key bundles, one-time pre-keys,
and group sender keys. The server stores only public keys —
private keys never leave the client device.
"""
import logging
from typing import Optional, List, Dict, Any

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.encryption import UserKeyBundle, OneTimePreKey, GroupSenderKey, KeyBackup, ConversationKeyBackup
from app.utils.datetime_utils import utc_now
from app.core.cache import cache

logger = logging.getLogger(__name__)


class EncryptionService:
    """Service for E2EE key management operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert_key_bundle(
        self,
        user_id: str,
        identity_key: str,
        signed_prekey_public: str,
        signed_prekey_signature: str,
        signed_prekey_id: int,
        one_time_prekeys: List[Dict[str, Any]],
    ) -> None:
        """
        Upload or update a user's key bundle.

        Upserts the identity key and signed pre-key, then inserts
        any new one-time pre-keys.

        Args:
            user_id: User ID
            identity_key: Base64-encoded public identity key
            signed_prekey_public: Base64-encoded signed pre-key
            signed_prekey_signature: Base64-encoded signature
            signed_prekey_id: Signed pre-key ID
            one_time_prekeys: List of {key_id, public_key} dicts
        """
        # Upsert key bundle
        result = await self.db.execute(
            select(UserKeyBundle).where(UserKeyBundle.user_id == user_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.identity_key = identity_key
            existing.signed_prekey = signed_prekey_public
            existing.signed_prekey_signature = signed_prekey_signature
            existing.signed_prekey_id = signed_prekey_id
            existing.updated_at = utc_now()
        else:
            bundle = UserKeyBundle(
                user_id=user_id,
                identity_key=identity_key,
                signed_prekey=signed_prekey_public,
                signed_prekey_signature=signed_prekey_signature,
                signed_prekey_id=signed_prekey_id,
            )
            self.db.add(bundle)

        # Insert one-time pre-keys (skip duplicates)
        for opk in one_time_prekeys:
            # Check if this prekey_id already exists for this user
            existing_opk = await self.db.execute(
                select(OneTimePreKey).where(
                    OneTimePreKey.user_id == user_id,
                    OneTimePreKey.prekey_id == opk["key_id"],
                )
            )
            if existing_opk.scalar_one_or_none() is None:
                self.db.add(OneTimePreKey(
                    user_id=user_id,
                    prekey_id=opk["key_id"],
                    public_key=opk["public_key"],
                ))

        await self.db.commit()

        # Invalidate cached key bundle
        await cache.delete(f"keybundle:{user_id}")

        logger.info(
            f"[ENCRYPTION] Key bundle upserted for user {user_id}, "
            f"{len(one_time_prekeys)} OPKs added"
        )

    async def get_key_bundle(
        self, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch a user's key bundle for session establishment.

        Returns the identity key, signed pre-key, and consumes ONE
        one-time pre-key (deleted after fetch to prevent replay).

        Args:
            user_id: User ID whose bundle to fetch

        Returns:
            Key bundle dict or None if user has no bundle
        """
        # Try Redis cache for stable key bundle data (identity key + signed prekey)
        cache_key = f"keybundle:{user_id}"
        cached_bundle = await cache.get(cache_key)

        if cached_bundle:
            response: Dict[str, Any] = {
                "user_id": user_id,
                "identity_key": cached_bundle["identity_key"],
                "signed_prekey": cached_bundle["signed_prekey"],
                "one_time_prekey": None,
            }
        else:
            result = await self.db.execute(
                select(UserKeyBundle).where(UserKeyBundle.user_id == user_id)
            )
            bundle = result.scalar_one_or_none()

            if not bundle:
                return None

            response = {
                "user_id": user_id,
                "identity_key": bundle.identity_key,
                "signed_prekey": {
                    "key_id": bundle.signed_prekey_id,
                    "public_key": bundle.signed_prekey,
                    "signature": bundle.signed_prekey_signature,
                },
                "one_time_prekey": None,
            }

            # Cache stable parts (identity key + signed prekey) for 10 minutes
            await cache.set(cache_key, {
                "identity_key": bundle.identity_key,
                "signed_prekey": response["signed_prekey"],
            }, ttl=600)

        # Always fetch OPK from DB (consumed per-call, not cacheable)
        opk_result = await self.db.execute(
            select(OneTimePreKey)
            .where(OneTimePreKey.user_id == user_id)
            .order_by(OneTimePreKey.prekey_id.asc())
            .limit(1)
        )
        opk = opk_result.scalar_one_or_none()

        if opk:
            response["one_time_prekey"] = {
                "key_id": opk.prekey_id,
                "public_key": opk.public_key,
            }
            # Delete consumed pre-key
            await self.db.delete(opk)
            await self.db.commit()
            logger.info(
                f"[ENCRYPTION] OPK {opk.prekey_id} consumed for user {user_id}"
            )
        else:
            await self.db.commit()
            logger.warning(
                f"[ENCRYPTION] No OPKs available for user {user_id}"
            )

        return response

    async def add_prekeys(
        self, user_id: str, prekeys: List[Dict[str, Any]]
    ) -> int:
        """
        Add additional one-time pre-keys for a user.

        Args:
            user_id: User ID
            prekeys: List of {key_id, public_key} dicts

        Returns:
            Number of pre-keys added
        """
        added = 0
        for pk in prekeys:
            existing = await self.db.execute(
                select(OneTimePreKey).where(
                    OneTimePreKey.user_id == user_id,
                    OneTimePreKey.prekey_id == pk["key_id"],
                )
            )
            if existing.scalar_one_or_none() is None:
                self.db.add(OneTimePreKey(
                    user_id=user_id,
                    prekey_id=pk["key_id"],
                    public_key=pk["public_key"],
                ))
                added += 1

        await self.db.commit()
        logger.info(f"[ENCRYPTION] Added {added} pre-keys for user {user_id}")
        return added

    async def get_prekey_count(self, user_id: str) -> int:
        """Get the number of remaining one-time pre-keys for a user."""
        result = await self.db.execute(
            select(func.count())
            .select_from(OneTimePreKey)
            .where(OneTimePreKey.user_id == user_id)
        )
        return result.scalar() or 0

    async def upsert_sender_key(
        self,
        conversation_id: str,
        sender_id: str,
        sender_key_id: str,
        public_key: str,
    ) -> None:
        """
        Store or update a group sender key.

        Args:
            conversation_id: Group conversation ID
            sender_id: User who owns this sender key
            sender_key_id: Client-assigned sender key ID
            public_key: Base64-encoded sender key public data
        """
        result = await self.db.execute(
            select(GroupSenderKey).where(
                GroupSenderKey.conversation_id == conversation_id,
                GroupSenderKey.sender_id == sender_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.sender_key_id = sender_key_id
            existing.public_key = public_key
            existing.created_at = utc_now()
        else:
            self.db.add(GroupSenderKey(
                conversation_id=conversation_id,
                sender_id=sender_id,
                sender_key_id=sender_key_id,
                public_key=public_key,
            ))

        await self.db.flush()

    async def distribute_sender_key(
        self,
        sender_id: str,
        conversation_id: str,
        sender_key_id: str,
        public_key: str,
        recipients: List[str],
    ) -> None:
        """
        Store sender key and relay distribution to recipients via WebSocket.

        Args:
            sender_id: User distributing their key
            conversation_id: Group conversation
            sender_key_id: Client-assigned key ID
            public_key: Base64-encoded key data
            recipients: User IDs to distribute to
        """
        # Store the sender key
        await self.upsert_sender_key(
            conversation_id, sender_id, sender_key_id, public_key
        )
        await self.db.commit()

        # Relay to recipients via WebSocket
        from app.core.websocket import connection_manager

        distribution_data = {
            "conversation_id": conversation_id,
            "sender_id": sender_id,
            "sender_key_id": sender_key_id,
            "public_key": public_key,
        }

        for recipient_id in recipients:
            if recipient_id == sender_id:
                continue
            sids = connection_manager.user_sessions.get(recipient_id, set())
            for sid in sids:
                try:
                    await connection_manager.sio.emit(
                        "sender_key_distribution",
                        distribution_data,
                        to=sid,
                    )
                except Exception as e:
                    logger.error(
                        f"[ENCRYPTION] Failed to relay sender key to {recipient_id}: {e}"
                    )

        logger.info(
            f"[ENCRYPTION] Sender key distributed: sender={sender_id}, "
            f"conversation={conversation_id}, recipients={len(recipients)}"
        )

    # ==================== Key Backup ====================

    async def upsert_key_backup(
        self,
        user_id: str,
        encrypted_data: str,
        nonce: str,
        salt: str,
        key_derivation: str,
        version: int,
        identity_key_hash: str,
    ) -> None:
        """
        Create or update an encrypted key backup.

        Args:
            user_id: User ID
            encrypted_data: Base64 encrypted key blob
            nonce: Base64 encryption nonce
            salt: Base64 Argon2id salt
            key_derivation: KDF algorithm used
            version: Backup format version
            identity_key_hash: SHA-256 hex of public identity key
        """
        result = await self.db.execute(
            select(KeyBackup).where(KeyBackup.user_id == user_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.encrypted_data = encrypted_data
            existing.nonce = nonce
            existing.salt = salt
            existing.key_derivation = key_derivation
            existing.version = version
            existing.identity_key_hash = identity_key_hash
            existing.updated_at = utc_now()
        else:
            self.db.add(KeyBackup(
                user_id=user_id,
                encrypted_data=encrypted_data,
                nonce=nonce,
                salt=salt,
                key_derivation=key_derivation,
                version=version,
                identity_key_hash=identity_key_hash,
            ))

        await self.db.commit()
        await cache.delete(f"keybackup:status:{user_id}")

        logger.info(f"[ENCRYPTION] Key backup upserted for user {user_id}")

    async def get_key_backup(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the encrypted key backup for a user."""
        result = await self.db.execute(
            select(KeyBackup).where(KeyBackup.user_id == user_id)
        )
        backup = result.scalar_one_or_none()

        if not backup:
            return None

        return {
            "encrypted_data": backup.encrypted_data,
            "nonce": backup.nonce,
            "salt": backup.salt,
            "key_derivation": backup.key_derivation,
            "version": backup.version,
            "identity_key_hash": backup.identity_key_hash,
            "created_at": backup.created_at.isoformat(),
        }

    async def has_key_backup(self, user_id: str) -> Dict[str, Any]:
        """Check if a key backup exists (cached in Redis 5 min)."""
        cache_key = f"keybackup:status:{user_id}"
        cached = await cache.get(cache_key)

        if cached is not None:
            return cached

        result = await self.db.execute(
            select(KeyBackup).where(KeyBackup.user_id == user_id)
        )
        backup = result.scalar_one_or_none()

        status = {
            "has_backup": backup is not None,
            "created_at": backup.created_at.isoformat() if backup else None,
            "identity_key_hash": backup.identity_key_hash if backup else None,
        }

        await cache.set(cache_key, status, ttl=300)
        return status

    # ==================== Conversation Key Backup ====================

    async def upsert_conversation_key_backup(
        self,
        user_id: str,
        conversation_id: str,
        encrypted_key: str,
        nonce: str,
    ) -> None:
        """
        Store or update the encrypted conversation key for multi-device recovery.
        Only the owning user can store/retrieve their conversation key backup.
        """
        result = await self.db.execute(
            select(ConversationKeyBackup).where(
                ConversationKeyBackup.user_id == user_id,
                ConversationKeyBackup.conversation_id == conversation_id,
            )
        )
        existing = result.scalar_one_or_none()

        now = utc_now()
        if existing:
            existing.encrypted_key = encrypted_key
            existing.nonce = nonce
            existing.updated_at = now
        else:
            record = ConversationKeyBackup(
                user_id=user_id,
                conversation_id=conversation_id,
                encrypted_key=encrypted_key,
                nonce=nonce,
            )
            self.db.add(record)

        await self.db.commit()

    async def get_conversation_key_backup(
        self,
        user_id: str,
        conversation_id: str,
    ) -> Optional[Dict[str, str]]:
        """Fetch the encrypted conversation key for multi-device recovery."""
        result = await self.db.execute(
            select(ConversationKeyBackup).where(
                ConversationKeyBackup.user_id == user_id,
                ConversationKeyBackup.conversation_id == conversation_id,
            )
        )
        record = result.scalar_one_or_none()
        if not record:
            return None

        return {
            "conversation_id": record.conversation_id,
            "encrypted_key": record.encrypted_key,
            "nonce": record.nonce,
        }
