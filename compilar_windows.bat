@echo off
REM Compila ControlAceites.exe (requiere Python 3.10 o superior instalado desde python.org)
cd /d "%~dp0"
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -c "from control_aceites.tema import guardar_ico; guardar_ico('icono.ico')"
pyinstaller --noconfirm --onefile --windowed --icon icono.ico --name ControlAceites main.py
echo.
echo Listo: el ejecutable quedo en la carpeta dist\ControlAceites.exe
pause
