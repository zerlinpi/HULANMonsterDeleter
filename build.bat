@echo off
setlocal
cd /d %~dp0

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    exit /b 1
)

echo [1/5] Installing build dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo [2/5] Validating AI walk / point / kick pose assets...
python tools\validate_character_assets.py
if errorlevel 1 (
    echo.
    echo Generate the action images first with local ComfyUI:
    echo   python tools\comfyui_generate_poses.py --checkpoint "YOUR_CHECKPOINT.safetensors"
    exit /b 1
)

echo [3/5] Generating application icon from the embedded portrait...
python tools\make_icon.py
if errorlevel 1 exit /b 1

echo [4/5] Building MonsterDeleter.exe...
python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name MonsterDeleter ^
  --icon assets\generated\photo_character.ico ^
  --add-data "assets;assets" ^
  --hidden-import send2trash ^
  main.py
if errorlevel 1 exit /b 1

echo [5/5] Done.
echo EXE: %CD%\dist\MonsterDeleter.exe
endlocal
