"""
Server-side SSO key backup crypto.

When a user opts for TMS-login-based backup instead of a PIN, the client sends
plaintext key material. This module encrypts it server-side using a per-user
key derived from SERVER_KEY_BACKUP_SECRET. On restore, the server decrypts and
returns plaintext over TLS (same trust model as Messenger's account-based backup).
"""
import base64
import hashlib
import hmac

import nacl.secret
import nacl.utils

from app.config import settings


def derive_sso_backup_key(local_user_id: str) -> bytes:
    """Derive a 32-byte per-user key from the server backup secret via HMAC-SHA256."""
    return hmac.new(
        settings.server_key_backup_secret.encode(),
        local_user_id.encode(),
        hashlib.sha256,
    ).digest()


def encrypt_sso_backup(plaintext: bytes, local_user_id: str) -> tuple[str, str]:
    """
    Encrypt plaintext key material for SSO backup storage.

    Returns (encrypted_data_b64, nonce_b64). The nonce is stored alongside the
    ciphertext — it is random and safe to store publicly.
    """
    key = derive_sso_backup_key(local_user_id)
    box = nacl.secret.SecretBox(key)
    encrypted = box.encrypt(plaintext)
    nonce_b64 = base64.b64encode(bytes(encrypted.nonce)).decode()
    ciphertext_b64 = base64.b64encode(bytes(encrypted.ciphertext)).decode()
    return ciphertext_b64, nonce_b64


def decrypt_sso_backup(encrypted_data_b64: str, nonce_b64: str, local_user_id: str) -> bytes:
    """Decrypt an SSO backup blob. Raises CryptoError on tamper/wrong key."""
    key = derive_sso_backup_key(local_user_id)
    box = nacl.secret.SecretBox(key)
    ciphertext = base64.b64decode(encrypted_data_b64)
    nonce = base64.b64decode(nonce_b64)
    return bytes(box.decrypt(ciphertext, nonce))
