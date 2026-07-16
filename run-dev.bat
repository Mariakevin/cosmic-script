@echo off
echo ========================================
echo   Cosmic Script - Starting Dev Servers
echo ========================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo.
echo Press Ctrl+C to stop both servers.
echo.

:: Start backend in background
start "Cosmic Script Backend" cmd /c "cd /d %~dp0 && uvicorn cosmic_script.web.app:app --reload --port 8000"

:: Wait a moment for backend to start
timeout /t 2 /nobreak >nul

:: Start frontend in foreground
cd /d "%~dp0frontend"
npm run dev
