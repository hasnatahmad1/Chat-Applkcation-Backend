"""
ASGI config for chat_app project.

This file wires Django's ASGI application and the Socket.IO server
into a single ASGI application so that **both HTTP and WebSocket
connections are served from the same process and port**.
"""

import os
import django
from django.core.asgi import get_asgi_application
from socketio import ASGIApp

# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chat_app.settings")
django.setup()

# Import the pre-configured Socket.IO server
from chat_app.socketio_app import sio

# Base Django ASGI application (handles normal HTTP views / DRF)
django_asgi_app = get_asgi_application()

# Wrap Django with Socket.IO's ASGI application.
# - HTTP & DRF stay available on the same host/port (e.g. 8000)
# - Socket.IO endpoints are exposed under the default `/socket.io` path
application = ASGIApp(sio, django_asgi_app)
