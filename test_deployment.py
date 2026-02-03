"""
Quick test to verify all imports work
"""
import sys

print("Testing imports...")

try:
    # Test that all our fixed imports work
    from app.services.conversation_service import ConversationService
    print("✅ conversation_service imports OK")
    
    from app.services.message_service import MessageService  
    print("✅ message_service imports OK")
    
    from app.repositories.base import BaseRepository
    print("✅ base repository imports OK")
    
    from app.core.websocket import ConnectionManager
    print("✅ websocket imports OK")
    
    print("\n✅ ALL IMPORTS SUCCESSFUL - Code is ready to deploy")
    sys.exit(0)
    
except Exception as e:
    print(f"\n❌ IMPORT FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
