"""
Encryption API routes for E2EE key management.

Provides endpoints for key bundle upload/fetch, pre-key replenishment,
and sender key distribution.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.encryption import (
    KeyBundleUpload,
    KeyBundleResponse,
    PreKeyUpload,
    PreKeyCountResponse,
    SenderKeyDistribute,
    SenderKeysResponse,
    KeyBackupUpload,
    KeyBackupResponse,
    KeyBackupStatusResponse,
    ConversationKeyBackupUpload,
    ConversationKeyBackupResponse,
)
from app.services.encryption_service import EncryptionService

logger = logging.getLogger(__name__)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


async def _get_local_user_id(db: AsyncSession, tms_user_id: str) -> str:
    """Resolve TMS user ID to local user ID."""
    from app.models.user import User
    from sqlalchemy import select

    result = await db.execute(
        select(User).where(User.tms_user_id == tms_user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in local database",
        )
    return user.id


@router.post(
    "/keys/bundle",
    status_code=status.HTTP_201_CREATED,
    summary="Upload key bundle",
    description="Upload or update the user's E2EE key bundle (identity key, signed pre-key, one-time pre-keys).",
)
@limiter.limit("10/minute")
async def upload_key_bundle(
    request: Request,
    bundle_data: KeyBundleUpload,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload the current user's E2EE key bundle."""
    try:
        user_id = await _get_local_user_id(db, current_user["tms_user_id"])
        service = EncryptionService(db)

        await service.upsert_key_bundle(
            user_id=user_id,
            identity_key=bundle_data.identity_key,
            signed_prekey_public=bundle_data.signed_prekey.public_key,
            signed_prekey_signature=bundle_data.signed_prekey.signature,
            signed_prekey_id=bundle_data.signed_prekey.key_id,
            one_time_prekeys=[
                {"key_id": opk.key_id, "public_key": opk.public_key}
                for opk in bundle_data.one_time_prekeys
            ],
        )

        return {"success": True, "message": "Key bundle uploaded"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ENCRYPTION] upload_key_bundle failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload key bundle: {type(e).__name__}",
        )


@router.get(
    "/keys/bundle/{user_id}",
    response_model=KeyBundleResponse,
    summary="Fetch key bundle",
    description="Fetch a user's public key bundle for establishing an E2EE session. One-time pre-key is consumed on fetch.",
)
@limiter.limit("30/minute")
async def get_key_bundle(
    request: Request,
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch a user's key bundle for session establishment."""
    try:
        # Resolve the target user_id (could be TMS ID or local ID)
        from app.models.user import User
        from sqlalchemy import select

        # Try to find user by local ID first, then TMS ID
        result = await db.execute(select(User).where(User.id == user_id))
        target_user = result.scalar_one_or_none()

        if not target_user:
            result = await db.execute(
                select(User).where(User.tms_user_id == user_id)
            )
            target_user = result.scalar_one_or_none()

        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        service = EncryptionService(db)
        bundle = await service.get_key_bundle(target_user.id)

        if not bundle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Key bundle not found for this user",
            )

        return bundle
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ENCRYPTION] get_key_bundle failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch key bundle: {type(e).__name__}",
        )


