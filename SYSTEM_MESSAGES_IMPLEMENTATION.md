# System Messages Backend Implementation

## ✅ Completed

1. ✅ **Added SYSTEM type to MessageType enum** (`app/models/message.py`)
2. ✅ **Created SystemMessageService** (`app/services/system_message_service.py`)
3. ✅ **Created database migration** (`alembic/versions/20251125_1600-add_system_message_type.py`)
4. ✅ **Updated add_members method** in `ConversationService` to create and broadcast system messages

## 🔧 Remaining Implementation Steps

### 1. Run Database Migration

```bash
cd /home/aiofficer/Workspace/tms-server
alembic upgrade head
```

### 2. Update Remaining ConversationService Methods

Add system message creation to these methods in `app/services/conversation_service.py`:

#### A. `remove_member` method (line ~599-618)

Add after line 597 (`await self.db.commit()`):

```python
        # Create system message for member removal
        try:
            from app.models.user import User
            from app.services.system_message_service import SystemMessageService
            from sqlalchemy import select
            import logging
            logger = logging.getLogger(__name__)

            # Get actor and removed user
            result = await self.db.execute(select(User).where(User.id == user_id))
            actor = result.scalar_one_or_none()

            result = await self.db.execute(select(User).where(User.id == member_id))
            removed_user = result.scalar_one_or_none()

            if actor and removed_user:
                system_msg = await SystemMessageService.create_member_removed_message(
                    db=self.db,
                    conversation_id=conversation_id,
                    actor=actor,
                    removed_user=removed_user
                )

                # Broadcast as regular message
                message_dict = {
                    'id': str(system_msg.id),
                    'conversationId': str(system_msg.conversation_id),
                    'senderId': str(system_msg.sender_id),
                    'content': system_msg.content,
                    'type': system_msg.type.value,
                    'status': 'sent',
                    'metadata': system_msg.metadata_json,
                    'isEdited': system_msg.is_edited,
                    'createdAt': system_msg.created_at.isoformat()
                }

                await connection_manager.broadcast_new_message(
                    conversation_id=conversation_id,
                    message_data=message_dict
                )

                logger.info(f"✅ Created and broadcasted system message for member_removed event")
        except Exception as e:
            logger.error(f"Failed to create system message for member_removed: {e}", exc_info=True)
```

#### B. `leave_conversation` method (line ~620-663)

Add after the `await self.member_repo.remove_member()` call:

```python
        # Create system message for member left
        try:
            from app.core.websocket import connection_manager
            from app.models.user import User
            from app.services.system_message_service import SystemMessageService
            from sqlalchemy import select
            import logging
            logger = logging.getLogger(__name__)

            # Get leaving user
            result = await self.db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if user:
                system_msg = await SystemMessageService.create_member_left_message(
                    db=self.db,
                    conversation_id=conversation_id,
                    user=user
                )

                # Broadcast as regular message
                message_dict = {
                    'id': str(system_msg.id),
                    'conversationId': str(system_msg.conversation_id),
                    'senderId': str(system_msg.sender_id),
                    'content': system_msg.content,
                    'type': system_msg.type.value,
                    'status': 'sent',
                    'metadata': system_msg.metadata_json,
                    'isEdited': system_msg.is_edited,
                    'createdAt': system_msg.created_at.isoformat()
                }

                await connection_manager.broadcast_new_message(
                    conversation_id=conversation_id,
                    message_data=message_dict
                )

                logger.info(f"✅ Created and broadcasted system message for member_left event")
        except Exception as e:
            logger.error(f"Failed to create system message for member_left: {e}", exc_info=True)
```

#### C. `update_conversation` method (line ~358-411)

Add before the final `await connection_manager.broadcast_conversation_updated()` call (around line 397):

```python
            # Create system message for conversation update
            try:
                from app.models.user import User
                from app.services.system_message_service import SystemMessageService
                from sqlalchemy import select

                # Get actor
                result = await self.db.execute(select(User).where(User.id == user_id))
                actor = result.scalar_one_or_none()

                if actor:
                    updates_dict = {}
                    if name is not None:
                        updates_dict['name'] = name
                    if avatar_url is not None:
                        updates_dict['avatar_url'] = avatar_url

                    system_msg = await SystemMessageService.create_conversation_updated_message(
                        db=self.db,
                        conversation_id=conversation_id,
                        actor=actor,
                        updates=updates_dict
                    )

                    # Broadcast as regular message
                    message_dict = {
                        'id': str(system_msg.id),
                        'conversationId': str(system_msg.conversation_id),
                        'senderId': str(system_msg.sender_id),
                        'content': system_msg.content,
                        'type': system_msg.type.value,
                        'status': 'sent',
                        'metadata': system_msg.metadata_json,
                        'isEdited': system_msg.is_edited,
                        'createdAt': system_msg.created_at.isoformat()
                    }

                    await connection_manager.broadcast_new_message(
                        conversation_id=conversation_id,
                        message_data=message_dict
                    )

                    logger.info(f"✅ Created and broadcasted system message for conversation_updated event")
            except Exception as e:
                logger.error(f"Failed to create system message for conversation_updated: {e}", exc_info=True)
```

