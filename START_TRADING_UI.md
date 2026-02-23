# 🎯 Start Trading with UI - Complete Guide

## Quick Start (3 Steps)

### Step 1: Install Dependencies (1 min)

```bash
# Python dependencies (bot + web server)
pip install -r requirements.txt

# UI dependencies (React + WebSocket)
cd ui
npm install
cd ..
```

### Step 2: Start Web Server (30 seconds)

```bash
# Terminal 1: Start the WebSocket server
python3 web_server.py
```

You should see:
```
══════════════════════════════════════════════════════════════════════
  🎯 POLYMARKET SNIPER - WEB SERVER
  WebSocket + REST API for UI control
══════════════════════════════════════════════════════════════════════

🌐 Starting server on http://0.0.0.0:8080
📡 WebSocket available at ws://localhost:8080/socket.io/
🎮 Control endpoints:
   POST /api/bot/start  - Start trading
   POST /api/bot/stop   - Stop trading
   GET  /api/bot/status - Check status
   GET  /api/stats      - Get statistics
   GET  /api/trades     - Get recent trades

💡 Open UI at: http://localhost:3000
```

### Step 3: Start UI (30 seconds)

```bash
# Terminal 2: Start the Next.js UI
cd ui
npm run dev
```

You should see:
```
  ▲ Next.js 15.1.0
  - Local:        http://localhost:3000
  - Network:      http://192.168.1.x:3000

 ✓ Ready in 2.1s
```

**Open your browser to: http://localhost:3000/live**

---

## Using the UI

### Main Dashboard

When you open http://localhost:3000/live, you'll see:

#### Header (Top Bar)
- **BTC Price** — Live price from current 5-min candle
- **Countdown Timer** — Time until candle close (color-coded)
  - Red: <30s (critical)
  - Yellow: 30-60s (warning)
  - White: >60s (normal)
- **Live Signal Badge** — Appears when snipe conditions met
  - Animated pulse effect
  - Shows: Type (LAST-SECOND/LATE), Direction (UP/DOWN), Confidence %
- **Stats Card** — Win/loss record, win rate, P&L
- **START/STOP BOT** — Click to control trading
- **Connection Status** — Green = live, Red = offline

#### Left Sidebar
1. **Current Candle**
   - Visual representation (body + wicks)
   - Direction (green/red)
   - Body size ($USD and % of range)
   - Volatility %
   - Range

2. **Polymarket Shares**
   - UP price (green panel)
   - DOWN price (red panel)
   - Market status (open/closed)

3. **Signal Status**
   - Current action (SNIPE / WAITING)
   - Signal reason
   - Confidence level
   - Metrics (body, volatility)

4. **Strategy Performance**
   - LAST-SECOND win rate
   - LATE win rate
   - Avg P&L per trade

#### Center Panel
- **Candlestick Chart** — TradingView-style 5-min BTC chart
- **Trade Markers** — Win (green ✓) / Loss (red ✗) on chart

#### Bottom Panel
- **Recent Trades Table** — Last 20 trades with:
  - Time
  - Type (LAST/LATE)
  - Direction (UP/DOWN)
  - Confidence %
  - Entry/Exit prices
  - P&L
  - Status (OPEN/WIN/LOSS)

---

## Trading Workflow

### 1. Configure Bot

Before starting, make sure you've configured your Polymarket credentials:

```bash
nano polymarket_creds.json
```

Fill in:
```json
{
  "api_key": "your_polymarket_api_key",
  "api_secret": "your_polymarket_api_secret",
  "api_passphrase": "your_polymarket_passphrase",
  "controller_key": "your_wallet_private_key",
  "polymarket_address": "your_wallet_address"
}
```

### 2. Fund Wallet

1. Go to https://polymarket.com
2. Deposit USDC (minimum $50 recommended)
3. Verify balance shows up in your wallet

### 3. Start Trading

1. **Open UI**: http://localhost:3000/live
2. **Check connection**: Green dot in top-right = server connected
3. **Click START BOT**: Big green button in header
4. **Watch for signals**: Bot analyzes every 500ms
5. **Auto-execution**: When snipe conditions met, bot trades automatically

### 4. Monitor Performance

Watch the UI in real-time:
- **Countdown timer** — Know when candle closes
- **Signal badge** — See when snipe fires
- **Trade table** — Track all executions
- **Stats card** — Monitor win rate & P&L

### 5. Stop Trading

**Click STOP BOT** when:
- Daily loss limit reached (>20% of bankroll)
- 5 consecutive losses
- You need a break
- Market conditions change

---

## Troubleshooting

### "Connection failed" error

**Problem:** UI can't connect to WebSocket server

**Solutions:**
1. Check web_server.py is running:
   ```bash
   # You should see "Starting server on http://0.0.0.0:8080"
   ```

2. Check port 8080 is not in use:
   ```bash
   lsof -i :8080  # Linux/Mac
   netstat -ano | findstr :8080  # Windows
   ```

3. Check firewall allows localhost:8080

### "Bot not starting" error

**Problem:** Click START BOT but nothing happens

**Solutions:**
1. Check polymarket_creds.json exists and has valid credentials
2. Check USDC balance in wallet
3. Check console output in web_server.py terminal for errors
4. Look for error banner at top of UI

### "No market" or "Waiting for data..."

**Problem:** UI shows no data

