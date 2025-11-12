"""
SSO Code Generation and Validation Module

Handles one-time codes for SSO authentication flow.
Codes are short-lived (5 minutes) and can only be used once.
"""

import secrets
import time
from typing import Dict, Optional
from datetime import datetime, timedelta

# In-memory storage for SSO codes
# In production, use Redis for distributed systems
_sso_codes: Dict[str, Dict[str, any]] = {}

# Code expiration time (5 minutes)
CODE_EXPIRATION_SECONDS = 300


def generate_sso_code(user_id: str, user_data: Dict[str, any], gcgc_token: str) -> str:
    """
    Generate a one-time SSO code for a user.

    Args:
        user_id: TMS user ID
        user_data: User data from GCGC
        gcgc_token: GCGC session token to pass through

    Returns:
        One-time SSO code (32-character hex string)
    """
    # Generate cryptographically secure random code
    code = secrets.token_hex(16)  # 32-character hex string

    # Store code with metadata
    _sso_codes[code] = {
        "user_id": user_id,
        "user_data": user_data,
        "gcgc_token": gcgc_token,  # Store GCGC token for pass-through
        "created_at": time.time(),
        "used": False,
    }

    # Clean up expired codes
    _cleanup_expired_codes()

    return code


def validate_sso_code(code: str) -> Optional[Dict[str, any]]:
    """
    Validate and consume an SSO code.

    Args:
        code: SSO code to validate

    Returns:
        User data if code is valid, None otherwise

    Side Effect:
        Marks code as used (can only be used once)
    """
    if not code or code not in _sso_codes:
        return None

    code_data = _sso_codes[code]

    # Check if already used
    if code_data["used"]:
        return None

    # Check if expired
    age = time.time() - code_data["created_at"]
    if age > CODE_EXPIRATION_SECONDS:
        # Clean up expired code
        del _sso_codes[code]
        return None

    # Mark as used
    code_data["used"] = True

    # Return user data and GCGC token
    return {
        "user_id": code_data["user_id"],
        "user_data": code_data["user_data"],
        "gcgc_token": code_data["gcgc_token"],
    }


def _cleanup_expired_codes():
    """
    Remove expired codes from storage.
    Called periodically during code generation.
    """
    current_time = time.time()
    expired_codes = [
        code
        for code, data in _sso_codes.items()
        if current_time - data["created_at"] > CODE_EXPIRATION_SECONDS
    ]

    for code in expired_codes:
        del _sso_codes[code]


def revoke_sso_code(code: str) -> bool:
    """
    Manually revoke an SSO code.

    Args:
        code: SSO code to revoke

    Returns:
        True if code was revoked, False if code didn't exist
    """
    if code in _sso_codes:
        del _sso_codes[code]
        return True
    return False


def get_active_codes_count() -> int:
    """
    Get count of active (non-expired) SSO codes.
    Useful for monitoring.
    """
    _cleanup_expired_codes()
    return len(_sso_codes)
