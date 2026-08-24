@echo off
setlocal
title Uninstall Iconify Search 0.6.3 for Inkscape
set "TARGET=%APPDATA%\inkscape\extensions\icon-importer"
set "EXPECTED=%APPDATA%\inkscape\extensions\icon-importer"

for %%I in ("%TARGET%") do set "RESOLVED_TARGET=%%~fI"
for %%I in ("%EXPECTED%") do set "RESOLVED_EXPECTED=%%~fI"

echo.
echo  Uninstall Iconify Search 0.6.3 for Inkscape
echo  -------------------------------------------
echo.

if /I not "%RESOLVED_TARGET%"=="%RESOLVED_EXPECTED%" goto unsafe
if not exist "%TARGET%" goto not_installed

echo  This will remove:
echo  %TARGET%
echo.
set /P "CONFIRM=  Type Y to continue: "
if /I not "%CONFIRM%"=="Y" goto cancelled

rmdir /S /Q "%TARGET%"
if exist "%TARGET%" goto failed

echo.
echo  Uninstallation complete.
echo  Close every Inkscape window and reopen Inkscape.
echo.
pause
exit /b 0

:not_installed
echo  Iconify Search is not installed in the expected user extension folder.
echo.
pause
exit /b 0

:cancelled
echo.
echo  Uninstallation cancelled.
echo.
pause
exit /b 0

:unsafe
echo  UNINSTALLATION STOPPED
echo.
echo  The resolved target did not match the expected Inkscape extension folder.
echo.
pause
exit /b 1

:failed
echo  UNINSTALLATION FAILED
echo.
echo  Close Inkscape and remove this folder manually:
echo  %TARGET%
echo.
pause
exit /b 1
