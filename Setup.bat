@echo off
REM Sets up this copy of the Librarian (scripts\setup.ps1): its own Python environment,
REM the package with its extras, and a desktop shortcut that opens the library picker.
REM Arguments pass through, e.g.  Setup.bat -Extras "mcp,pdf,embed,dev" -NoShortcut
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1" %*
set "CODE=%ERRORLEVEL%"
if "%~1"=="" pause
exit /b %CODE%
