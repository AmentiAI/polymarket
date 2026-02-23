#!/bin/bash
# Start Candle Server (FastAPI port 8081)

cd "$(dirname "$0")"

echo "═══════════════════════════════════════════════════════════"
echo "  🧬 Polymarket Candle Server (DNA + 24 Signals)"
echo "  Port: 8081 | Framework: FastAPI + WebSocket"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Check Python dependencies
echo "Checking dependencies..."
if ! python3 -c "import uvicorn" 2>/dev/null; then
    echo "Installing uvicorn..."
    pip3 install uvicorn fastapi websockets
fi

# Start server
echo ""
echo "Starting candle server on http://localhost:8081"
echo "WebSocket: ws://localhost:8081/ws"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python3 candle_server.py
