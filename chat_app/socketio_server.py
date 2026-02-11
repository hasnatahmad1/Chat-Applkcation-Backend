"""
Standalone Socket.IO Server for Django Chat App
Run this separately: python socketio_server.py
"""
import os
import django


# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chat_app.settings')
django.setup()

# Import Socket.IO app after Django setup
import socketio
from aiohttp import web
from chat_app.socketio_app import sio
# Create aiohttp application
app = web.Application()

# Attach Socket.IO
sio.attach(app)

# Add a simple health check route


async def health_check(request):
    return web.Response(text="Socket.IO Server Running")

app.router.add_get('/health', health_check)

if __name__ == '__main__':
    print("="*60)
    print("🚀 Socket.IO Server Starting...")
    print("="*60)
    print("📡 WebSocket URL: ws://127.0.0.1:8001")
    print("🌐 HTTP URL: http://127.0.0.1:8001")
    print("="*60)
    print("Press Ctrl+C to stop")
    print("="*60)

    web.run_app(app, host='127.0.0.1', port=8001)
