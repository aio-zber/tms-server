"""
WebSocket manager for real-time messaging.
Handles WebSocket connections, rooms, and message broadcasting.
"""
import asyncio
import logging
from typing import Dict, Set, Optional, Any
from uuid import UUID

import socketio
from fastapi import FastAPI

from app.config import settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    WebSocket connection manager using Socket.IO.

    Manages WebSocket connections, rooms, and message broadcasting
    for real-time messaging features.
    """

    def __init__(self):
        """Initialize the connection manager."""
        logger.info("Initializing ConnectionManager with WebSocket-only mode")
        logger.info(f"CORS allowed origins: {settings.allowed_origins}")
        logger.info(f"CORS allowed origins type: {type(settings.allowed_origins)}")
        logger.info(f"Debug mode: {settings.debug}")
        logger.info(f"Heartbeat interval: {settings.ws_heartbeat_interval}")

        try:
            # Prepare CORS origins - python-socketio expects list or "*"
            # Convert comma-separated string to list
            cors_origins = settings.get_allowed_origins_list() if settings.allowed_origins else ["*"]
            logger.info(f"Prepared CORS origins for Socket.IO: {cors_origins}")

            # Create async Socket.IO server
            # Note: Railway requires WebSocket-only mode (no polling)
            # Engine.IO configuration is done via environment variables or server params
            self.sio = socketio.AsyncServer(
                async_mode='asgi',
                cors_allowed_origins=cors_origins,
                logger=settings.debug,
                engineio_logger=settings.debug,
                ping_timeout=settings.ws_heartbeat_interval,
                ping_interval=settings.ws_heartbeat_interval // 2,
                # Critical: These control Engine.IO transport layer
                # But python-socketio 5.12.0 doesn't support these in AsyncServer
                # They must be configured in the ASGI wrapper or client-side
            )

            logger.info("Socket.IO server initialized successfully")
            logger.info(f"WebSocket endpoint: /ws/socket.io/ (mount point: /ws, socketio_path: socket.io)")
        except Exception as e:
            logger.error(f"Failed to initialize Socket.IO server: {type(e).__name__}: {str(e)}")
            logger.error(f"Full error:", exc_info=True)
            raise

        # Track connections: {sid: user_id}
        self.connections: Dict[str, UUID] = {}

        # Track user sessions: {user_id: set of sids}
        self.user_sessions: Dict[UUID, Set[str]] = {}

        # Track conversation rooms: {conversation_id: set of sids}
        self.conversation_rooms: Dict[UUID, Set[str]] = {}

        # Setup event handlers
        self._setup_handlers()

    def _setup_handlers(self):
        """Setup Socket.IO event handlers."""

        @self.sio.event
        async def connect(sid, environ, auth):
            """
            Handle client connection.

            Client should provide auth token in handshake.
            """
            logger.info(f"Client attempting to connect: {sid}")

            # Extract auth token from handshake
            token = auth.get('token') if auth else None

            if not token:
                logger.warning(f"Connection rejected - no token: {sid}")
                return False

            try:
                # Validate token and get user
                from app.core.security import decode_nextauth_token
                from app.core.tms_client import tms_client

                logger.info(f"Attempting to decode token for sid: {sid}")
                logger.info(f"Token (first 20 chars): {token[:20]}...")

                try:
                    token_payload = decode_nextauth_token(token)
                    logger.info(f"Token payload: {token_payload}")
                except Exception as decode_error:
                    logger.error(f"Token decode failed: {type(decode_error).__name__}: {str(decode_error)}")
                    logger.error(f"Full error details: {decode_error}", exc_info=True)
                    raise  # Re-raise to be caught by outer exception handler

                tms_user_id = token_payload.get('id')  # NextAuth token contains 'id' as TMS user ID

                if not tms_user_id:
                    logger.warning(f"Connection rejected - invalid token payload (no id): {sid}")
                    logger.warning(f"Token payload keys: {list(token_payload.keys())}")
                    return False

                # Get local user ID
                from app.core.database import AsyncSessionLocal
                from app.models.user import User
                from sqlalchemy import select

                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(User).where(User.tms_user_id == tms_user_id)
                    )
                    user = result.scalar_one_or_none()

                    if not user:
                        logger.warning(f"Connection rejected - user not found: {sid}")
                        return False

                    # Store connection
                    self.connections[sid] = user.id

                    # Track user session
                    if user.id not in self.user_sessions:
                        self.user_sessions[user.id] = set()
                    self.user_sessions[user.id].add(sid)

                    logger.info(f"Client connected: {sid} (user: {user.id})")

                    # Emit user online status
                    await self.sio.emit('user_online', {
                        'user_id': str(user.id),
                        'timestamp': str(asyncio.get_event_loop().time())
                    }, skip_sid=sid)

                    # Update presence cache
                    from app.core.cache import set_user_presence
                    await set_user_presence(str(user.id), 'online')

                    return True

            except Exception as e:
                logger.error(f"Connection error: {type(e).__name__}: {str(e)}")
                logger.error(f"Full connection error details:", exc_info=True)
                return False

        @self.sio.event
        async def disconnect(sid):
            """Handle client disconnection."""
            user_id = self.connections.get(sid)

            if user_id:
                # Remove from user sessions
                if user_id in self.user_sessions:
                    self.user_sessions[user_id].discard(sid)
                    if not self.user_sessions[user_id]:
                        del self.user_sessions[user_id]

                        # User fully disconnected (no more sessions)
                        await self.sio.emit('user_offline', {
                            'user_id': str(user_id),
                            'timestamp': str(asyncio.get_event_loop().time())
                        })

                        # Update presence cache
                        from app.core.cache import set_user_presence
                        await set_user_presence(str(user_id), 'offline')

                # Remove from conversation rooms
                rooms_left = []
                for conv_id, sids in list(self.conversation_rooms.items()):
                    if sid in sids:
                        rooms_left.append(str(conv_id))
                        sids.discard(sid)
                        logger.info(f"[disconnect] Removed {sid} from conversation room: {conv_id}")
                    if not sids:
                        del self.conversation_rooms[conv_id]
                        logger.info(f"[disconnect] Conversation room {conv_id} is now empty")

                # Remove connection
                del self.connections[sid]

                logger.info(f"[disconnect] Client disconnected: {sid} (user: {user_id})")
                logger.info(f"[disconnect] User left {len(rooms_left)} conversation rooms: {rooms_left}")

        @self.sio.event
        async def join_conversation(sid, data):
            """
            Join a conversation room.

            Expected data: {'conversation_id': 'uuid'}
            """
            try:
                logger.info(f"[join_conversation] Received data: {data}")
                logger.info(f"[join_conversation] SID: {sid}")

                conversation_id = UUID(data['conversation_id'])
                logger.info(f"[join_conversation] Parsed conversation_id: {conversation_id}")

                user_id = self.connections.get(sid)
                logger.info(f"[join_conversation] User ID from connection: {user_id}")

                if not user_id:
                    logger.warning(f"[join_conversation] User not authenticated - sid: {sid}")
                    await self.sio.emit('error', {
                        'message': 'Unauthorized'
                    }, to=sid)
                    return

                # Verify user is member of conversation
                from app.core.database import AsyncSessionLocal
                from app.models.conversation import ConversationMember
                from sqlalchemy import select

                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(ConversationMember).where(
                            ConversationMember.conversation_id == conversation_id,
                            ConversationMember.user_id == user_id
                        )
                    )
                    member = result.scalar_one_or_none()
                    logger.info(f"[join_conversation] ConversationMember found: {member is not None}")

                    if not member:
                        logger.warning(f"[join_conversation] User {user_id} not a member of conversation {conversation_id}")
                        await self.sio.emit('error', {
                            'message': 'Not a member of this conversation'
                        }, to=sid)
                        return

                # Join Socket.IO room
                room_name = f"conversation:{conversation_id}"
                logger.info(f"[join_conversation] Joining Socket.IO room: {room_name}")
                logger.info(f"[join_conversation] SID being added: {sid}")
                
                await self.sio.enter_room(sid, room_name)
                
                # VERIFY the room actually exists in Socket.IO manager
                try:
                    # Access rooms from the default namespace ('/')
                    namespace = '/'
                    if hasattr(self.sio.manager, 'rooms'):
                        # For AsyncManager, rooms are stored per namespace
                        if namespace in self.sio.manager.rooms:
                            namespace_rooms = self.sio.manager.rooms[namespace]
                            if room_name in namespace_rooms:
                                logger.info(f"[join_conversation] ✅ VERIFIED: Room '{room_name}' exists in Socket.IO manager")
                                logger.info(f"[join_conversation] SIDs in Socket.IO room: {namespace_rooms[room_name]}")
                            else:
                                logger.error(f"[join_conversation] ❌ PROBLEM: Room '{room_name}' NOT in Socket.IO manager after enter_room()!")
                                logger.error(f"[join_conversation] Available rooms in namespace: {list(namespace_rooms.keys())[:10]}")  # Show first 10
                        else:
                            logger.error(f"[join_conversation] Namespace '/' not found in manager.rooms")
                            logger.error(f"[join_conversation] Available namespaces: {list(self.sio.manager.rooms.keys())}")
                    else:
                        logger.warning(f"[join_conversation] Cannot access manager.rooms - using alternative verification")
                except Exception as e:
                    logger.error(f"[join_conversation] Error checking Socket.IO rooms: {e}", exc_info=True)

                # Track in conversation rooms
                if conversation_id not in self.conversation_rooms:
                    self.conversation_rooms[conversation_id] = set()
                self.conversation_rooms[conversation_id].add(sid)

                logger.info(f"[join_conversation] SUCCESS: User {user_id} joined conversation {conversation_id}")
                logger.info(f"[join_conversation] Active rooms for conversation {conversation_id}: {len(self.conversation_rooms[conversation_id])} members")
                logger.info(f"[join_conversation] Our internal tracking - SIDs: {self.conversation_rooms[conversation_id]}")

                await self.sio.emit('joined_conversation', {
                    'conversation_id': str(conversation_id)
                }, to=sid)

            except Exception as e:
                logger.error(f"Error joining conversation: {e}")
                await self.sio.emit('error', {
                    'message': 'Failed to join conversation'
                }, to=sid)

        @self.sio.event
        async def leave_conversation(sid, data):
            """
            Leave a conversation room.

            Expected data: {'conversation_id': 'uuid'}
            """
            try:
                conversation_id = UUID(data['conversation_id'])

                # Leave Socket.IO room
                await self.sio.leave_room(sid, f"conversation:{conversation_id}")

                # Remove from tracking
                if conversation_id in self.conversation_rooms:
                    self.conversation_rooms[conversation_id].discard(sid)
                    if not self.conversation_rooms[conversation_id]:
                        del self.conversation_rooms[conversation_id]

                await self.sio.emit('left_conversation', {
                    'conversation_id': str(conversation_id)
                }, to=sid)

            except Exception as e:
                logger.error(f"Error leaving conversation: {e}")

        @self.sio.event
        async def typing_start(sid, data):
            """
            User started typing.

            Expected data: {'conversation_id': 'uuid'}
            """
            try:
                conversation_id = data['conversation_id']
                user_id = self.connections.get(sid)

                if user_id:
                    await self.sio.emit('user_typing', {
                        'conversation_id': conversation_id,
                        'user_id': str(user_id),
                        'is_typing': True
                    }, room=f"conversation:{conversation_id}", skip_sid=sid)

            except Exception as e:
                logger.error(f"Error in typing_start: {e}")

        @self.sio.event
        async def typing_stop(sid, data):
            """
            User stopped typing.

            Expected data: {'conversation_id': 'uuid'}
            """
            try:
                conversation_id = data['conversation_id']
                user_id = self.connections.get(sid)

                if user_id:
                    await self.sio.emit('user_typing', {
                        'conversation_id': conversation_id,
                        'user_id': str(user_id),
                        'is_typing': False
                    }, room=f"conversation:{conversation_id}", skip_sid=sid)

            except Exception as e:
                logger.error(f"Error in typing_stop: {e}")

    async def broadcast_new_message(
        self,
        conversation_id: UUID,
        message_data: Dict[str, Any],
        sender_sid: Optional[str] = None
    ):
        """
        Broadcast a new message to conversation members.

        Args:
            conversation_id: Conversation UUID
            message_data: Message data to broadcast
            sender_sid: Optional sender SID to skip
        """
        room = f"conversation:{conversation_id}"
        room_members = self.conversation_rooms.get(conversation_id, set())

        logger.info(f"[broadcast_new_message] Broadcasting to room: {room}")
        logger.info(f"[broadcast_new_message] Active members in room: {len(room_members)}")
        logger.info(f"[broadcast_new_message] Message ID: {message_data.get('id')}")
        logger.info(f"[broadcast_new_message] Sender ID: {message_data.get('sender_id')}")

        # Log all Socket.IO rooms and their members for debugging
        try:
            namespace = '/'
            logger.info(f"[broadcast_new_message] Checking Socket.IO manager...")
            logger.info(f"[broadcast_new_message] Manager type: {type(self.sio.manager)}")
            logger.info(f"[broadcast_new_message] Has 'rooms' attr: {hasattr(self.sio.manager, 'rooms')}")
            
            if hasattr(self.sio.manager, 'rooms'):
                logger.info(f"[broadcast_new_message] manager.rooms type: {type(self.sio.manager.rooms)}")
                logger.info(f"[broadcast_new_message] manager.rooms content: {self.sio.manager.rooms}")
                logger.info(f"[broadcast_new_message] Namespaces in manager.rooms: {list(self.sio.manager.rooms.keys()) if self.sio.manager.rooms else 'None'}")
                
                if namespace in self.sio.manager.rooms:
                    namespace_rooms = self.sio.manager.rooms[namespace]
                    logger.info(f"[broadcast_new_message] namespace_rooms type: {type(namespace_rooms)}")
                    if namespace_rooms:
                        logger.info(f"[broadcast_new_message] Total Socket.IO rooms in namespace: {len(namespace_rooms)}")
                        logger.info(f"[broadcast_new_message] Sample rooms: {list(namespace_rooms.keys())[:5]}")
                        
                        if room in namespace_rooms:
                            logger.info(f"[broadcast_new_message] ✅ Room '{room}' EXISTS in Socket.IO manager")
                            logger.info(f"[broadcast_new_message] SIDs in target room '{room}': {namespace_rooms[room]}")
                        else:
                            logger.warning(f"[broadcast_new_message] ⚠️  Room '{room}' does NOT exist in Socket.IO manager!")
                            logger.warning(f"[broadcast_new_message] Searching for similar rooms...")
                            matching_rooms = [r for r in namespace_rooms.keys() if 'conversation:' in str(r)]
                            logger.warning(f"[broadcast_new_message] Found {len(matching_rooms)} conversation rooms: {matching_rooms[:3]}")
                    else:
                        logger.error(f"[broadcast_new_message] namespace_rooms is None or empty!")
                else:
                    logger.error(f"[broadcast_new_message] Namespace '/' not found in manager.rooms!")
                    logger.error(f"[broadcast_new_message] Available namespaces: {list(self.sio.manager.rooms.keys())}")
            else:
                logger.error(f"[broadcast_new_message] Socket.IO manager has no 'rooms' attribute!")
        except Exception as e:
            logger.error(f"[broadcast_new_message] Error checking rooms: {e}", exc_info=True)
        
        # Broadcast the message
        await self.sio.emit('new_message', message_data, room=room, skip_sid=sender_sid)
        logger.info(f"[broadcast_new_message] ✅ Message emitted to Socket.IO room: {room}")
        
        # Verify our internal tracking matches Socket.IO
        if len(room_members) == 0:
            logger.warning(f"[broadcast_new_message] ⚠️  WARNING: No members in our internal tracking for {room}!")
            logger.warning(f"[broadcast_new_message] This message may not be received by anyone!")

    async def broadcast_message_edited(
        self,
        conversation_id: UUID,
        message_data: Dict[str, Any]
    ):
        """
        Broadcast message edit to conversation members.

        Args:
            conversation_id: Conversation UUID
            message_data: Updated message data
        """
        room = f"conversation:{conversation_id}"
        await self.sio.emit('message_edited', message_data, room=room)

    async def broadcast_message_deleted(
        self,
        conversation_id: UUID,
        message_id: UUID
    ):
        """
        Broadcast message deletion to conversation members.

        Args:
            conversation_id: Conversation UUID
            message_id: Deleted message UUID
        """
        room = f"conversation:{conversation_id}"
        await self.sio.emit('message_deleted', {
            'conversation_id': str(conversation_id),
            'message_id': str(message_id)
        }, room=room)

    async def broadcast_message_status(
        self,
        conversation_id: UUID,
        message_id: UUID,
        user_id: UUID,
        status: str
    ):
        """
        Broadcast message status update.

        Args:
            conversation_id: Conversation UUID
            message_id: Message UUID
            user_id: User UUID
            status: Status (sent, delivered, read)
        """
        room = f"conversation:{conversation_id}"
        await self.sio.emit('message_status', {
            'message_id': str(message_id),
            'user_id': str(user_id),
            'status': status
        }, room=room)

    async def broadcast_reaction_added(
        self,
        conversation_id: UUID,
        message_id: UUID,
        reaction_data: Dict[str, Any]
    ):
        """
        Broadcast reaction added to conversation members.

        Args:
            conversation_id: Conversation UUID
            message_id: Message UUID
            reaction_data: Reaction data
        """
        room = f"conversation:{conversation_id}"
        await self.sio.emit('reaction_added', {
            'message_id': str(message_id),
            'reaction': reaction_data
        }, room=room)

    async def broadcast_reaction_removed(
        self,
        conversation_id: UUID,
        message_id: UUID,
        user_id: UUID,
        emoji: str
    ):
        """
        Broadcast reaction removed to conversation members.

        Args:
            conversation_id: Conversation UUID
            message_id: Message UUID
            user_id: User UUID
            emoji: Removed emoji
        """
        room = f"conversation:{conversation_id}"
        await self.sio.emit('reaction_removed', {
            'message_id': str(message_id),
            'user_id': str(user_id),
            'emoji': emoji
        }, room=room)

    def get_asgi_app(self, fastapi_app):
        """
        Get the ASGI app for Socket.IO wrapping FastAPI.

        Args:
            fastapi_app: FastAPI application instance

        Returns:
            Socket.IO ASGI app with FastAPI wrapped inside

        Critical: According to python-socketio docs, correct pattern is:
        - app = socketio.ASGIApp(sio, other_asgi_app)
        - Socket.IO wraps FastAPI, not the other way around
        - Client connects to: /socket.io/?EIO=4&transport=websocket
        - socketio_path defaults to 'socket.io' (correct)

        Note: python-socketio 5.12.0 ASGIApp doesn't support engineio_options.
        WebSocket-only mode is enforced client-side via Socket.IO client config:
        - transports: ['websocket']
        - upgrade: false
        """
        return socketio.ASGIApp(
            self.sio,
            fastapi_app  # Pass FastAPI app as positional argument
            # Note: socketio_path defaults to 'socket.io' - don't specify explicitly
            # Letting it use default ensures proper routing of non-Socket.IO requests
        )


# Global connection manager instance
connection_manager = ConnectionManager()
