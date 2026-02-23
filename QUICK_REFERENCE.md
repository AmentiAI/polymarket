# 🎯 Quick Reference Card

## Quick Start

```bash
# Setup (first time)
./setup.sh

# Edit credentials
nano polymarket_creds.json

# Run bot
python3 sniper_bot.py

# Check stats
python3 analyze_stats.py
```

## Snipe Triggers

### 🔥 LAST-SECOND (10-20s left)
- Body > 40% of range
- Body > $50 move
- **Best for:** Quick profits, high win rate

### 💎 LATE (60-120s left)
- Green candle
- Volatility < 0.15%
- Body > $30 AND >25% of range
- Small wicks (<30% each)
- **Best for:** Safer entries, lower risk

## Live Output Codes

```
[285s] 🟢 Body: $42 (31.2%) | Vol: 0.08% | UP: $0.523 DN: $0.477 | WAIT
       ^^^^  ^^  ^^^^  ^^^^^    ^^^  ^^^^    ^^  ^^^^^  ^^  ^^^^^    ^^^^
        |     |    |      |       |     |     |     |     |     |      |
      secs  dir  move  body%   type  vol%   UP    UP$   DN   DN$   action
       left      $USD           

🟢/🔴 = Green/Red candle
Body: $ = Dollar move from open
(%) = Body as % of total range
Vol: % = Range as % of open price
UP/DN: $ = Share prices on Polymarket
WAIT/SNIPE = Bot action
```

## Key Metrics

| Metric | Good | Okay | Bad |
|--------|------|------|-----|
| **Body %** | >40% | 30-40% | <30% |
| **Volatility** | <0.15% | 0.15-0.25% | >0.25% |
| **Share Price** | <$0.60 | $0.60-0.75 | >$0.80 |
| **Win Rate** | >70% | 65-70% | <65% |

## Position Sizing

| Bankroll | Per Trade | Daily Limit |
|----------|-----------|-------------|
| $100 | $5 | $25 |
| $200 | $10 | $50 |
| $500 | $15-20 | $100 |
| $1000+ | $25-50 | $200 |

## Stop Rules

**Stop trading if:**
- Daily loss > 20% of bankroll
- 5 losses in a row
- Win rate < 55% over 20+ trades
- You feel tilted/emotional

**Take a break:**
- Every 4 hours (mental fatigue)
- After big win (overconfidence risk)
- After big loss (revenge trading risk)

## Troubleshooting

| Error | Fix |
|-------|-----|
| "No CLOB price" | Market paused, wait 5 min |
| "Order failed" | Check USDC balance |
| "Proxy blocked" | Normal, auto-rotates |
| "Price too high" | Good! Skipping bad odds |

## Optimization

**Best Hours:**
- 9am-4pm ET (peak volume)

**Avoid:**
- 12am-6am ET (low liquidity)
- Weekends (wider spreads)

**VPS Recommendations:**
- Region: us-east-1 (near Polymarket)
- Provider: DigitalOcean, AWS, Vultr
- Cost: $5-10/month

## Quick Stats

After first 20 trades, check:

```bash
python3 analyze_stats.py
```

**Target metrics:**
- Win rate: 70-75%
- Avg P&L: +$0.80-1.50/trade
- LAST-SECOND: 75-80% WR
- LATE: 65-70% WR

If win rate < 65%, tighten thresholds (see README).

## Emergency Stop

```bash
# Stop bot
Ctrl+C

# Check open positions
python3 analyze_stats.py

# Manually close position
# (login to polymarket.com and sell manually)
```

## File Locations

```
sniper_bot.py              # Main bot
snipe_trades.json          # All trades (backup this!)
polymarket_creds.json      # Your keys (NEVER share!)
analyze_stats.py           # Stats analyzer
```

## Contact/Support

**Discord:** https://discord.com/invite/clawd  
**Docs:** https://docs.openclaw.ai  
**Issues:** Check proxy status, USDC balance, Polymarket.com status

---

**Remember:** This is real money. Start small, prove the edge, then scale up.

Good luck! 🎯
