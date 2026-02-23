# 🎯 Polymarket Sniper - Quick Start Guide

Get up and running in 5 minutes.

## Prerequisites

- Python 3.8+
- Node.js 18+ (for UI)
- Polymarket account with API keys
- USDC in your Polymarket wallet

## Step 1: Setup Bot (2 minutes)

```bash
cd /home/amenti/.openclaw/workspace/polymarket-sniper

# Install dependencies
./setup.sh

# Edit your credentials
nano polymarket_creds.json
```

**Fill in:**
```json
{
  "api_key": "your_polymarket_api_key",
  "api_secret": "your_polymarket_api_secret",
  "api_passphrase": "your_polymarket_passphrase",
  "controller_key": "your_wallet_private_key",
  "polymarket_address": "your_wallet_address"
}
```

## Step 2: Fund Wallet

1. Go to https://polymarket.com
2. Deposit USDC (minimum $50 recommended)
3. Verify balance shows up

## Step 3: Test Bot (1 minute)

```bash
python3 sniper_bot.py
```

You should see:
```
══════════════════════════════════════════════════════════════════════
  🎯 POLYMARKET 5-MIN BTC CANDLE SNIPER BOT
  Strategy: Body Candles + Volatility + Last-Second Sniping
  Poll: 500ms | Entry: $10 | Max Price: $0.85
══════════════════════════════════════════════════════════════════════

✅ CLOB client initialized

[285s] 🟢 Body: $42 (31.2%) | Vol: 0.08% | UP: $0.523 DN: $0.477 | WAIT
```

**Good signs:**
- ✅ CLOB client initialized
- ✅ Live BTC price updating
- ✅ Timer counting down

**Bad signs:**
- ❌ "No CLOB price" errors → Market might be paused
- ❌ "Order failed" → Check USDC balance
- ❌ Python errors → Install missing packages

Press **Ctrl+C** to stop.

## Step 4: Setup UI (Optional, 2 minutes)

```bash
cd ui

# Install dependencies
./setup.sh

# Run dev server
npm run dev
```

Open http://localhost:3000

The UI starts in **DEMO mode** — toggle to LIVE mode once bot is running.

## Step 5: Run Your First Trade

1. **Wait for signal**
   ```
   [15s] 🟢 Body: $67 (43.1%) | Vol: 0.09% | UP: $0.612 DN: $0.388 | SNIPE
   ```

2. **Bot executes automatically**
   ```
   🎯 ══════════════════════════════════════════════════════════════════
     SNIPE SIGNAL | LAST_SECOND
     Direction: UP
     Reason: LAST-SECOND: Strong UP body 43.1% ($67)
     Confidence: 78.2%
     Share Price: $0.6120
   ════════════════════════════════════════════════════════════════════
     💰 SNIPE: UP 16.34 shares @ $0.6120 (limit $0.7120)
     ✅ FILLED: 16.34 shares @ $0.6150 ($10.05)
   ════════════════════════════════════════════════════════════════════
   ```

3. **Wait for resolution** (~5 minutes)
   ```
   ✅ RESOLVED: a3f42b19 | WIN $+6.29 | sold 16.34 @ $0.9950
   ```

🎉 **You just made $6.29!**

## Check Stats

```bash
python3 analyze_stats.py
```

Output:
```
══════════════════════════════════════════════════════════════════════
  📊 SNIPER BOT PERFORMANCE
══════════════════════════════════════════════════════════════════════

📈 OVERALL:
  Total Trades: 1
  Wins: 1 (100.0%)
  Losses: 0 (0.0%)
  P&L: $+6.29
  Avg P&L/Trade: $+6.29
```

## Troubleshooting

### "No market" errors
- Market might be paused
- Wait 5 minutes for next market
- Check https://polymarket.com/event/btc-updown-5m

### "Price too high" skips
- Good! Bot is protecting you
- Only enters when share price < $0.85
- This is by design (bad odds above $0.85)

