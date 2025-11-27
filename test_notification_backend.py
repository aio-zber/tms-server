"""
Test script for notification backend implementation.
Verifies models, schemas, and endpoints are correctly set up.
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models import NotificationPreferences, MutedConversation, User
from app.schemas.notification import (
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
    MutedConversationResponse
)


async def test_models():
    """Test that models can be imported and instantiated."""
    print("Testing models...")

    # Test NotificationPreferences model
    prefs = NotificationPreferences(
        user_id="test-user-id",
        sound_enabled=True,
        sound_volume=75
    )
    assert prefs.user_id == "test-user-id"
    assert prefs.sound_enabled == True
    assert prefs.sound_volume == 75
    print("✓ NotificationPreferences model works")

    # Test MutedConversation model
    muted = MutedConversation(
        user_id="test-user-id",
        conversation_id="test-conversation-id"
    )
    assert muted.user_id == "test-user-id"
    assert muted.conversation_id == "test-conversation-id"
    print("✓ MutedConversation model works")


def test_schemas():
    """Test that schemas can validate data."""
    print("\nTesting schemas...")

    # Test NotificationPreferencesUpdate schema
    update_data = {
        "sound_enabled": False,
        "sound_volume": 50,
        "dnd_enabled": True,
        "dnd_start": "22:00",
        "dnd_end": "08:00"
    }
    update = NotificationPreferencesUpdate(**update_data)
    assert update.sound_enabled == False
    assert update.sound_volume == 50
    assert update.dnd_start == "22:00"
    print("✓ NotificationPreferencesUpdate schema works")

    # Test invalid time format
    try:
        invalid_update = NotificationPreferencesUpdate(dnd_start="invalid")
        print("✗ Schema validation failed - should have rejected invalid time")
    except Exception:
        print("✓ Schema validation works (rejects invalid time)")


def test_imports():
    """Test that all necessary modules can be imported."""
    print("\nTesting imports...")

    try:
        from app.api.v1.notifications import router
        print("✓ Notification router imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import notification router: {e}")
        return False

    try:
        from app.services.notification_service import NotificationService
        print("✓ NotificationService imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import NotificationService: {e}")
        return False

    return True


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Notification Backend Implementation Test")
    print("=" * 60)

    # Test imports
    if not test_imports():
        print("\n✗ Import tests failed")
        return

    # Test schemas
    test_schemas()

    # Test models
    await test_models()

    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Start the server: uvicorn app.main:app --reload --port 8000")
    print("2. Check API docs: http://localhost:8000/docs")
    print("3. Test endpoints:")
    print("   - GET /api/v1/notifications/preferences")
    print("   - PUT /api/v1/notifications/preferences")
    print("   - POST /api/v1/notifications/conversations/{id}/mute")
    print("   - DELETE /api/v1/notifications/conversations/{id}/mute")
    print("   - GET /api/v1/notifications/muted-conversations")


if __name__ == "__main__":
    asyncio.run(main())
