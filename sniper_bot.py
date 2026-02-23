#!/usr/bin/env python3
"""
Polymarket 5-Min BTC Candle Sniper Bot
Pure body candle + volatility sniper — NO complex indicators.

Strategy:
1. LAST-SECOND SNIPE: Enter in final 10-20s if candle has strong body
2. LATE SNIPE: Enter at 1-2min left if green + low volatility + decent body
3. Poll every 0.5s for fast execution
"""

import json
import os
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs, BalanceAllowanceParams, AssetType
from py_clob_client.order_builder.constants import BUY, SELL

# ── Config ─────────────────────────────────────────────────────────────
POLL_INTERVAL = 0.5  # 500ms polling for fast sniping
TRADE_AMOUNT = 10.0  # $ per snipe
SNIPE_LOG = "snipe_trades.json"

# Proxy config (Netherlands proxies)
PROXY_AUTH = "bpvuwaya:q6ps07u6twzr"
PROXY_HOSTS = [
    "31.59.22.120:8153", "104.222.184.249:5267", "31.59.22.78:8111",
    "145.223.61.118:8150", "23.109.239.153:5168", "46.202.254.213:8244",
]
_proxy_idx = 0

def get_proxy():
    global _proxy_idx
    host = PROXY_HOSTS[_proxy_idx % len(PROXY_HOSTS)]
    _proxy_idx += 1
    url = f"http://{PROXY_AUTH}@{host}"
    return {"http": url, "https": url}

# ── Binance BTC/USDT Price ────────────────────────────────────────────
def get_btc_price():
    """Fetch latest BTC/USDT 1m candle from Binance."""
    try:
        resp = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": "BTCUSDT", "interval": "1m", "limit": 1},
            proxies=get_proxy(),
            timeout=3
        )
        candle = resp.json()[0]
        return {
            "open": float(candle[1]),
            "high": float(candle[2]),
            "low": float(candle[3]),
            "close": float(candle[4]),
            "timestamp": candle[0],
        }
    except Exception as e:
        print(f"⚠ Binance fetch failed: {e}")
        return None

def get_5min_synthetic_candle():
    """Build current 5-min candle from last 5 x 1-min candles."""
    try:
        resp = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": "BTCUSDT", "interval": "1m", "limit": 5},
            proxies=get_proxy(),
            timeout=5
        )
        candles = resp.json()
        if len(candles) < 5:
            return None
        
        return {
            "open": float(candles[0][1]),
            "high": max(float(c[2]) for c in candles),
            "low": min(float(c[3]) for c in candles),
            "close": float(candles[-1][4]),
            "timestamp": candles[0][0],
        }
    except Exception as e:
        print(f"⚠ 5min candle fetch failed: {e}")
        return None