### "Proxy blocked" errors
- Normal — bot auto-rotates proxies
- If persistent, replace proxies in `sniper_bot.py`

### Low win rate (<60%)
- Tighten thresholds (see README.md "Parameter Tuning")
- Or run longer (need 20+ trades for stats)

## Risk Management

### Start Small
```python
# In sniper_bot.py:
TRADE_AMOUNT = 5.0  # Start with $5 per trade
```

### Set Daily Limits
- Stop if daily loss > 20% of bankroll
- Stop after 5 consecutive losses
- Take breaks every 4 hours

### Position Sizing
| Bankroll | Per Trade | Daily Max |
|----------|-----------|-----------|
| $50      | $3-5      | $15       |
| $100     | $5-10     | $30       |
| $200     | $10-15    | $60       |
| $500+    | $15-25    | $100      |

## Best Hours to Trade

**Peak volume (best):**
- 9am-4pm ET (weekdays)

**Avoid:**
- 12am-6am ET (low liquidity)
- Weekends (wider spreads)

## Next Steps

1. **Run for 24 hours** — Track win rate
2. **If win rate >65%** — Increase position size
3. **If win rate <60%** — Tighten thresholds
4. **Build stats dashboard** — Track P&L over time

## Advanced: VPS Deployment

For 24/7 trading:

```bash
# 1. Get VPS (DigitalOcean, AWS, Vultr)
# Region: us-east-1 (near Polymarket servers)

# 2. SSH into VPS
ssh root@your-vps-ip

# 3. Clone repo
git clone [your-repo]
cd polymarket-sniper

# 4. Install deps
./setup.sh

# 5. Setup credentials
nano polymarket_creds.json

# 6. Run in background
nohup python3 sniper_bot.py > bot.log 2>&1 &

# 7. Check logs
tail -f bot.log
```

## Files Overview

```
polymarket-sniper/
├── sniper_bot.py              # Main bot (run this)
├── analyze_stats.py           # Stats analyzer
├── snipe_trades.json          # All trades (auto-created)
├── polymarket_creds.json      # Your keys (DO NOT share!)
├── requirements.txt           # Python dependencies
├── setup.sh                   # Setup script
├── README.md                  # Full documentation
├── STRATEGY_EXPLANATION.md    # Why this works
├── QUICK_REFERENCE.md         # Cheat sheet
└── ui/                        # Trading dashboard (optional)
    ├── app/page.tsx           # Main UI
    ├── package.json           # Dependencies
    └── README.md              # UI docs
```

## Support

**Docs:** All markdown files in this folder  
**Issues:** Check README.md troubleshooting section  
**Community:** https://discord.com/invite/clawd

## Safety Reminders

- ⚠️ **This is real money** — start small!
- ⚠️ **Crypto is risky** — only trade what you can afford to lose
- ⚠️ **Bot can lose money** — 70% win rate ≠ guaranteed profit
- ⚠️ **Polymarket can ban you** — don't abuse API
- ⚠️ **Check local laws** — Polymarket blocked in some countries

## Expected Results (First Week)

**Realistic:**
- Win rate: 65-75%
- Daily trades: 10-20
- Daily P&L: +$10-30
- Best trade: +$6-8
- Worst trade: -$8-10

**Not realistic:**
- Win rate: >85% (you got lucky, don't scale up yet)
- Daily P&L: >$100 (sample size too small)
- 0 losses (variance, keep trading)

## Final Checklist

Before running for real:

- [ ] Polymarket credentials configured
- [ ] USDC deposited and visible in wallet
- [ ] Bot connects successfully
- [ ] Ran one test trade manually (paper trade)
- [ ] Set position size appropriate for bankroll
- [ ] Understand the strategy (read STRATEGY_EXPLANATION.md)
- [ ] Know when to stop (daily loss limit, consecutive losses)
- [ ] Have backup plan if bot crashes (manual close on polymarket.com)

---

**Good luck!** 🎯

Start small. Prove the edge. Scale up slowly.
