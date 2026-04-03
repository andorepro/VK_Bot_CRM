#!/bin/bash
# Скрипт генерации самоподписанных SSL сертификатов для локальной сети

set -e

CERT_DIR="${1:-certs}"
DAYS_VALID=3650
CN="laser-workshop.local"

echo "🔐 Генерация SSL сертификатов..."
echo "   Директория: $CERT_DIR"
echo "   Срок действия: $DAYS_VALID дней"
echo "   Common Name: $CN"

# Создаем директорию
mkdir -p "$CERT_DIR"

# Генерируем приватный ключ и сертификат
openssl req -x509 -nodes -days $DAYS_VALID -newkey rsa:2048 \
    -keyout "$CERT_DIR/server.key" \
    -out "$CERT_DIR/server.crt" \
    -subj "/C=RU/ST=Moscow/L=Moscow/O=LaserWorkshop/OU=IT/CN=$CN" \
    -addext "subjectAltName=DNS:$CN,DNS:localhost,IP:127.0.0.1,IP:192.168.1.100"

echo ""
echo "✅ Сертификаты успешно созданы:"
echo "   - $CERT_DIR/server.crt (публичный сертификат)"
echo "   - $CERT_DIR/server.key (приватный ключ)"
echo ""
echo "📋 Для добавления сертификата в доверенные:"
echo ""
echo "   Windows (запустить от администратора):"
echo "   certutil -addstore -f root \"$CERT_DIR/server.crt\""
echo ""
echo "   macOS:"
echo "   sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain \"$CERT_DIR/server.crt\""
echo ""
echo "   Linux (Ubuntu/Debian):"
echo "   sudo cp \"$CERT_DIR/server.crt\" /usr/local/share/ca-certificates/"
echo "   sudo update-ca-certificates"
echo ""
echo "🌐 После установки сертификата приложение будет доступно по HTTPS"
