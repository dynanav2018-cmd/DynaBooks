@echo off
echo === DynaBooks Build Script ===
echo.

echo [1/3] Building frontend...
cd frontend
call npm run build
if %errorlevel% neq 0 (
    echo ERROR: Frontend build failed!
    exit /b 1
)
cd ..

echo.
echo [2/3] Running PyInstaller...
python -m PyInstaller dynabooks.spec --noconfirm --distpath "%TEMP%\dynabooks_dist" --workpath "%TEMP%\dynabooks_build"
if %errorlevel% neq 0 (
    echo ERROR: PyInstaller failed!
    exit /b 1
)

echo.
echo [3/3] Build complete!
echo Output: %TEMP%\dynabooks_dist\DynaBooks\DynaBooks.exe
echo.
pause
