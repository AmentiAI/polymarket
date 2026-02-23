# 🎯 Polymarket Sniper - Trading UI

Real-time trading interface for the Polymarket 5-min BTC sniper bot.

## Features

- **Live BTC Price** — Real-time price from Binance
- **Countdown Timer** — Next 5-min candle close
- **Snipe Signals** — LAST-SECOND and LATE snipes with confidence
- **Live Candle Chart** — TradingView-style 5-min BTC candlestick chart
- **Current Candle Metrics** — Body %, volatility, range
- **Polymarket Shares** — Live UP/DOWN share prices
- **Trade History** — All snipes with P&L tracking
- **Win Rate Stats** — Overall + by strategy type
- **Demo Mode** — Test UI without running the bot

## Quick Start

```bash
# Install dependencies
npm install

# Run dev server
npm run dev

# Open http://localhost:3000
```

## Demo Mode

The UI starts in **DEMO mode** by default — it generates fake data so you can see the interface without running the Python bot.

Toggle between DEMO/LIVE with the button in the top-right corner.

## Live Mode (Connect to Bot)

To connect to the actual Python sniper bot, you need to:

1. **Add WebSocket endpoint to the bot** (see below)
2. **Switch to LIVE mode** in the UI

### Adding WebSocket to the Bot

The bot currently doesn't expose a WebSocket endpoint. You'll need to add a simple Flask/FastAPI server:

```python
# Add to sniper_bot.py or create ws_server.py

from flask import Flask
from flask_sock import Sock
import json
import time

app = Flask(__name__)
sock = Sock(app)

# Global state
bot_state = {
    "running": False,
    "current_candle": None,
    "current_market": None,
    "secs_left": 300,
    "last_signal": None,
    "stats": {},
    "recent_trades": [],
    "candles": [],
}

@sock.route('/ws')
def ws(ws):
    """WebSocket endpoint — sends bot state every 500ms"""
    while True:
        ws.send(json.dumps(bot_state))
        time.sleep(0.5)

@app.route('/api/bot/status')
def bot_status():
    return {"running": bot_state["running"]}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
```

Then update the UI WebSocket URL in `app/page.tsx`:

```typescript
// Change from:
const ws = new WebSocket('ws://localhost:8080/ws');

// To your server:
const ws = new WebSocket('ws://YOUR_SERVER_IP:8080/ws');
```

## Data Format

The bot should send this JSON structure over WebSocket:

```json
{
  "running": true,
  "current_market": {
    "timestamp": 1740163200,
    "up_price": 0.62,
    "down_price": 0.38,
    "accepting_orders": true
  },
  "current_candle": {
    "open": 95420.50,
    "high": 95510.20,
    "low": 95380.10,
    "close": 95503.80,
    "body_pct": 63.8,
    "volatility": 0.11
  },
  "secs_left": 90,
  "last_signal": {
    "action": "SNIPE",
    "direction": "UP",
    "reason": "LATE: Clean green continuation (body $67, vol 0.11%)",
    "confidence": 72.4,
    "type": "LATE"
  },
  "stats": {
    "total": 24,
    "wins": 17,
    "losses": 7,
    "win_rate": 70.8,
    "pnl": 34.20,
    "avg_pnl": 1.43,
    "last_second_wr": 76.5,
    "late_wr": 68.2
  },
  "recent_trades": [
    {
      "trade_id": "a3f42b19",
      "timestamp": "2026-02-21T19:45:22Z",
      "direction": "UP",
      "type": "LATE",
      "reason": "LATE: Clean green continuation",
      "confidence": 72.4,
      "entry_price": 0.6150,
      "entry_cost": 10.05,
      "shares": 16.34,
      "status": "closed",
      "outcome": "WIN",
      "pnl": 6.29,
      "exit_price": 0.9950,
      "metrics": {
        "body_pct": 41.3,
        "body_usd": 67,
        "volatility": 0.11
      }
    }
  ],
  "candles": [
    {
      "time": 1740163200,
      "open": 95420.50,
      "high": 95510.20,
      "low": 95380.10,
      "close": 95503.80
    }
  ]
}
```

## Build for Production

```bash
# Build
npm run build

# Start production server
npm start

# Deploy to Vercel (optional)
npm i -g vercel
vercel
```

## Tech Stack

- **Next.js 15** — React framework
- **TypeScript** — Type safety
- **Tailwind CSS** — Styling
- **lightweight-charts** — TradingView-style charts
- **WebSocket** — Real-time data from Python bot

## Customization

### Colors

Edit `app/globals.css`:

```css
:root {
  --background: #0a0a14;  /* Dark background */
  --foreground: #e5e7eb;  /* Light text */
}
```

### Layout

All UI code is in `app/page.tsx` — single-file component for easy editing.

### Chart Settings

Chart config in `initChart()` function:

```typescript
const chart = createChart(chartContainerRef.current, {
  layout: {
    background: { color: '#0a0a14' },
    textColor: '#9ca3af',
  },
  // ... more settings
});
```

## Troubleshooting

### Chart not showing

Make sure `lightweight-charts` is installed:

```bash
npm install lightweight-charts
```

### WebSocket not connecting

1. Check Python bot is running on port 8080
2. Check firewall allows WebSocket connections
3. Look for errors in browser console (F12)

### Styles not loading

Make sure Tailwind is configured:

```bash
npm install -D tailwindcss postcss autoprefixer
```

## Screenshots

(Demo mode — shows what the UI looks like)

**Main Dashboard:**
- Top: BTC price, countdown timer, live signal
- Left: Current candle metrics, Polymarket shares, signal status
- Center: 5-min candlestick chart
- Bottom: Recent trades table with P&L

---

**Made for speed.** 🎯
