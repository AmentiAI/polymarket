#!/bin/bash
# Quick launcher for Polymarket Sniper Bot + UI

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  🎯 POLYMARKET SNIPER - QUICK START                        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if dependencies installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 18+"
    exit 1
fi

# Check if credentials exist
if [ ! -f "polymarket_creds.json" ]; then
    echo "⚠️  polymarket_creds.json not found!"
    echo ""
    echo "Creating from template..."
    cp polymarket_creds.json.example polymarket_creds.json
    echo ""
    echo "📝 Please edit polymarket_creds.json with your Polymarket API keys"
    echo "   Then run this script again."
    exit 1
fi

# Install Python deps if needed
if ! python3 -c "import flask" 2>/dev/null; then
    echo "📦 Installing Python dependencies..."
    pip3 install -r requirements.txt
fi

# Install UI deps if needed
if [ ! -d "ui/node_modules" ]; then
    echo "📦 Installing UI dependencies..."
    cd ui
    npm install
    cd ..
fi

echo ""
echo "✅ All dependencies ready!"
echo ""
echo "Starting services..."
echo ""

# Start web server in background
echo "🌐 Starting WebSocket server..."
python3 web_server.py > server.log 2>&1 &
WEB_SERVER_PID=$!
echo "   PID: $WEB_SERVER_PID"
echo "   Logs: tail -f server.log"

# Wait for server to start
sleep 3

# Start UI
echo ""
echo "🎨 Starting UI..."
cd ui
npm run dev &
UI_PID=$!
cd ..
echo "   PID: $UI_PID"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  ✅ READY TO TRADE                                         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "🌐 Web Server:  http://localhost:8080"
echo "🎯 Trading UI:  http://localhost:3000/live"
echo ""
echo "📊 To check stats:"
echo "   python3 analyze_stats.py"
echo ""
echo "🛑 To stop all services:"
echo "   kill $WEB_SERVER_PID $UI_PID"
echo "   Or just press Ctrl+C"
echo ""
echo "💡 Open your browser to http://localhost:3000/live"
echo "   Then click START BOT to begin trading!"
echo ""

# Keep script running
trap "kill $WEB_SERVER_PID $UI_PID 2>/dev/null; exit" INT TERM

# Wait for UI to be ready
echo "⏳ Waiting for UI to start..."
sleep 10

# Try to open browser (Mac/Linux)
if command -v open &> /dev/null; then
    open http://localhost:3000/live
elif command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:3000/live
fi

echo ""
echo "Press Ctrl+C to stop all services"
wait
