@echo off
REM ============================================
REM Papa Ka TV Launcher (Windows)
REM Double-click this file to start Papa Ka TV!
REM ============================================

SET PORT=8080

echo.
echo ============================================
echo   Papa Ka TV - Starting up...
echo ============================================
echo.

REM Check if Python is available
where python >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    SET PYTHON=python
) ELSE (
    where python3 >nul 2>&1
    IF %ERRORLEVEL% EQU 0 (
        SET PYTHON=python3
    ) ELSE (
        echo.
        echo ============================================
        echo   Python is not installed!
        echo   Please install Python from:
        echo   https://python.org
        echo ============================================
        pause
        exit /b 1
    )
)

REM Refresh video IDs (news live streams + broken song IDs)
echo Refreshing video IDs (this may take a moment)...
%PYTHON% refresh_ids.py
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo WARNING: Video refresh had issues.
    echo Check refresh_log.txt for details.
    echo Starting app with existing video IDs...
    echo.
)

echo Starting Papa Ka TV server on port %PORT%...

REM Start the browser after a short delay (start opens default browser)
timeout /t 2 /nobreak >nul
start "" "http://localhost:%PORT%/index.html"

REM Start ngrok tunnel if available
where ngrok >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    echo.
    echo Starting ngrok tunnel...
    start /B ngrok http %PORT% --log=stdout >nul 2>&1
    timeout /t 4 /nobreak >nul
    echo.
    echo   ngrok is running. Check remote URL at:
    echo   http://127.0.0.1:4040
    echo   Share the https URL with Papa!
    echo.
) ELSE (
    echo.
    echo   ngrok not installed - skipping remote access
    echo   Install from: https://ngrok.com/download
    echo.
)

echo.
echo ============================================
echo   Papa Ka TV is running!
echo   Local: http://localhost:%PORT%/index.html
echo.
echo   To stop: close this window or press Ctrl+C
echo ============================================
echo.

REM Start Python HTTP server with no-cache headers (this blocks, keeping the window open)
REM When the user closes the command prompt window, the server dies
%PYTHON% -c "import http.server,socketserver;H=type('H',(http.server.SimpleHTTPRequestHandler,),{'end_headers':lambda s:(s.send_header('Cache-Control','no-cache, no-store, must-revalidate'),s.send_header('Pragma','no-cache'),s.send_header('Expires','0'),http.server.SimpleHTTPRequestHandler.end_headers(s))});socketserver.TCPServer(('', %PORT%), H).serve_forever()"
