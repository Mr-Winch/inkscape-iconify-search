@echo off
setlocal
title Install Icon Importer for Inkscape
set "SOURCE=%~dp0"
set "TARGET=%APPDATA%\inkscape\extensions\icon-importer"
set "PACKAGE_SOURCE=%SOURCE%icon_importer"
set "PACKAGE_TARGET=%TARGET%\icon_importer"

echo.
echo  Icon Importer for Inkscape
echo  --------------------------
echo.

for %%F in (icon_importer.inx icon_importer_extension.py iconify_search_icon.svg README.md LICENSE) do if not exist "%SOURCE%%%F" goto missing
for %%F in (__init__.py api.py cache.py favorites.py models.py svg.py ui.py) do if not exist "%PACKAGE_SOURCE%\%%F" goto missing

if not exist "%TARGET%" mkdir "%TARGET%"
if errorlevel 1 goto failed
if not exist "%PACKAGE_TARGET%" mkdir "%PACKAGE_TARGET%"
if errorlevel 1 goto failed

for %%F in (icon_importer.inx icon_importer_extension.py iconify_search_icon.svg README.md LICENSE) do (
  copy /Y "%SOURCE%%%F" "%TARGET%\%%F" >nul
  if errorlevel 1 goto failed
)

for %%F in (__init__.py api.py cache.py favorites.py models.py svg.py ui.py) do (
  copy /Y "%PACKAGE_SOURCE%\%%F" "%PACKAGE_TARGET%\%%F" >nul
  if errorlevel 1 goto failed
)

echo  Installation complete!
echo.
echo  1. Close every Inkscape window.
echo  2. Reopen Inkscape.
echo  3. Choose Extensions ^> Import/Export ^> Search and Import Icons.
echo.
echo  Installed in:
echo  %TARGET%
echo.
pause
exit /b 0

:missing
echo  INSTALLATION COULD NOT START
echo.
echo  Extract the ZIP before running this installer and keep all Icon Importer files together.
echo.
pause
exit /b 1

:failed
echo  INSTALLATION FAILED
echo.
echo  Windows could not copy Icon Importer to:
echo  %TARGET%
echo.
pause
exit /b 1