@router.post(
    "/keys/prekeys",
    status_code=status.HTTP_201_CREATED,
    summary="Replenish pre-keys",
    description="Add additional one-time pre-keys to the user's key bundle.",
)
@limiter.limit("10/minute")
async def replenish_prekeys(
    request: Request,
    prekey_data: PreKeyUpload,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add more one-time pre-keys."""
    try:
        user_id = await _get_local_user_id(db, current_user["tms_user_id"])
        service = EncryptionService(db)

        added = await service.add_prekeys(
            user_id=user_id,
            prekeys=[
                {"key_id": pk.key_id, "public_key": pk.public_key}
                for pk in prekey_data.prekeys
            ],
        )

        return {"success": True, "added": added}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ENCRYPTION] replenish_prekeys failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to replenish pre-keys: {type(e).__name__}",
        )


@router.get(
    "/keys/prekeys/count",
    response_model=PreKeyCountResponse,
    summary="Get pre-key count",
    description="Get the number of remaining one-time pre-keys.",
)
async def get_prekey_count(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get remaining pre-key count for the current user."""
    user_id = await _get_local_user_id(db, current_user["tms_user_id"])
    service = EncryptionService(db)
    count = await service.get_prekey_count(user_id)
    return {"count": count}


@router.post(
    "/sender-keys/distribute",
    status_code=status.HTTP_200_OK,
    summary="Distribute sender key",
    description="Distribute a group sender key to specified recipients via WebSocket.",
)
@limiter.limit("20/minute")
async def distribute_sender_key(
    request: Request,
    data: SenderKeyDistribute,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Distribute a sender key to group members."""
    try:
        user_id = await _get_local_user_id(db, current_user["tms_user_id"])
        service = EncryptionService(db)

        await service.distribute_sender_key(
            sender_id=user_id,
            conversation_id=data.conversation_id,
            sender_key_id=data.distribution.sender_key_id,
            public_key=data.distribution.public_key,
            recipients=data.recipients,
            chain_key=data.distribution.chain_key,
        )

        return {"success": True, "message": "Sender key distributed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[ENCRYPTION] distribute_sender_key failed: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to distribute sender key: {type(e).__name__}",
        )


@router.get(
    "/sender-keys/{conversation_id}",
    response_model=SenderKeysResponse,
    summary="Fetch group sender keys",
    description="Fetch all stored sender keys for a group conversation. Only accessible to conversation members.",
)
@limiter.limit("30/minute")
async def get_sender_keys(
    request: Request,
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch all sender keys for a group (called when opening a group chat)."""
    try:
        user_id = await _get_local_user_id(db, current_user["tms_user_id"])
        service = EncryptionService(db)

        keys = await service.get_sender_keys(
            conversation_id=conversation_id,
            requesting_user_id=user_id,
        )

        return {"sender_keys": keys}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[ENCRYPTION] get_sender_keys failed: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch sender keys: {type(e).__name__}",
        )


# ==================== Key Backup Endpoints ====================


@router.post(
    "/keys/backup",
    status_code=status.HTTP_200_OK,
    summary="Upload key backup",
    description="Upload an encrypted key backup. Overwrites any existing backup.",
)
@limiter.limit("5/minute")
async def upload_key_backup(
    request: Request,
    backup_data: KeyBackupUpload,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload an encrypted key backup."""
    try:
        user_id = await _get_local_user_id(db, current_user["tms_user_id"])
        service = EncryptionService(db)

        await service.upsert_key_backup(
            user_id=user_id,
            encrypted_data=backup_data.encrypted_data,
            nonce=backup_data.nonce,
            salt=backup_data.salt,
            key_derivation=backup_data.key_derivation,
            version=backup_data.version,
            identity_key_hash=backup_data.identity_key_hash,
        )

        return {"success": True, "message": "Key backup uploaded"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ENCRYPTION] upload_key_backup failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload key backup: {type(e).__name__}",
        )


@router.get(
    "/keys/backup",
    response_model=KeyBackupResponse,
    summary="Download key backup",
    description="Download the encrypted key backup for the current user.",
)
@limiter.limit("10/minute")
async def get_key_backup(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download the encrypted key backup."""
    try:
        user_id = await _get_local_user_id(db, current_user["tms_user_id"])
        service = EncryptionService(db)

        backup = await service.get_key_backup(user_id)
        if not backup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No key backup found",
            )

        return backup
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ENCRYPTION] get_key_backup failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch key backup: {type(e).__name__}",
        )


@router.get(
    "/keys/backup/status",
    response_model=KeyBackupStatusResponse,
    summary="Check backup status",
    description="Check if a key backup exists for the current user.",
)
async def get_key_backup_status(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if a key backup exists."""
    user_id = await _get_local_user_id(db, current_user["tms_user_id"])
    service = EncryptionService(db)
    return await service.has_key_backup(user_id)


# ==================== Conversation Key Backup Endpoints ====================


@router.post(
    "/keys/conversation",
    status_code=status.HTTP_200_OK,
    summary="Upload conversation key backup",
    description="Store the conversation key encrypted with the user's identity key for multi-device recovery.",
)
@limiter.limit("60/minute")
async def upload_conversation_key(
    request: Request,
    data: ConversationKeyBackupUpload,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload an encrypted conversation key for multi-device recovery."""
    try:
        user_id = await _get_local_user_id(db, current_user["tms_user_id"])
        service = EncryptionService(db)

        await service.upsert_conversation_key_backup(
            user_id=user_id,
            conversation_id=data.conversation_id,
            encrypted_key=data.encrypted_key,
            nonce=data.nonce,
        )

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ENCRYPTION] upload_conversation_key failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload conversation key: {type(e).__name__}",
        )


@router.get(
    "/keys/conversation/{conversation_id}",
    response_model=ConversationKeyBackupResponse,
    summary="Fetch conversation key backup",
    description="Retrieve the encrypted conversation key for multi-device session recovery.",
)
@limiter.limit("60/minute")
async def get_conversation_key(
    request: Request,
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch the encrypted conversation key for multi-device recovery."""
    try:
        user_id = await _get_local_user_id(db, current_user["tms_user_id"])
        service = EncryptionService(db)

        record = await service.get_conversation_key_backup(user_id, conversation_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No conversation key backup found",
            )

        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ENCRYPTION] get_conversation_key failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversation key: {type(e).__name__}",
        )
