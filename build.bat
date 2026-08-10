@echo off
setlocal
cd /d %~dp0

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    exit /b 1
)

echo [1/4] Installing build dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo [2/4] Generating application icon from the embedded photo...
python tools\make_icon.py
if errorlevel 1 exit /b 1

echo [3/4] Building MonsterDeleter.exe...
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

echo [4/4] Done.
echo EXE: %CD%\dist\MonsterDeleter.exe
endlocal
