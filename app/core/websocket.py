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
            cors_origins = settings.allowed_origins if isinstance(settings.allowed_origins, list) else ["*"]
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
                for conv_id, sids in list(self.conversation_rooms.items()):
                    sids.discard(sid)
                    if not sids:
                        del self.conversation_rooms[conv_id]

                # Remove connection
                del self.connections[sid]

                logger.info(f"Client disconnected: {sid} (user: {user_id})")

        @self.sio.event
        async def join_conversation(sid, data):
            """
            Join a conversation room.

            Expected data: {'conversation_id': 'uuid'}
            """
            try:
                conversation_id = UUID(data['conversation_id'])
                user_id = self.connections.get(sid)

                if not user_id:
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

                    if not member:
                        await self.sio.emit('error', {
                            'message': 'Not a member of this conversation'
                        }, to=sid)
                        return

                # Join Socket.IO room
                await self.sio.enter_room(sid, f"conversation:{conversation_id}")

                # Track in conversation rooms
                if conversation_id not in self.conversation_rooms:
                    self.conversation_rooms[conversation_id] = set()
                self.conversation_rooms[conversation_id].add(sid)

                logger.info(f"User {user_id} joined conversation {conversation_id}")

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
        await self.sio.emit('new_message', message_data, room=room, skip_sid=sender_sid)

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
            other_asgi_app=fastapi_app,
            socketio_path='socket.io',  # Default Socket.IO path
        )


# Global connection manager instance
connection_manager = ConnectionManager()
