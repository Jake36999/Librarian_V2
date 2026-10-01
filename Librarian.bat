@echo off
setlocal
REM Opens the Librarian. The desktop shortcut runs "Librarian.bat --pick": the library
REM picker first. Without --pick, a library at or above this folder opens; else the picker.
REM This window is the Librarian's server: closing it stops the Librarian.
REM Runs this folder's own environment (made by Setup.bat), else resource-librarian on PATH.
set "OPENBLAS_NUM_THREADS=1"
set "OMP_NUM_THREADS=1"
set "HERE=%~dp0"
if exist "%HERE%.venv\Scripts\python.exe" (
    "%HERE%.venv\Scripts\python.exe" -m resource_librarian app --open --port 0 %*
) else (
    where resource-librarian >nul 2>nul
    if errorlevel 1 (
        echo The Librarian isn't set up in %HERE% yet: run Setup.bat there first.
        pause
        exit /b 1
    )
    resource-librarian app --open --port 0 %*
)
if errorlevel 1 (
    echo.
    echo The Librarian stopped with an error ^(see above^).
    pause
)
