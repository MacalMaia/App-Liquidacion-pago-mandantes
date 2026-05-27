@echo off
setlocal

set APPDIR=%~dp0

if exist "%APPDIR%venv\Scripts\activate.bat" (
    call "%APPDIR%venv\Scripts\activate.bat"
    set PYTHON=%APPDIR%venv\Scripts\python.exe
) else (
    set PYTHON=python
)

"%PYTHON%" "%APPDIR%main.py"
pause

endlocal