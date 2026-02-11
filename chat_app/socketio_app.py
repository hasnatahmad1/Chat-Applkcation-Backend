"""
Socket.IO Server Configuration for Django Chat App
"""
import socketio
import jwt
from django.conf import settings
from django.contrib.auth.models import User
from channels.db import database_sync_to_async
from chat.models import CustomUser, Group, GroupMessage, DirectMessage
import asyncio
import logging

logger = logging.getLogger(__name__)

# Create Socket.IO server with CORS support
sio = socketio.AsyncServer(
    async_mode='aiohttp',
    cors_allowed_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    logger=True,
    engineio_logger=True
)


# Helper functions to interact with Django ORM
@database_sync_to_async
def get_user_from_token(token):
    """Extract user from JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
        user = User.objects.get(id=user_id)
        return user
    except Exception as e:
        logger.error(f"Token validation failed: {e}")
        return None


@database_sync_to_async
def update_user_status(user, is_online):
    """Update user online status"""
    try:
        custom_user, created = CustomUser.objects.get_or_create(user=user)
        custom_user.is_online = is_online
        custom_user.save()
        return True
    except Exception as e:
        logger.error(f"Error updating user status: {e}")
        return False


@database_sync_to_async
def check_group_membership(user, group_id):
    """Check if user is member of group"""
    try:
        group = Group.objects.get(id=group_id)
        return group.members.filter(id=user.id).exists()
    except Exception as e:
        logger.error(f"Error checking group membership: {e}")
        return False


@database_sync_to_async
def save_group_message(user, group_id, message_text):
    """Save group message to database"""
    try:
        group = Group.objects.get(id=group_id)
        message = GroupMessage.objects.create(
            group=group,
            sender=user,
            message=message_text
        )
        return {
            'id': message.id,
            'group': group.id,
            'sender': user.username,
            'sender_id': user.id,
            'message': message.message,
            'created_at': message.created_at.isoformat(),
        }
    except Exception as e:
        logger.error(f"Error saving group message: {e}")
        return None


@database_sync_to_async
def save_direct_message(sender, receiver_id, message_text):
    """Save direct message to database"""
    try:
        receiver = User.objects.get(id=receiver_id)
        message = DirectMessage.objects.create(
            sender=sender,
            receiver=receiver,
            message=message_text
        )
        return {
            'id': message.id,
            'sender': sender.username,
            'sender_id': sender.id,
            'receiver_id': receiver.id,
            'message': message.message,
            'created_at': message.created_at.isoformat(),
        }
    except Exception as e:
        logger.error(f"Error saving direct message: {e}")
        return None


@database_sync_to_async
def get_online_users_ids():
    """Get list of online user IDs"""
    try:
        # Get all online users
        online_users = CustomUser.objects.filter(
            is_online=True).values_list('user__id', flat=True)
        return list(online_users)
    except Exception as e:
        logger.error(f"Error getting online users: {e}")
        return []


# Socket.IO Event Handlers
@sio.event
async def connect(sid, environ):
    """Handle client connection"""
    logger.info(f"Client connecting: {sid}")

    # Get token from query parameters
    query_string = environ.get('QUERY_STRING', '')
    token = None

    for param in query_string.split('&'):
        if param.startswith('token='):
            token = param.split('=')[1]
            break

    if not token:
        logger.warning(f"Connection rejected - no token: {sid}")
        return False

    # Authenticate user
    user = await get_user_from_token(token)
    if not user:
        logger.warning(f"Connection rejected - invalid token: {sid}")
        return False

    # Store user info in session
    async with sio.session(sid) as session:
        session['user_id'] = user.id
        session['username'] = user.username

    # Update user online status
    await update_user_status(user, True)

    # Get all online users and send to client
    online_user_ids = await get_online_users_ids()
    await sio.emit('online_users_list', {
        'user_ids': online_user_ids
    }, room=sid)

    # Broadcast status change
    await sio.emit('user_status_change', {
        'user_id': user.id,
        'is_online': True
    })

    logger.info(f"Client connected: {sid} (User: {user.username})")
    return True


@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    try:
        logger.info(f"🔌 SID {sid} disconnected")
        async with sio.session(sid) as session:
            user_id = session.get('user_id')
            username = session.get('username')
            logger.info(
                f"Session data for {sid}: user_id={user_id}, username={username}")

        if user_id:
            user = await database_sync_to_async(User.objects.get)(id=user_id)
            await update_user_status(user, False)

            logger.info(f"📢 Broadcasting offline for user {user_id}")
            # Broadcast status change
            await sio.emit('user_status_change', {
                'user_id': user_id,
                'is_online': False
            })
        else:
            logger.warning(f"⚠️ No user_id found for SID {sid} in disconnect")
    except Exception as e:
        logger.error(f"❌ Error in disconnect: {e}")


@sio.event
async def join_group(sid, data):
    """Join a group chat room"""
    try:
        async with sio.session(sid) as session:
            user_id = session.get('user_id')
            username = session.get('username')

        group_id = data.get('group_id')

        if not group_id or not user_id:
            await sio.emit('error', {'message': 'Invalid request'}, room=sid)
            return

        # Get user and check membership
        user = await database_sync_to_async(User.objects.get)(id=user_id)
        is_member = await check_group_membership(user, group_id)

        if not is_member:
            await sio.emit('error', {'message': 'Not a member of this group'}, room=sid)
            return

        # Join the room
        room = f'group_{group_id}'
        sio.enter_room(sid, room)

        logger.info(f"User {username} joined group {group_id}")

        # Notify others in the group
        await sio.emit('user_joined', {
            'user_id': user_id,
            'username': username,
            'message': f'{username} joined the chat'
        }, room=room, skip_sid=sid)

        # Confirm to the user
        await sio.emit('joined_group', {
            'group_id': group_id,
            'message': 'Successfully joined group'
        }, room=sid)

    except Exception as e:
        logger.error(f"Error joining group: {e}")
        await sio.emit('error', {'message': 'Failed to join group'}, room=sid)


@sio.event
async def leave_group(sid, data):
    """Leave a group chat room"""
    try:
        async with sio.session(sid) as session:
            user_id = session.get('user_id')
            username = session.get('username')

        group_id = data.get('group_id')

        if not group_id:
            return

        room = f'group_{group_id}'
        sio.leave_room(sid, room)

        logger.info(f"User {username} left group {group_id}")

        # Notify others
        await sio.emit('user_left', {
            'user_id': user_id,
            'username': username,
            'message': f'{username} left the chat'
        }, room=room)

    except Exception as e:
        logger.error(f"Error leaving group: {e}")


@sio.event
async def send_group_message(sid, data):
    """Send message to group"""
    try:
        async with sio.session(sid) as session:
            user_id = session.get('user_id')
            username = session.get('username')

        group_id = data.get('group_id')
        message_text = data.get('message')

        if not group_id or not message_text or not user_id:
            await sio.emit('error', {'message': 'Invalid message data'}, room=sid)
            return

        # Get user and verify membership
        user = await database_sync_to_async(User.objects.get)(id=user_id)
        is_member = await check_group_membership(user, group_id)

        if not is_member:
            await sio.emit('error', {'message': 'Not authorized'}, room=sid)
            return

        # Save message to database
        message_data = await save_group_message(user, group_id, message_text)

        if not message_data:
            await sio.emit('error', {'message': 'Failed to save message'}, room=sid)
            return

        # Broadcast to group room
        room = f'group_{group_id}'
        await sio.emit('group_message', message_data, room=room)

        logger.info(f"Group message sent: {username} -> Group {group_id}")

    except Exception as e:
        logger.error(f"Error sending group message: {e}")
        await sio.emit('error', {'message': 'Failed to send message'}, room=sid)


@sio.event
async def join_direct_chat(sid, data):
    """Join a direct chat room"""
    try:
        async with sio.session(sid) as session:
            user_id = session.get('user_id')
            username = session.get('username')

        other_user_id = data.get('user_id')

        if not other_user_id or not user_id:
            await sio.emit('error', {'message': 'Invalid request'}, room=sid)
            return

        # Create unique room name
        user_ids = sorted([user_id, int(other_user_id)])
        room = f'direct_{user_ids[0]}_{user_ids[1]}'

        sio.enter_room(sid, room)

        logger.info(
            f"User {username} joined direct chat with user {other_user_id}")

        await sio.emit('joined_direct_chat', {
            'other_user_id': other_user_id,
            'message': 'Successfully joined chat'
        }, room=sid)

    except Exception as e:
        logger.error(f"Error joining direct chat: {e}")
        await sio.emit('error', {'message': 'Failed to join chat'}, room=sid)


@sio.event
async def leave_direct_chat(sid, data):
    """Leave a direct chat room"""
    try:
        async with sio.session(sid) as session:
            user_id = session.get('user_id')

        other_user_id = data.get('user_id')

        if not other_user_id or not user_id:
            return

        user_ids = sorted([user_id, int(other_user_id)])
        room = f'direct_{user_ids[0]}_{user_ids[1]}'

        sio.leave_room(sid, room)

        logger.info(
            f"User {user_id} left direct chat with user {other_user_id}")

    except Exception as e:
        logger.error(f"Error leaving direct chat: {e}")


@sio.event
async def send_direct_message(sid, data):
    """Send direct message"""
    try:
        async with sio.session(sid) as session:
            user_id = session.get('user_id')
            username = session.get('username')

        receiver_id = data.get('receiver_id')
        message_text = data.get('message')

        if not receiver_id or not message_text or not user_id:
            await sio.emit('error', {'message': 'Invalid message data'}, room=sid)
            return

        # Get user
        user = await database_sync_to_async(User.objects.get)(id=user_id)

        # Save message
        message_data = await save_direct_message(user, receiver_id, message_text)

        if not message_data:
            await sio.emit('error', {'message': 'Failed to save message'}, room=sid)
            return

        # Send to both users
        user_ids = sorted([user_id, int(receiver_id)])
        room = f'direct_{user_ids[0]}_{user_ids[1]}'

        await sio.emit('direct_message', message_data, room=room)

        logger.info(f"Direct message sent: {username} -> User {receiver_id}")

    except Exception as e:
        logger.error(f"Error sending direct message: {e}")
        await sio.emit('error', {'message': 'Failed to send message'}, room=sid)


@sio.event
async def typing(sid, data):
    """Handle typing indicator"""
    try:
        async with sio.session(sid) as session:
            user_id = session.get('user_id')
            username = session.get('username')

        chat_type = data.get('type')  # 'group' or 'direct'
        chat_id = data.get('id')
        is_typing = data.get('is_typing', False)

        if chat_type == 'group':
            room = f'group_{chat_id}'
        else:
            user_ids = sorted([user_id, int(chat_id)])
            room = f'direct_{user_ids[0]}_{user_ids[1]}'

        await sio.emit('user_typing', {
            'user_id': user_id,
            'username': username,
            'is_typing': is_typing
        }, room=room, skip_sid=sid)

    except Exception as e:
        logger.error(f"Error handling typing: {e}")
