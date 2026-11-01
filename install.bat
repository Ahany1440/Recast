@echo off
rem Sets up Recast: Python packages, right-click menu, Send To and Start Menu.
rem Keep this folder where it is afterwards: the menu entries point here. Moved it? Run this again.
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Setting up, this takes a few minutes the first time...
    python -m venv .venv || goto :nopython
)
rem Offline copies of the Python packages (installers\python-packages) are used when present.
if exist "installers\python-packages" (
    ".venv\Scripts\python.exe" -m pip install -q --no-index --find-links installers\python-packages -r requirements.txt || goto :failed
) else (
    ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || goto :failed
)
".venv\Scripts\python.exe" shell.py install || goto :failed
echo.
echo Done. Right-click any file and choose "Recast",
echo or open "Recast" from the Start Menu.
echo If the entry isn't in the new Windows 11 menu yet, restart Explorer or sign out and in.
pause
exit /b

:nopython
echo Python was not found. Install it with:  winget install Python.Python.3.13
pause
exit /b 1

:failed
echo Setup failed. See the messages above.
pause
exit /b 1
