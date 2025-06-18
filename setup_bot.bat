@echo off
setlocal

REM Set version and installer name
set PYTHON_VERSION=3.12.4
set PYTHON_INSTALLER=python-%PYTHON_VERSION%-amd64.exe
set PYTHON_DOWNLOAD_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/%PYTHON_INSTALLER%

REM Check if Python 3.12.4 is already installed
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python not found. Downloading Python %PYTHON_VERSION%...
    curl -O %PYTHON_DOWNLOAD_URL%
    echo Installing Python...
    start /wait %PYTHON_INSTALLER% /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    del %PYTHON_INSTALLER%
)

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv

REM Activate venv and install dependencies
call venv\Scripts\activate
echo Installing requirements...
pip install --upgrade pip
pip install -r requirements.txt

REM Create .env file with placeholder token
if not exist .env (
    echo Creating .env file...
    echo DISCORD_TOKEN= > .env
)

REM Create run_bot.bat
echo Creating run_bot.bat...
(
    echo @echo off
    echo call venv\Scripts\activate
    echo python bot.py
) > run_bot.bat

echo.
echo ✅ Setup complete!
echo 🔑 Please open .env and paste your actual Discord token after DISCORD_TOKEN=
echo ▶ Use run_bot.bat to launch your bot.
pause

REM Self-delete this setup script
del "%~f0"