# ── Polymarket Market & Prices ────────────────────────────────────────
def get_next_market():
    """Fetch the NEXT 5-min BTC market (the one currently forming)."""
    now_ts = int(time.time())
    current_5min_start = (now_ts // 300) * 300
    next_5min_start = current_5min_start + 300
    
    event_slug = f"btc-updown-5m-{next_5min_start}"
    
    try:
        url = f"https://gamma-api.polymarket.com/events?slug={event_slug}"
        resp = requests.get(url, proxies=get_proxy(), timeout=5)
        
        if resp.status_code != 200:
            return None
        
        events = resp.json()
        if not events:
            return None
        
        market = events[0]['markets'][0]
        tokens = json.loads(market['clobTokenIds'])
        prices = json.loads(market.get('outcomePrices', '[0.5, 0.5]'))
        
        return {
            'up_token': tokens[0],
            'down_token': tokens[1],
            'up_price': float(prices[0]),
            'down_price': float(prices[1]),
            'market_slug': event_slug,
            'timestamp': next_5min_start,
            'accepting_orders': market.get('acceptingOrders', False),
        }
    except Exception as e:
        print(f"⚠ Market fetch failed: {e}")
        return None

def get_live_share_prices(market):
    """Get real-time UP/DOWN share prices from CLOB."""
    try:
        proxy = get_proxy()
        up_resp = requests.get(
            'https://clob.polymarket.com/price',
            params={'token_id': market['up_token'], 'side': 'buy'},
            proxies=proxy,
            timeout=3,
        )
        down_resp = requests.get(
            'https://clob.polymarket.com/price',
            params={'token_id': market['down_token'], 'side': 'buy'},
            proxies=proxy,
            timeout=3,
        )
        
        up_price = float(up_resp.json().get('price', market['up_price']))
        down_price = float(down_resp.json().get('price', market['down_price']))
        
        return {'up': up_price, 'down': down_price}
    except Exception as e:
        print(f"⚠ CLOB price fetch failed: {e}")
        return {'up': market['up_price'], 'down': market['down_price']}

# ── Snipe Logic ────────────────────────────────────────────────────────
def analyze_candle_for_snipe(candle_5m, secs_left):
    """
    Analyze current 5-min candle and decide if we should snipe.
    
    Returns:
        {
            "action": "SNIPE" | "WAIT",
            "direction": "UP" | "DOWN" | None,
            "reason": str,
            "confidence": float (0-100),
            "type": "LAST_SECOND" | "LATE" | None
        }
    """
    if not candle_5m:
        return {"action": "WAIT", "reason": "no_candle_data"}
    
    open_price = candle_5m["open"]
    close_price = candle_5m["close"]
    high = candle_5m["high"]
    low = candle_5m["low"]
    
    # Body metrics
    body = abs(close_price - open_price)
    range_total = high - low
    body_pct = (body / range_total * 100) if range_total > 0 else 0
    
    is_green = close_price >= open_price
    direction = "UP" if is_green else "DOWN"
    
    # Wicks
    upper_wick = high - max(open_price, close_price)
    lower_wick = min(open_price, close_price) - low
    
    # Volatility (range as % of open)
    volatility = (range_total / open_price * 100) if open_price > 0 else 0
    
    # ═══════════════════════════════════════════════════════════════════
    # SNIPE 1: LAST-SECOND (10-20s left)
    # ═══════════════════════════════════════════════════════════════════
    if 10 <= secs_left <= 20:
        # Requirements:
        # - Strong body (>40% of range)
        # - Decent movement (body > $50)
        # - Not doji (body > 0.1% of price)
        
        if body_pct > 40 and body > 50 and (body / open_price * 100) > 0.1:
            confidence = min(95, 60 + body_pct)
            return {
                "action": "SNIPE",
                "direction": direction,
                "reason": f"LAST-SECOND: Strong {direction} body {body_pct:.1f}% (${body:.0f})",
                "confidence": round(confidence, 1),
                "type": "LAST_SECOND",
                "metrics": {
                    "body_pct": round(body_pct, 1),
                    "body_usd": round(body, 0),
                    "volatility": round(volatility, 2),
                }
            }
    
    # ═══════════════════════════════════════════════════════════════════
    # SNIPE 2: LATE (60-120s left)
    # ═══════════════════════════════════════════════════════════════════
    if 60 <= secs_left <= 120:
        # Requirements:
        # - GREEN candle (bullish continuation)
        # - LOW volatility (range < 0.15% of price) — stable, not whipsawing
        # - DECENT body (>$30 AND >25% of range) — real move, not noise
        # - Small wicks (< 30% of range each) — clean direction
        
        low_volatility = volatility < 0.15
        decent_body = body > 30 and body_pct > 25
        small_wicks = (upper_wick / range_total < 0.3 and 
                       lower_wick / range_total < 0.3) if range_total > 0 else False
        
        if is_green and low_volatility and decent_body and small_wicks:
            # Confidence based on how clean the setup is
            confidence = 55 + (body_pct * 0.3) + (20 if body > 50 else 0)
            confidence = min(85, confidence)
            
            return {
                "action": "SNIPE",
                "direction": "UP",
                "reason": f"LATE: Clean green continuation (body ${body:.0f}, vol {volatility:.2f}%)",
                "confidence": round(confidence, 1),
                "type": "LATE",
                "metrics": {
                    "body_pct": round(body_pct, 1),
                    "body_usd": round(body, 0),
                    "volatility": round(volatility, 2),
                    "upper_wick_pct": round(upper_wick / range_total * 100, 1) if range_total > 0 else 0,
                    "lower_wick_pct": round(lower_wick / range_total * 100, 1) if range_total > 0 else 0,
                }
            }
    
    return {
        "action": "WAIT",
        "reason": f"No snipe window (secs_left={secs_left}, body_pct={body_pct:.1f}%)",
        "metrics": {
            "body_pct": round(body_pct, 1),
            "body_usd": round(body, 0),
            "volatility": round(volatility, 2),
        }
    }

# ── Trade Execution ────────────────────────────────────────────────────
def init_clob_client():
    """Initialize Polymarket CLOB client."""
    with open('polymarket_creds.json', 'r') as f:
        creds = json.load(f)
    
    api_creds = ApiCreds(
        api_key=creds['api_key'],
        api_secret=creds['api_secret'],
        api_passphrase=creds['api_passphrase'],
    )
    
    # Use first proxy for CLOB
    import py_clob_client.http_helpers.helpers as clob_helpers
    import httpx
    clob_proxy = f"http://{PROXY_AUTH}@{PROXY_HOSTS[0]}"
    clob_helpers._http_client = httpx.Client(http2=True, proxy=clob_proxy)
    
    return ClobClient(
        host='https://clob.polymarket.com',
        key=creds['controller_key'],
        chain_id=137,
        creds=api_creds,
        signature_type=2,
        funder=creds['polymarket_address'],
    )

def execute_snipe(client, market, direction, amount, signal):
    """Execute snipe trade on Polymarket."""
    token = market['up_token'] if direction == 'UP' else market['down_token']
    
    # Get live CLOB price
    try:
        resp = requests.get(
            'https://clob.polymarket.com/price',
            params={'token_id': token, 'side': 'buy'},
            timeout=3,
        )
        best_ask = float(resp.json().get('price', 0.50))
    except Exception:
        best_ask = 0.50
    
    if best_ask > 0.85:
        print(f"  ⚠ Price too high: ${best_ask:.4f} > $0.85 (bad odds)")
        return None
    
    # Aggressive fill: buy at limit 0.95 to sweep the book
    buy_price = min(best_ask + 0.10, 0.95)
    shares = round(amount / best_ask, 2)
    if shares < 5:
        shares = 5.02  # Polymarket minimum
    
    print(f"  💰 SNIPE: {direction} {shares} shares @ ${best_ask:.4f} (limit ${buy_price:.4f})")
    
    try:
        order = OrderArgs(token_id=token, price=buy_price, size=shares, side=BUY)
        signed = client.create_order(order)
        resp = client.post_order(signed)
        
        if not resp.get('success'):
            print(f"  ❌ Order failed: {resp}")
            return None
        
        actual_cost = float(resp.get('makingAmount') or 0)
        shares_received = float(resp.get('takingAmount') or 0)
        
        if shares_received == 0:
            shares_received = shares
            actual_cost = round(shares * best_ask, 4)
        
        entry_price = actual_cost / shares_received if shares_received > 0 else best_ask
        
        print(f"  ✅ FILLED: {shares_received} shares @ ${entry_price:.4f} (${actual_cost:.2f})")
        
        return {
            'trade_id': str(uuid.uuid4())[:8],
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'candle_timestamp': market['timestamp'],
            'direction': direction,
            'type': signal['type'],
            'reason': signal['reason'],
            'confidence': signal['confidence'],
            'metrics': signal.get('metrics', {}),
            'token_id': token,
            'entry_cost': actual_cost,
            'shares': shares_received,
            'entry_price': entry_price,
            'market_slug': market['market_slug'],
            'status': 'open',
        }
    except Exception as e:
        print(f"  ❌ Trade error: {e}")
        traceback.print_exc()
        return None

# ── Trade Log ──────────────────────────────────────────────────────────
def load_trade_log():
    try:
        with open(SNIPE_LOG, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_trade_log(log):
    with open(SNIPE_LOG, 'w') as f:
        json.dump(log, f, indent=2, default=str)

def log_trade(trade):
    log = load_trade_log()
    log.append(trade)
    save_trade_log(log)

def check_resolutions(client):
    """Check open positions and resolve if candle expired."""
    log = load_trade_log()
    now_ts = int(time.time())
    updated = False
    
    for trade in log:
        if trade.get('status') != 'open':
            continue
        
        candle_ts = trade.get('candle_timestamp', 0)
        
        # Market resolves ~30-60s after candle close
        if now_ts < candle_ts + 330:
            continue
        
        # Try to sell (even if expired, try to claim $1 payout)
        try:
            token_id = trade['token_id']
            
            # Update balance
            client.update_balance_allowance(
                BalanceAllowanceParams(asset_type=AssetType.CONDITIONAL, token_id=token_id)
            )
            time.sleep(2)
            
            ba = client.get_balance_allowance(
                BalanceAllowanceParams(asset_type=AssetType.CONDITIONAL, token_id=token_id)
            )
            balance = int(ba.get('balance', 0)) / 1e6
            
            if balance < 0.01:
                print(f"  ⚠ No balance for {trade['trade_id']} — marking as lost")
                trade['status'] = 'closed'
                trade['outcome'] = 'LOSS'
                trade['pnl'] = -trade['entry_cost']
                updated = True
                continue
            
            shares_to_sell = round(balance, 2)
            if shares_to_sell > balance:
                shares_to_sell = round(balance - 0.01, 2)
            
            if shares_to_sell < 5:
                # Below minimum sell size — hold for full resolution
                print(f"  📌 Holding {trade['trade_id']} (only {shares_to_sell} shares)")
                trade['status'] = 'holding'
                updated = True
                continue
            
            # Market sell at $0.01
            order = OrderArgs(token_id=token_id, price=0.01, size=shares_to_sell, side=SELL)
            signed = client.create_order(order)
            resp = client.post_order(signed)
            
            if resp.get('success'):
                proceeds = float(resp.get('takingAmount') or 0)
                shares_sold = float(resp.get('makingAmount') or 0)
                
                if proceeds == 0:
                    # Estimate from CLOB price
                    try:
                        pr = requests.get(
                            'https://clob.polymarket.com/price',
                            params={'token_id': token_id, 'side': 'sell'},
                            timeout=3,
                        )
                        sell_price = float(pr.json().get('price', 0.01))
                        proceeds = shares_sold * sell_price
                    except:
                        proceeds = 0.0
                
                pnl = proceeds - trade['entry_cost']
                outcome = "WIN" if pnl > 0 else "LOSS"
                
                trade['status'] = 'closed'
                trade['outcome'] = outcome
                trade['pnl'] = round(pnl, 2)
                trade['proceeds'] = round(proceeds, 2)
                trade['exit_price'] = round(proceeds / shares_sold, 4) if shares_sold > 0 else 0
                
                print(f"  {'✅' if outcome == 'WIN' else '❌'} RESOLVED: {trade['trade_id']} | "
                      f"{outcome} ${pnl:+.2f} | sold {shares_sold} @ ${trade['exit_price']:.4f}")
                
                updated = True
        except Exception as e:
            print(f"  ⚠ Resolution error for {trade['trade_id']}: {e}")
    
    if updated:
        save_trade_log(log)

# ── Main Loop ──────────────────────────────────────────────────────────
def main():
    print("\n" + "="*70)
    print("  🎯 POLYMARKET 5-MIN BTC CANDLE SNIPER BOT")
    print("  Strategy: Body Candles + Volatility + Last-Second Sniping")
    print("  Poll: 500ms | Entry: $10 | Max Price: $0.85")
    print("="*70 + "\n")
    
    # Init CLOB client
    try:
        client = init_clob_client()
        print("✅ CLOB client initialized\n")
    except Exception as e:
        print(f"❌ Failed to init CLOB client: {e}")
        return
    
    last_traded_window = 0
    
    while True:
        try:
            loop_start = time.time()
            
            # 1. Get current market
            market = get_next_market()
            if not market or not market['accepting_orders']:
                time.sleep(POLL_INTERVAL)
                continue
            
            # 2. Get time in window
            now_ts = int(time.time())
            current_5min_start = (now_ts // 300) * 300
            secs_left = (current_5min_start + 300) - now_ts
            
            # 3. Get 5-min synthetic candle
            candle_5m = get_5min_synthetic_candle()
            if not candle_5m:
                time.sleep(POLL_INTERVAL)
                continue
            
            # 4. Get live share prices
            share_prices = get_live_share_prices(market)
            
            # 5. Analyze for snipe
            signal = analyze_candle_for_snipe(candle_5m, secs_left)
            
            # 6. Display status
            body = abs(candle_5m['close'] - candle_5m['open'])
            is_green = candle_5m['close'] >= candle_5m['open']
            direction = "🟢" if is_green else "🔴"
            
            print(f"\r[{secs_left:3d}s] {direction} Body: ${body:>6.0f} ({signal['metrics'].get('body_pct', 0):>4.1f}%) | "
                  f"Vol: {signal['metrics'].get('volatility', 0):>5.2f}% | "
                  f"UP: ${share_prices['up']:.3f} DN: ${share_prices['down']:.3f} | "
                  f"{signal['action']:<10}", end="", flush=True)
            
            # 7. Execute snipe
            if signal['action'] == 'SNIPE' and market['timestamp'] != last_traded_window:
                print()  # newline before trade output
                print(f"\n🎯 {'='*66}")
                print(f"  SNIPE SIGNAL | {signal['type']}")
                print(f"  Direction: {signal['direction']}")
                print(f"  Reason: {signal['reason']}")
                print(f"  Confidence: {signal['confidence']}%")
                print(f"  Share Price: ${share_prices[signal['direction'].lower()]:.4f}")
                print(f"{'='*68}")
                
                trade = execute_snipe(client, market, signal['direction'], TRADE_AMOUNT, signal)
                
                if trade:
                    log_trade(trade)
                    last_traded_window = market['timestamp']
                    print(f"{'='*68}\n")
            
            # 8. Check resolutions
            check_resolutions(client)
            
            # 9. Stats summary every 60s
            if now_ts % 60 < POLL_INTERVAL:
                log = load_trade_log()
                if log:
                    wins = sum(1 for t in log if t.get('outcome') == 'WIN')
                    losses = sum(1 for t in log if t.get('outcome') == 'LOSS')
                    total = wins + losses
                    pnl = sum(t.get('pnl', 0) for t in log if 'pnl' in t)
                    
                    if total > 0:
                        print(f"\n📊 STATS: {total} trades | {wins}W/{losses}L ({wins/total*100:.1f}%) | "
                              f"P&L: ${pnl:+.2f}\n")
            
            # Sleep to maintain poll rate
            elapsed = time.time() - loop_start
            sleep_time = max(0, POLL_INTERVAL - elapsed)
            time.sleep(sleep_time)
            
        except KeyboardInterrupt:
            print("\n\n🛑 Shutting down...\n")
            break
        except Exception as e:
            print(f"\n⚠ Loop error: {e}")
            traceback.print_exc()
            time.sleep(5)

if __name__ == "__main__":
    main()
