@echo off
REM Genera bin\DespertadorEmas.exe (requiere: pip install pyinstaller)
cd /d "%~dp0"
pyinstaller --noconfirm --clean --onefile --windowed --name DespertadorEmas --add-data "sonidos;sonidos" despertador.py
if errorlevel 1 exit /b 1
if not exist bin mkdir bin
copy /Y "dist\DespertadorEmas.exe" "bin\DespertadorEmas.exe"
echo.
echo Listo: bin\DespertadorEmas.exe
