@echo off
REM Simple Django dev server WITHOUT WebSocket
REM Use this if Daphne has issues

echo.
echo =============================================
echo   Chat App - Django Dev Server (HTTP Only)
echo =============================================
echo.

echo Checking Python installation...
python --version

echo.
echo Setting Django Settings...
set DJANGO_SETTINGS_MODULE=chat_app.settings

echo.
echo Starting Django Development Server...
echo Server will run on: http://127.0.0.1:8000
echo Admin Panel: http://127.0.0.1:8000/admin/
echo API Root: http://127.0.0.1:8000/api/
echo.
echo Press Ctrl+C to stop the server
echo.

python manage.py runserver 0.0.0.0:8000

pause
