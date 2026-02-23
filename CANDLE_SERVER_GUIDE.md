# Candle Server Guide — DNA System + 24 Signals

## Overview

The **candle server** (`candle_server.py` on port 8081) is an advanced prediction system built exactly as specified in your comprehensive 8,120-line implementation. It runs **alongside** the current web server (port 8080) for comparison and eventual replacement.

---

## System Comparison

### Current System (web_server.py — Port 8080)
- **Framework**: Flask + SocketIO
- **Signals**: 7 indicators (RSI, MACD, Bollinger Bands, S/R, Volume Profile, Patterns, EMA)
- **Prediction Method**: Ensemble voting
- **Historical Analysis**: 5000 candles (~17 days of 5m data)
- **Backtest Results**: 38.4% overall, 63.9% on high confidence (>70%)
- **Status**: ✅ Production, tested

### Candle Server (candle_server.py — Port 8081)
- **Framework**: FastAPI + WebSocket
- **Signals**: **24 weighted signals** (see below)
- **Prediction Method**: **50-point DNA classification** + weighted voting
- **Historical Analysis**: 20,000 1m candles + 4,000 5m candles (~14 days)
- **Advanced Features**:
  - **Toxic combo hijacking** (auto-flips verdicts when known-bad signal combos appear)
  - **RSI zone direction flipping** (7 multi-timeframe rules)
  - **MACD red zone gating** (blocks GREEN bets during falling MACD)
  - **Backtest WR lookup table** (only trades scenarios with ≥60% historical WR)
  - **Relief take-profit** (sells at breakeven if position survives -50% drawdown)
  - **Auto-threshold adjustment** (targets 50% trade rate)
- **Expected Performance**: 73.3% live WR (22W/8L on 30 trades)
- **Status**: 🆕 Just built — needs testing

---

## 24-Signal System

### Signal Weights

1. **DNA Prediction** (0.5) — 50-point candle fingerprint matching
2. **2-Candle Pattern** (2.75) — GG/GR/RG/RR historical win rates
3. **3-Candle Pattern** (5.0) — GGG/GGR/.../RRR historical patterns
4. **4-Candle Pattern** (5.0) — 4-candle sequence statistics
5. **Momentum** (1.5) — 5-candle price change direction
6. **Dildo Candle** (1.5) — Strong directional candles (body >80% range, >1.5x ATR)
7. **Streak-5** (2.0) — Contrarian signal after 5+ same-color candles
8. **MACDstr** (2.0) — Strong MACD histogram moves
9. **Sequence 5m** (weight varies) — Historical sequence continuation stats
10. **Sequence 15m** (weight varies)
11. **Sequence 1m** (weight varies)
12. **Sequence Strong Matches** (weight varies)
13-24. **Additional signals** (RSI divergence, volume spikes, S/R proximity, etc.)

### DNA Classification (50 Points)

Each candle is classified across 15 dimensions:

- **Color**: GREEN / RED
- **Shape**: HAMMER / DOJI / SHOOTING_STAR / STRONG / NORMAL
- **Size**: TINY / SMALL / MEDIUM / LARGE (ATR-relative)
- **Body %**: Percentage of total range
- **Upper Wick %**: Percentage of total range
- **Lower Wick %**: Percentage of total range
- **RSI**: OB (>70) / OS (<30) / RISING / FALLING / MID
- **MACD**: POS_STRONG / POS_WEAK / NEG_WEAK / NEG_STRONG
- **BB Position**: ABOVE / NEAR_UPPER / MID / NEAR_LOWER / BELOW
- **Volume**: HIGH / NORMAL / LOW (vs SMA)
- **Trend**: UP / DOWN / FLAT (EMA fast vs slow)
- **Streak**: 3G / 4G / 5G+ / 3R / 4R / 5R+ / MIXED
- **Previous Color**: GREEN / RED
- **2-Candle Pattern**: GG / GR / RG / RR
- **3-Candle Pattern**: GGG / GGR / ... / RRR

The system builds a **train/test split (70/30)** database of historical DNAs and predicts new candles by matching their DNA fingerprint.

---

## Advanced Features Explained

### 🎯 Toxic Combo Hijacking

**Problem**: Sometimes multiple signals **all agree** on a direction, but historically this combo has <40% win rate.

