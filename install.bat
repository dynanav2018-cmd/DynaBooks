@echo off
setlocal enabledelayedexpansion

:: ── Read tier config from build_config.json ─────────────────
set "APP_NAME=DynaBooks"
set "FOLDER_NAME=DynaBooks"
set "EXE_NAME=DynaBooks.exe"

set "CFG=%~dp0build_config.json"
if exist "!CFG!" (
    for /f "usebackq delims=" %%V in (`powershell -NoProfile -Command "try { (Get-Content '!CFG!' | ConvertFrom-Json).app_name } catch {}"`) do (
        if not "%%V"=="" set "APP_NAME=%%V"
    )
    for /f "usebackq delims=" %%V in (`powershell -NoProfile -Command "try { (Get-Content '!CFG!' | ConvertFrom-Json).dist_folder } catch {}"`) do (
        if not "%%V"=="" set "FOLDER_NAME=%%V"
    )
)

:: Derive EXE name: replace spaces with hyphens to match PyInstaller output
set "EXE_NAME=!APP_NAME: =-!.exe"

title !APP_NAME! Installer

echo.
echo  ========================================
echo       !APP_NAME! Installation
echo  ========================================
echo.

:: ── Detect Dropbox folder ──────────────────────────────────
set "DROPBOX_PATH="

:: Try Dropbox info.json (most reliable)
for %%F in ("%APPDATA%\Dropbox\info.json" "%LOCALAPPDATA%\Dropbox\info.json") do (
    if exist "%%~F" (
        for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "try { (Get-Content '%%~F' | ConvertFrom-Json).personal.path } catch {}"`) do (
            if not "%%A"=="" set "DROPBOX_PATH=%%A"
        )
    )
)

:: Fallback to common locations
if not defined DROPBOX_PATH (
    if exist "%USERPROFILE%\Dropbox" set "DROPBOX_PATH=%USERPROFILE%\Dropbox"
)
if not defined DROPBOX_PATH (
    if exist "D:\Dropbox" set "DROPBOX_PATH=D:\Dropbox"
)

:: ── Set default install directory ──────────────────────────
if defined DROPBOX_PATH (
    set "DEFAULT_DIR=!DROPBOX_PATH!\!FOLDER_NAME!"
    echo  Dropbox detected: !DROPBOX_PATH!
) else (
    set "DEFAULT_DIR=%USERPROFILE%\!FOLDER_NAME!"
    echo  Dropbox not detected. Using home directory.
)

echo.
echo  Default: !DEFAULT_DIR!
echo.
echo  Press Enter to accept the default, or
echo  type a different path (e.g. C:\MyApps\!FOLDER_NAME!)
echo.
set /p "INSTALL_DIR=  Install to [!DEFAULT_DIR!]: "
if "!INSTALL_DIR!"=="" set "INSTALL_DIR=!DEFAULT_DIR!"
echo.
echo  Installing to: !INSTALL_DIR!

:: ── Check for existing installation ────────────────────────
if exist "!INSTALL_DIR!\!EXE_NAME!" (
    echo.
    echo  Existing installation detected.
    echo  Your accounting data will be preserved.
    echo.
    choice /C YN /M "  Continue with update"
    if errorlevel 2 goto :cancel
)

:: ── Get source directory ───────────────────────────────────
set "SOURCE=%~dp0"
:: Remove trailing backslash
if "!SOURCE:~-1!"=="\" set "SOURCE=!SOURCE:~0,-1!"

if not exist "!SOURCE!\!EXE_NAME!" (
    echo.
    echo  ERROR: Cannot find !EXE_NAME! in the installer directory.
    echo  Make sure this installer is in the same folder as !EXE_NAME!.
    pause
    goto :eof
)

:: ── Create install directory ───────────────────────────────
if not exist "!INSTALL_DIR!" mkdir "!INSTALL_DIR!"

:: ── Copy application files ─────────────────────────────────
echo.
echo  Copying application files...

:: Copy EXE
copy /Y "!SOURCE!\!EXE_NAME!" "!INSTALL_DIR!\" >nul
if errorlevel 1 (
    echo  ERROR: Could not copy !EXE_NAME!
    echo  Make sure !APP_NAME! is not currently running.
    pause
    goto :eof
)

:: Copy _internal folder
echo  Copying runtime files (this may take a moment)...
xcopy /E /Y /I "!SOURCE!\_internal" "!INSTALL_DIR!\_internal" >nul
if errorlevel 1 (
    echo  WARNING: Some runtime files could not be copied.
)

:: ── Set up data directory ──────────────────────────────────
if not exist "!INSTALL_DIR!\data" (
    :: Check for bundled clean data (dist_data/)
    if exist "!SOURCE!\dist_data\dynabooks.db" (
        echo  Setting up default company (My Company)...
        xcopy /E /Y /I "!SOURCE!\dist_data" "!INSTALL_DIR!\data" >nul
        echo  Default company created. Rename it in Settings.
    ) else if exist "%LOCALAPPDATA%\DynaBooks\dynabooks.db" (
        :: Migrate from older local storage
        echo  Migrating existing data from local storage...
        xcopy /E /Y /I "%LOCALAPPDATA%\DynaBooks" "!INSTALL_DIR!\data" >nul
        echo  Data migrated successfully.
    ) else (
        echo  Creating empty data directory...
        mkdir "!INSTALL_DIR!\data"
    )
) else (
    echo  Existing data directory preserved.
)

:: ── Create desktop shortcut ────────────────────────────────
echo  Creating desktop shortcut...
powershell -NoProfile -Command ^
    "$ws = New-Object -ComObject WScript.Shell;" ^
    "$sc = $ws.CreateShortcut([System.IO.Path]::Combine($env:USERPROFILE, 'Desktop', '!APP_NAME!.lnk'));" ^
    "$sc.TargetPath = '!INSTALL_DIR!\!EXE_NAME!';" ^
    "$sc.WorkingDirectory = '!INSTALL_DIR!';" ^
    "$sc.Description = '!APP_NAME! Accounting';" ^
    "$sc.Save()"

:: ── Done ───────────────────────────────────────────────────
echo.
echo  ========================================
echo       Installation Complete!
echo  ========================================
echo.
echo  Installed to: !INSTALL_DIR!
echo  Desktop shortcut: !APP_NAME!.lnk
echo.
echo  A default company "My Company" has been
echo  created. Go to Settings to rename it.
echo.
echo  Data is stored in: !INSTALL_DIR!\data
echo  This folder syncs via Dropbox across all
echo  your computers.
echo.
echo  To install on another computer, copy this
echo  entire folder and run install.bat again.
echo.
pause
goto :eof

:cancel
echo.
echo  Installation cancelled.
pause
