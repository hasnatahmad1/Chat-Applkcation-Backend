"""
ASGI config for chat_app project.
It exposes the ASGI callable as a module-level variable named ``application``.
"""

from chat.routing import websocket_urlpatterns
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from channels.security.websocket import AllowedHostsOriginValidator
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
import os
import django
import logging

# Setup Django settings and apps
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chat_app.settings')
django.setup()


logger = logging.getLogger(__name__)

django_asgi_app = get_asgi_application()


class TokenAuthMiddleware:
    """
    Custom middleware to extract JWT token from Authorization header
    and authenticate WebSocket connections
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        # Get authorization header
        headers = dict(scope.get('headers', []))
        auth_header = headers.get(b'authorization', b'').decode()

        scope['user'] = AnonymousUser()

        # Try to authenticate using JWT token
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]  # Remove 'Bearer ' prefix
            try:
                access_token = AccessToken(token)
                scope['user'] = await self.get_user(access_token['user_id'])
            except Exception as e:
                logger.error(f"WebSocket authentication failed: {e}")
                scope['user'] = AnonymousUser()

        await self.inner(scope, receive, send)

    @database_sync_to_async
    def get_user(self, user_id):
        from django.contrib.auth.models import User
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return AnonymousUser()


application = ProtocolTypeRouter({
    # Django's ASGI application to handle traditional HTTP requests
    "http": django_asgi_app,

    # WebSocket chat handler with custom JWT token auth
    "websocket": AllowedHostsOriginValidator(
        TokenAuthMiddleware(
            URLRouter(
                websocket_urlpatterns
            )
        )
    ),
})