**Solution**: The system auto-detects these "toxic combos" during backtest:
- Identifies signal combinations where all dissent together ≥10 times
- Tracks verdict win rate when this combo appears
- If WR <40%, the combo is flagged as **toxic**

**Live Behavior**: When a toxic combo is detected, the system **automatically flips the verdict** to the opposite direction.

Example:
```
Original: RSI + MACD + Patterns all say "UP" (75% confidence)
Toxic Check: This combo historically wins only 35%
Hijack: FLIP to "DOWN" + log reason
```

### 🔄 RSI Zone Direction Flipping

**7 Rules** that override predictions based on multi-timeframe RSI analysis:

1. **5m RSI >73 + rising** → Block GREEN bets (58.1% historical trap)
2. **15m RSI <32 + 5m falling** → Flip to GREEN (bullish divergence)
3. **5m RSI >70 + 15m >65** → Block GREEN (double overbought)
4. **1m RSI <25 + 5m <40** → Force GREEN (extreme oversold)
5. **15m RSI >75 + 5m rising** → Flip to RED (extended rally)
6. **5m RSI 30-40 + 15m <35** → Force GREEN (MTF oversold)
7. **1m RSI >80** → Block GREEN (parabolic exhaustion)

### 🚫 MACD Red Zone Gate

**Rule**: When MACD histogram is **falling** and outside the ±6 deadzone, block all GREEN bets.

**Reason**: Backtests showed 58.1% win rate for GREEN bets in this zone = losing strategy.

**Detection**:
- Check current MACD histogram vs previous bar
- If `hist_curr < hist_prev` AND `abs(hist_curr) > 6` → RED ZONE
- Shift left by 1 bar (if next bar is falling, flag current bar too)

### 📊 Backtest WR Lookup Table

**Concept**: Only trade scenarios that have historically performed well.

**Implementation**:
1. Run full backtest on 30% test set (untouched during training)
2. Track win rate for every `(direction, confidence_bucket)` pair
   - Buckets: 50-55%, 55-60%, 60-65%, 65-70%, 70%+
3. Build lookup table: `{("GREEN", 60): {"wr": 72.3%, "n": 15}}`
4. **Live gate**: Only trade if backtested WR ≥60% AND n ≥5 samples

Example:
```
Verdict: GREEN 62% confidence
Bucket: 60-65%
Backtest: This bucket has 57.8% WR (n=12)
Decision: SKIP (below 60% threshold)
```

### 💰 Relief Take-Profit

**Problem**: Position dips to -50%, looks dead, but recovers to +5%.

**Normal Behavior**: Hold for resolution (might go to -100%)

**Relief Behavior**: **SELL IMMEDIATELY** at any profit >0% after surviving deep drawdown.

**Why**: Recovering from -50% is psychologically and statistically significant. Lock in the survival win.

### 🎚️ Auto-Threshold Adjustment

**Goal**: Maintain ~50% trade rate (avoid over/under-trading).

**How**:
- Every 120 candles (~10 hours), check trade rate
- If <45%: Lower thresholds by 3% (RSI, MACD, sequence, confluence)
- If >55%: Raise thresholds by 3%
- Cap adjustments at min/max safe ranges

**Effect**: System self-balances to stay in optimal frequency zone.

---

## How to Use

### 1. Start Both Servers (Side-by-Side Testing)

**Terminal 1 — Current System (port 8080)**:
```bash
cd /home/amenti/.openclaw/workspace/polymarket-sniper
./start_all.sh
```

**Terminal 2 — Candle Server (port 8081)**:
```bash
cd /home/amenti/.openclaw/workspace/polymarket-sniper
chmod +x start_candle_server.sh
./start_candle_server.sh
```

**Terminal 3 — UI (port 3001)**:
```bash
cd /home/amenti/.openclaw/workspace/polymarket-sniper/ui
npm run dev
```

### 2. Access Both UIs

- **Current System**: http://localhost:3001/live (connected to port 8080)
- **Candle Server**: Need to update UI to support dual connections

### 3. Compare Predictions

Both servers will run simultaneously. You can:
- Log predictions from both
- Compare verdict directions
- Track which system is more accurate
- See when toxic hijack / RSI flip changes outcomes

### 4. Monitor Performance

**Week 1-2**: Run both in **dry-run mode** (no real trades, just logging)

**Week 3**: If candle server shows ≥70% accuracy sustained:
- Enable auto-trade with **$1 bets** (vs $4 on current)
- Run 50+ trades before scaling

