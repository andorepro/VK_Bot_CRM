#!/bin/bash
# SSL Certificate Generator for Local Development
# Generates self-signed certificates for HTTPS

CERT_DIR="${1:-./certs}"

echo "🔐 Generating SSL certificates in $CERT_DIR..."

# Create directory if it doesn't exist
mkdir -p "$CERT_DIR"

# Generate private key and certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$CERT_DIR/key.pem" \
    -out "$CERT_DIR/cert.pem" \
    -subj "/C=RU/ST=Moscow/L=Moscow/O=LaserWorkshop/OU=IT/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:192.168.1.1"

echo "✅ Certificates generated successfully!"
echo "📁 Certificate: $CERT_DIR/cert.pem"
echo "🔑 Key: $CERT_DIR/key.pem"
echo ""
echo "⚠️  For browsers to trust these certificates:"
echo "   - Chrome/Edge: Go to chrome://net-internals/#dns and clear cache"
echo "   - Firefox: Import cert.pem in Settings > Privacy & Security > View Certificates"
echo "   - Or simply click 'Advanced' > 'Proceed to localhost (unsafe)' when warned"
