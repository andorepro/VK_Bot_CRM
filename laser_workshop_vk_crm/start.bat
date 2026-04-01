@echo off
REM Quick Start Script for Windows
REM Laser Workshop VK CRM

echo 🚀 Starting Laser Workshop VK CRM...

REM Check if .env exists
if not exist ".env" (
    echo ⚠️  .env file not found. Creating from template...
    copy .env.example .env
    echo Please edit .env with your settings before running again.
    pause
    exit /b 1
)

REM Check if certificates exist
if not exist "certs\cert.pem" (
    echo 🔐 SSL certificates not found. Generating...
    bash generate_certs.sh certs
)

REM Install dependencies if needed
pip install -r requirements.txt --quiet

REM Run the application
echo 🌐 Starting server on https://localhost:5000
python app.py

pause
