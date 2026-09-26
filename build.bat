@echo off
setlocal enabledelayedexpansion

echo ============================================
echo  FFmpeg Toolkit - PyInstaller Build Script
echo ============================================
echo.

:: --- Step 1: Scan and enumerate Python files safely ---
echo Scanning current directory for Python scripts...
echo ---------------------------------------------------
set count=0
for /f "delims=" %%f in ('dir /b *.py') do (
    set /a count+=1
    set "script[!count!]=%%f"
    echo [!count!] %%f
)

:: Safe single-line check: Prevents crashing on path parentheses
if "%count%"=="0" echo ERROR: No Python scripts (*.py) found.& pause& exit /b 1
echo.

:select
set /p choice="Enter the number of the script to compile (1-%count%): "

:: Validate user selection
if not defined script[%choice%] (
    echo [INVALID] Selection out of range. Please try again.
    echo.
    goto select
)

:: Extract chosen script name and base filename safely
for /f "delims=" %%i in ("!script[%choice%]!") do (
    set "chosen_script=%%i"
    set "base_name=%%~ni"
)

echo.
echo Selected Script: !chosen_script!
echo Executable Target Name: !base_name!
echo ---------------------------------------------------
echo.

:: --- Stop any running process before building ---
echo Stopping any running !base_name!.exe process...

taskkill /f /im "!base_name!.exe" >nul 2>&1
if errorlevel 1 echo   No running !base_name!.exe process found.
if not errorlevel 1 echo   Stopped running !base_name!.exe process.
echo.

:: --- Install required packages ---
echo [1/4] Installing dependencies...
pip install pyinstaller customtkinter Pillow
if %ERRORLEVEL% neq 0 echo ERROR: pip install failed. Make sure Python is on PATH.& pause& exit /b 1
echo.

:: --- Clean old build artifacts ---
echo [2/4] Cleaning old build artifacts and regenerating icon...
if exist "build" rmdir /s /q "build" && echo   Removed: build\
:: If python script exists, execute it
if exist "generate_ico.py" python generate_ico.py
echo.

:: --- Run PyInstaller ---
echo [3/4] Running PyInstaller...
python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "!base_name!" ^
    --icon="app_icon.ico" ^
    --collect-data customtkinter ^
    "!chosen_script!"

if %ERRORLEVEL% neq 0 goto build_failed
echo.

:: --- Done ---
echo [4/4] Build complete!
echo.
echo  Output: dist\!base_name!.exe
echo.
echo  To distribute:
echo    1. Copy dist\!base_name!.exe to your target folder.
echo    2. Place ffmpeg.exe in the SAME folder as !base_name!.exe.
echo    3. Double-click !base_name!.exe to run.
echo.
echo ============================================
if exist "ffmpeg.exe" copy ffmpeg.exe .\dist >nul
if exist "ffprobe.exe" copy ffprobe.exe .\dist >nul
goto end

:build_failed
echo.
echo ERROR: PyInstaller build failed. See output above.
pause
exit /b 1

:end
pause
