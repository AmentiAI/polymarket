#!/bin/bash
# Quick setup script for Polymarket Sniper UI

echo "🎯 Polymarket Sniper UI - Setup"
echo "================================"
echo ""

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 18+ first."
    echo "   Visit: https://nodejs.org"
    exit 1
fi

echo "✅ Node found: $(node --version)"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
npm install

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Run: npm run dev"
echo "  2. Open: http://localhost:3000"
echo "  3. Toggle DEMO/LIVE mode in top-right"
echo ""
echo "For live mode, connect to your Python bot WebSocket."
echo "See README.md for details."
echo ""
echo "Happy trading! 🎯"
