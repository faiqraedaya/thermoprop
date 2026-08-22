@echo off
setlocal

rem ---------------------------------------------------------------------------
rem ThermoProp build script
rem
rem Uses uv to sync the dev group (which provides PyInstaller) and then runs
rem PyInstaller against build.spec. Produces dist\ThermoProp\ThermoProp.exe
rem (directory bundle, not onefile).
rem ---------------------------------------------------------------------------

pushd "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
    echo [build] uv not found on PATH. Install from https://docs.astral.sh/uv/.
    popd
    exit /b 1
)

echo [build] Syncing dev dependencies with uv...
uv sync --group dev || goto :error

echo [build] Cleaning previous build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [build] Running PyInstaller...
uv run --group dev pyinstaller --noconfirm --clean build.spec || goto :error

echo.
echo [build] Done. Output: dist\ThermoProp\ThermoProp.exe
popd
endlocal
exit /b 0

:error
echo [build] FAILED.
popd
endlocal
exit /b 1
