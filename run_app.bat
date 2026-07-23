@echo off
cd /d "%~dp0"

set PORT=8600

echo Starting AI Investor Panel...
start "AI Investor Panel (server)" cmd /c "py -3 -m streamlit run app.py --server.port %PORT% --server.headless true"

timeout /t 5 /nobreak >nul

start "" http://localhost:%PORT%

echo.
echo The app should now be open in your browser at http://localhost:%PORT%
echo A separate "AI Investor Panel (server)" window is running the app.
echo Close that window (or press Ctrl+C in it) to stop the server.
