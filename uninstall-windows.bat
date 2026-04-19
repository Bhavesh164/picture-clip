@echo off
echo Uninstalling Picture Clipboard (Windows)...

:: 1. Force quit the app if running
echo Stopping any running instances...
taskkill /F /IM PictureClipboard.exe 2>nul
taskkill /F /IM "Picture Clipboard.exe" 2>nul

:: Give it a moment
timeout /t 2 /nobreak >nul

:: 2. Remove AppData and LocalAppData
echo Removing application data...
if exist "%APPDATA%\Picture Clipboard" rd /s /q "%APPDATA%\Picture Clipboard"
if exist "%APPDATA%\PictureClipboard" rd /s /q "%APPDATA%\PictureClipboard"
if exist "%LOCALAPPDATA%\Picture Clipboard" rd /s /q "%LOCALAPPDATA%\Picture Clipboard"
if exist "%LOCALAPPDATA%\PictureClipboard" rd /s /q "%LOCALAPPDATA%\PictureClipboard"

:: 3. Remove Registry keys for preferences (PySide6 usually uses registry on Windows)
echo Removing registry keys...
reg delete "HKCU\Software\Picture Clipboard" /f 2>nul
reg delete "HKCU\Software\PictureClipboard" /f 2>nul
:: Just in case residue from the previous Kilo organization is present
reg delete "HKCU\Software\Kilo" /f 2>nul

:: 4. Optional: Remove common installation directory
if exist "%PROGRAMFILES%\PictureClipboard" (
    echo Note: Removing from Program Files requires Administrator privileges.
    rmdir /s /q "%PROGRAMFILES%\PictureClipboard" 2>nul
)

echo Done! Picture Clipboard has been completely uninstalled from Windows.
pause