**Solutions:**
1. Wait 5-10 seconds for first data broadcast
2. Check Polymarket is operating (https://polymarket.com/event/btc-updown-5m)
3. Check Binance API is accessible (web_server.py logs)
4. Refresh the page

### Chart not showing

**Problem:** Blank chart area

**Solutions:**
1. Wait for first candle data (takes ~5-10s)
2. Check browser console for errors (F12)
3. Try refreshing the page

### Trades not executing

**Problem:** Signal fires but no trade appears

**Solutions:**
1. Check USDC balance sufficient ($10+ per trade)
2. Check Polymarket market accepting orders
3. Check share price < $0.85 (bot skips if too high)
4. Look at web_server.py logs for "Order failed" errors

---

## Advanced: Running on VPS

For 24/7 trading, deploy to a VPS:

### 1. Setup VPS

```bash
# SSH into VPS
ssh root@your-vps-ip

# Clone repo
git clone [your-repo]
cd polymarket-sniper

# Install dependencies
pip install -r requirements.txt
```

### 2. Run Web Server in Background

```bash
# Using nohup
nohup python3 web_server.py > server.log 2>&1 &

# Or using screen
screen -S sniper
python3 web_server.py
# Ctrl+A, D to detach

# Or using systemd (recommended)
sudo nano /etc/systemd/system/polymarket-sniper.service
```

Systemd service file:
```ini
[Unit]
Description=Polymarket Sniper Web Server
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/polymarket-sniper
ExecStart=/usr/bin/python3 web_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Start service:
```bash
sudo systemctl daemon-reload
sudo systemctl start polymarket-sniper
sudo systemctl enable polymarket-sniper
sudo systemctl status polymarket-sniper
```

### 3. Deploy UI (Optional)

If you want the UI accessible remotely:

```bash
cd ui
npm run build
npm start  # Production mode

# Or deploy to Vercel
npm i -g vercel
vercel
```

### 4. Access Remotely

**Option A: SSH Tunnel** (secure)
```bash
# On your laptop
ssh -L 8080:localhost:8080 -L 3000:localhost:3000 root@your-vps-ip

# Then open http://localhost:3000/live
```

**Option B: Public Access** (less secure)
- Edit web_server.py: Change `host='0.0.0.0'` to bind all interfaces
- Set up nginx reverse proxy
- Use HTTPS + authentication

---

## Environment Variables

Create `.env` file in `ui/` folder:

```bash
# WebSocket server URL
NEXT_PUBLIC_WS_URL=http://localhost:8080

# For production
NEXT_PUBLIC_WS_URL=https://your-vps-domain.com
```

---

## API Endpoints

The web server exposes these endpoints:

### Bot Control

**POST** `/api/bot/start`
- Start the trading bot
- Returns: `{"success": true, "message": "Bot started"}`

**POST** `/api/bot/stop`
- Stop the trading bot
- Returns: `{"success": true, "message": "Bot stopped"}`

**GET** `/api/bot/status`
- Check if bot is running
- Returns: `{"running": true, "has_client": true}`

### Statistics

**GET** `/api/stats`
- Get trading statistics
- Returns: Win rate, P&L, trade counts, strategy breakdown

**GET** `/api/trades?limit=20`
- Get recent trades
- Returns: Array of trade objects

### Health

**GET** `/health`
- Server health check
- Returns: `{"status": "healthy", "bot_running": true, "timestamp": "..."}`

---

## WebSocket Events

The UI connects to WebSocket and receives:

**Event:** `bot_state`
**Frequency:** Every 500ms
**Payload:**
```json
{
  "running": true,
  "btc_price": 95503.80,
  "secs_left": 90,
  "current_candle": {...},
  "current_market": {...},
  "last_signal": {...},
  "stats": {...},
  "recent_trades": [...]
}
```

---

## File Structure

```
polymarket-sniper/
├── sniper_bot.py              # Core trading logic
├── web_server.py              # WebSocket server ⭐ NEW
├── polymarket_creds.json      # Your API keys
├── snipe_trades.json          # Trade log
├── requirements.txt           # Python deps (updated)
└── ui/
    ├── app/
    │   └── live/
    │       └── page.tsx       # Live trading UI ⭐ NEW
    ├── package.json           # Node deps (updated)
    └── ...
```

---

## Tips for Best Performance

### 1. Network Latency

- **VPS location**: us-east-1 (near Polymarket servers)
- **Low latency**: <50ms to Polymarket = faster fills

### 2. Screen Setup

Recommended layout:
- **Monitor 1**: Trading UI (http://localhost:3000/live)
- **Monitor 2**: Polymarket.com (manual verification)
- **Terminal**: web_server.py logs

### 3. Auto-Restart

Use systemd (Linux) or pm2 (Node.js) to auto-restart if crash:

```bash
# pm2 for Node processes
npm i -g pm2
cd ui
pm2 start "npm run dev" --name sniper-ui
pm2 save
pm2 startup
```

### 4. Logging

Check logs for errors:

```bash
# Web server logs (Terminal 1)
tail -f server.log

# Bot execution logs
tail -f snipe_trades.json
```

---

## Security Notes

⚠️ **IMPORTANT:**

1. **Never share polymarket_creds.json** — Contains your private keys
2. **Don't expose web server publicly** — Use SSH tunnel or VPN
3. **Use HTTPS in production** — Don't send credentials over HTTP
4. **Set daily loss limits** — Automated trading = automated losses
5. **Monitor regularly** — Check every few hours, don't set-and-forget

---

## Next Steps

Once you're comfortable with the UI:

1. **Run for 24 hours** — Track win rate
2. **Adjust thresholds** — If needed (see STRATEGY_EXPLANATION.md)
3. **Scale position size** — If >70% win rate
4. **Deploy to VPS** — For 24/7 trading
5. **Build alerts** — Email/SMS on big wins/losses

---

**You're ready to start sniping!** 🎯

Open http://localhost:3000/live and click START BOT.

Good luck! 💰
