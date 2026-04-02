#!/bin/bash
# Генерация самоподписанных SSL сертификатов
CERT_DIR="${1:-certs}"
mkdir -p "$CERT_DIR"
echo "🔐 Генерация SSL сертификатов в $CERT_DIR..."
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "$CERT_DIR/key.pem" \
  -out "$CERT_DIR/cert.pem" \
  -subj "/C=RU/ST=Moscow/L=Moscow/O=LaserWorkshop/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
chmod 600 "$CERT_DIR/key.pem"
chmod 644 "$CERT_DIR/cert.pem"
echo "✅ Сертификаты созданы:"
echo "   - $CERT_DIR/cert.pem"
echo "   - $CERT_DIR/key.pem"