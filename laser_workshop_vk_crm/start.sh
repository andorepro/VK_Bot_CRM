#!/bin/bash
# Quick Start Script for Linux/Raspberry Pi
# Laser Workshop VK CRM

echo "🚀 Starting Laser Workshop VK CRM..."

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp .env.example .env
    echo "Please edit .env with your settings before running again."
    exit 1
fi

# Check if certificates exist
if [ ! -f "certs/cert.pem" ]; then
    echo "🔐 SSL certificates not found. Generating..."
    bash generate_certs.sh certs
fi

# Install dependencies if needed
pip install -r requirements.txt --quiet

# Run the application
echo "🌐 Starting server on https://localhost:5000"
python3 app.py
