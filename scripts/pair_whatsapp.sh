#!/usr/bin/env bash
# Pair WhatsApp with Hermes Agent on Matrix box
set -euo pipefail

PORT="${WHATSAPP_BRIDGE_PORT:-3010}"
SESSION_DIR="${HOME}/.hermes/whatsapp/session"
BRIDGE_DIR="${HOME}/.hermes/hermes-agent/scripts/whatsapp-bridge"

mkdir -p "$SESSION_DIR"
cd "$BRIDGE_DIR"

echo "========================================================================"
echo "📱 Launching WhatsApp pairing bridge on port ${PORT}..."
echo "1. Open WhatsApp on your phone"
echo "2. Go to: Settings -> Linked Devices -> Link a Device"
echo "3. Scan the QR code below:"
echo "========================================================================"

node bridge.js --port "$PORT" --pair-only --session "$SESSION_DIR"