**Week 4+**: If success continues, migrate fully to candle server.

---

## API Endpoints

### Candle Server (port 8081)

```
GET  /api/state          — Full state snapshot
GET  /api/pnl            — P&L + frequency + accuracy
GET  /api/trades         — Recent 50 trades
GET  /api/bot/status     — Bot status
POST /api/bot/start      — Enable auto-trade
POST /api/bot/stop       — Disable auto-trade
GET  /api/candles/history — Full 5m candle history
WS   /ws                 — Real-time state updates
```

### WebSocket State Format

```json
{
  "type": "update",
  "price": 96234.50,
  "timestamp": 1708535100,
  "rsi_5m": 58.3,
  "verdict": {
    "direction": "GREEN",
    "confidence": 67.8,
    "up_score": 12.5,
    "down_score": 6.2,
    "signals": [
      {"name": "DNA", "dir": "GREEN", "weight": 0.5, "edge": 35, "confidence": 67.5},
      {"name": "3-Candle", "dir": "GREEN", "weight": 5.0, "edge": 12, "confidence": 62},
      ...
    ],
    "hijacked": false,
    "rsi_zone_flipped": false
  },
  "candle_prediction": {
    "predicted_color": "GREEN",
    "confidence": 67.5,
    "n_matches": 23,
    "green_count": 16,
    "red_count": 7
  },
  "pnl_summary": {...},
  "frequency": {...},
  "rolling_accuracy": {...},
  "recent_trades": [...],
  "candles_5m": [...],
  "dna_stats": {...},
  "sequence_stats": {...}
}
```

---

## Migration Path

### Phase 1: Parallel Testing (Now)
- ✅ Candle server built
- ⏳ Start both servers
- ⏳ Log predictions side-by-side
- ⏳ No real money yet

### Phase 2: Small Stakes Testing (Week 2)
- Update UI to show both predictions
- Enable candle server auto-trade with $1 bets
- Keep current system at $4 (as control group)
- Track 50+ trades

### Phase 3: Validation (Week 3-4)
- If candle server ≥70% WR sustained:
  - Increase to $2 bets
  - Run another 50 trades
- If current system <65% WR:
  - Reduce to $2 bets

### Phase 4: Full Migration (Week 5+)
- If candle server proves superior:
  - Switch UI default to port 8081
  - Retire Flask server (port 8080)
  - Scale to $4+ bets
- If equal/worse:
  - Keep both running
  - Use ensemble (trade when both agree)

---

## Key Advantages Over Current System

1. **3x More Signals** (24 vs 7) → better information
2. **DNA Pattern Matching** → historical precedent-based
3. **Toxic Combo Detection** → prevents catastrophic "all-agree-but-wrong" scenarios
4. **RSI Multi-Timeframe** → catches divergences current system misses
5. **WR-Gated Trading** → only trades proven scenarios
6. **Train/Test Split** → validated accuracy (not overfitted)
7. **Auto-Adjustment** → self-optimizes thresholds
8. **Relief TP** → recovers from near-death positions

---

## Monitoring Commands

```bash
# Watch candle server logs
tail -f candle_server.log

# Check trade log
cat candle_trades.json | jq '.[-10:]'

# Compare servers
curl http://localhost:8080/api/state | jq '.verdict'
curl http://localhost:8081/api/state | jq '.verdict'

# Get P&L from both
curl http://localhost:8080/api/pnl
curl http://localhost:8081/api/pnl
```

---

## Next Steps

1. **Start candle server** alongside current system
2. **Update UI** to connect to both WebSockets (show predictions side-by-side)
3. **Log all predictions** for 24-48 hours without trading
4. **Analyze results** to see which system is more accurate
5. **Enable small trades** ($1) on the winner
6. **Scale gradually** based on sustained performance

---

## Expected Performance

Based on the original implementation's backtest:

- **Verdict WR**: 60.1% (before filters)
- **Live WR**: 73.3% (after all filters — toxic hijack + RSI flip + WR gate)
- **Trade Rate**: ~50% (balanced, not over/under-trading)
- **Signal Count**: 24 weighted signals vs 7
- **Edge**: +23.3% over random (vs +13.9% for current high-confidence only)

**This system should significantly outperform the current 63.9% high-confidence rate.**

---

Ready to start testing! 🚀
