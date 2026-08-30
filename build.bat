@echo off
setlocal

echo ============================================
echo  FFmpeg Toolkit - PyInstaller Build Script
echo ============================================
echo.

REM --- Install required packages ---
echo [1/4] Installing dependencies...
pip install pyinstaller customtkinter Pillow
if %ERRORLEVEL% neq 0 (
    echo ERROR: pip install failed. Make sure Python is on PATH.
    pause
    exit /b 1
)
echo.

REM --- Clean old build artifacts ---
echo [2/4] Cleaning old build artifacts...
if exist "build" (
    rmdir /s /q "build"
    echo   Removed: build\
)
if exist "dist" (
    rmdir /s /q "dist"
    echo   Removed: dist\
)
echo.

REM --- Run PyInstaller ---
echo [3/4] Running PyInstaller...
python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "FFmpeg_Toolkit" ^
    --icon="app_icon.ico" ^
    --collect-data customtkinter ^
    ffmpeg_toolkit.py

if %ERRORLEVEL% neq 0 (
    echo ERROR: PyInstaller build failed. See output above.
    pause
    exit /b 1
)
echo.

REM --- Done ---
echo [4/4] Build complete!
echo.
echo  Output: dist\FFmpeg_Toolkit.exe
echo.
REM Place icon_source.jpg and ffmpeg.exe in the same folder as FFmpeg_Toolkit.exe
echo  To distribute:
echo    1. Copy dist\FFmpeg_Toolkit.exe to your target folder.
echo    2. Place ffmpeg.exe in the SAME folder as FFmpeg_Toolkit.exe.
echo    3. Place icon_source.jpg in the SAME folder (for the welcome splash).
echo    4. Double-click FFmpeg_Toolkit.exe to run.
echo.
echo ============================================
pause