### 3. Update Message Deletion Endpoint

In `app/api/v1/messages.py`, find the `delete_message` endpoint and add system message creation when `scope == 'everyone'`.

Find the section that broadcasts `message_deleted` event and add:

```python
            # Create system message for deletion (when deleting for everyone)
            if scope == 'everyone':
                try:
                    from app.models.user import User
                    from app.services.system_message_service import SystemMessageService
                    from sqlalchemy import select
                    import logging
                    logger = logging.getLogger(__name__)

                    # Get actor
                    result = await db.execute(select(User).where(User.id == user.id))
                    actor = result.scalar_one_or_none()

                    if actor:
                        system_msg = await SystemMessageService.create_message_deleted_message(
                            db=db,
                            conversation_id=message.conversation_id,
                            actor=actor
                        )

                        # Broadcast as regular message
                        message_dict = {
                            'id': str(system_msg.id),
                            'conversationId': str(system_msg.conversation_id),
                            'senderId': str(system_msg.sender_id),
                            'content': system_msg.content,
                            'type': system_msg.type.value,
                            'status': 'sent',
                            'metadata': system_msg.metadata_json,
                            'isEdited': system_msg.is_edited,
                            'createdAt': system_msg.created_at.isoformat()
                        }

                        await connection_manager.broadcast_new_message(
                            conversation_id=message.conversation_id,
                            message_data=message_dict
                        )

                        logger.info(f"✅ Created and broadcasted system message for message_deleted event")
                except Exception as e:
                    logger.error(f"Failed to create system message for message_deleted: {e}", exc_info=True)
```

## 📱 Client-Side Cleanup

Once backend is deployed and tested:

### Remove Client-Side System Message Generation

1. **Remove hook usage** in `src/app/(main)/layout.tsx`:
   ```typescript
   // Delete this line:
   useGlobalConversationEvents(); // ❌ Remove
   ```

2. **Delete files**:
   ```bash
   rm src/features/conversations/hooks/useGlobalConversationEvents.ts
   rm src/features/messaging/utils/systemMessages.ts
   ```

3. **Keep**:
   - `MessageBubble.tsx` - Already handles SYSTEM type correctly ✅
   - Type definitions in `types/message.ts` ✅
   - Event types in `types/conversation.ts` ✅

## ✅ Testing Checklist

After implementation:

- [ ] Add member to group → system message appears and persists after refresh
- [ ] Remove member from group → system message appears and persists
- [ ] Leave group → system message appears and persists
- [ ] Change group name → system message appears and persists
- [ ] Delete message for everyone → system message appears and persists
- [ ] System messages included in message history pagination
- [ ] System messages appear even when not viewing the conversation
- [ ] Multiple clients see consistent system messages
- [ ] System messages searchable in conversation

## 🔒 Security Notes

- ✅ Server validates all actions before creating system messages
- ✅ Message content is server-controlled (prevents spoofing)
- ✅ Full audit trail in database
- ✅ No client-side manipulation possible
- ✅ Permissions checked before any system message creation

## 📊 Database Impact

- **New enum value**: `SYSTEM` added to `message_type` enum
- **No schema changes**: Uses existing Message table structure
- **Storage**: Minimal - system messages are text-only
- **Performance**: No impact - same indexes apply

## 🚀 Deployment Strategy

**Zero-Downtime Deployment:**

1. Deploy backend with system message creation
2. Keep client's `useGlobalConversationEvents` for 24-48 hours
3. Both work simultaneously (harmless duplication)
4. Deploy client cleanup after verification
5. Done ✅

**Benefits:**
- No breaking changes
- Gradual rollout
- Easy rollback if needed
- Users see immediate improvement

## 📝 Example System Messages

```
John Doe added Jane Smith, Bob Johnson to the group
John Doe removed Jane Smith
Jane Smith left the group
John Doe changed the group name to "Project Team"
John Doe changed the group photo
John Doe deleted a message
```

All messages follow Messenger's style: clear, concise, and informative.
