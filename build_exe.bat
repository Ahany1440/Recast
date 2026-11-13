@echo off
rem Optional: builds dist\FileConverter\FileConverter.exe (no Python needed to run it).
rem LibreOffice, Pandoc, FFmpeg and Tesseract are NOT bundled: they must still be installed.
cd /d "%~dp0"
".venv\Scripts\python.exe" -m pip install -q pyinstaller || exit /b 1
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --name FileConverter ^
    --icon assets\icon.ico --add-data "assets;assets" ^
    --collect-submodules converters --hidden-import shell --hidden-import gui ^
    --collect-all tkinterdnd2 --collect-all sv_ttk --collect-all pdf2docx ^
    --collect-all pillow_heif --collect-all pymupdf ^
    gui_qt.pyw || exit /b 1
echo.
echo Built: dist\FileConverter\FileConverter.exe
echo Open it and switch on "Show in right-click menu" to point the menu at the .exe.
pause
