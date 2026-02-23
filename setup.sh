#!/bin/bash
# Quick setup script for Polymarket Sniper Bot

echo "🎯 Polymarket Sniper Bot - Setup"
echo "================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+ first."
    exit 1
fi

echo "✅ Python found: $(python3 --version)"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt

echo ""
echo "📝 Setting up credentials..."

# Check if credentials exist
if [ -f "polymarket_creds.json" ]; then
    echo "✅ polymarket_creds.json already exists"
else
    echo "⚠️  Creating polymarket_creds.json from template..."
    cp polymarket_creds.json.example polymarket_creds.json
    echo ""
    echo "🔑 IMPORTANT: Edit polymarket_creds.json with your actual credentials!"
    echo "   1. Go to https://polymarket.com"
    echo "   2. Create API keys (Settings → API Keys)"
    echo "   3. Export your wallet private key"
    echo "   4. Fill in polymarket_creds.json"
    echo ""
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit polymarket_creds.json with your credentials"
echo "  2. Fund your Polymarket wallet with USDC"
echo "  3. Run bot: python3 sniper_bot.py"
echo ""
echo "📊 To check stats: python3 analyze_stats.py"
echo ""
echo "🎯 BONUS: Web Trading UI"
echo "   cd ui && ./setup.sh"
echo "   npm run dev"
echo "   Open http://localhost:3000"
echo ""
echo "Good luck! 🎯"
