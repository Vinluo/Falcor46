@echo off
:: Fetch the Amazon Lumberyard Bistro scene into external/assets/Bistro/.
:: License: CC-BY 4.0 — see https://developer.nvidia.com/orca/amazon-lumberyard-bistro
::
:: The download is a ~853 MB zip. Safe to re-run; skips download if zip exists,
:: skips extract if marker file is present.

setlocal
set REPO_ROOT=%~dp0..
set DEST_DIR=%REPO_ROOT%\external\assets\Bistro
set ZIP_PATH=%DEST_DIR%\Bistro_v5_2.zip
set MARKER=%DEST_DIR%\.extracted
set LANDING_URL=https://developer.nvidia.com/bistro

if not exist "%DEST_DIR%" mkdir "%DEST_DIR%"

if exist "%MARKER%" (
    echo [fetch_bistro] already extracted at %DEST_DIR% — nothing to do.
    exit /b 0
)

if not exist "%ZIP_PATH%" (
    echo [fetch_bistro] downloading Bistro_v5_2.zip ^(~853 MB^) ...
    curl -L --fail --progress-bar -o "%ZIP_PATH%" "%LANDING_URL%"
    if errorlevel 1 (
        echo [fetch_bistro] download failed.
        exit /b 1
    )
) else (
    echo [fetch_bistro] zip already present, skipping download.
)

echo [fetch_bistro] extracting ...
where tar >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    tar -xf "%ZIP_PATH%" -C "%DEST_DIR%"
) else (
    powershell -NoProfile -Command "Expand-Archive -LiteralPath '%ZIP_PATH%' -DestinationPath '%DEST_DIR%' -Force"
)
if errorlevel 1 (
    echo [fetch_bistro] extract failed.
    exit /b 1
)

echo done > "%MARKER%"
echo [fetch_bistro] ready at %DEST_DIR%
exit /b 0
