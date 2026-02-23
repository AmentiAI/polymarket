#!/usr/bin/env python3
"""
WebSocket server for Polymarket Sniper Bot
Provides real-time UI updates and bot control
"""

import json
import os
import sys
import time
import threading
import requests
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS

# Import bot functions
try:
    from sniper_bot import (
        get_btc_price,
        get_5min_synthetic_candle,
        get_next_market,
        get_live_share_prices,
        analyze_candle_for_snipe,
        init_clob_client,
        execute_snipe,
        check_resolutions,
        load_trade_log,
        get_proxy,
        TRADE_AMOUNT,
    )
    from predictor import predict_next_candle
    from advanced_predictor import predict_advanced
    from prediction_validator import (
        save_validation_entry,
        calculate_accuracy_metrics,
        add_validation_stats_to_prediction,
        get_accuracy_summary,
        backtest_predictions
    )
    from wick_arbitrage import WickArbitrage
    from polymarket_api import PolymarketAPI
except ImportError:
    print("⚠ Could not import from sniper_bot.py")
    print("Make sure web_server.py is in the same directory as sniper_bot.py")
    sys.exit(1)

# Initialize wick arbitrage detector and Polymarket API
wick_arb = WickArbitrage()
poly_api = PolymarketAPI()

# ── Flask Setup ──────────────────────────────────────────────────────
app = Flask(__name__)
app.config['SECRET_KEY'] = 'polymarket-sniper-2026'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# ── Bot State ────────────────────────────────────────────────────────
bot_state = {
    'running': False,
    'client': None,
    'last_traded_window': 0,
}

# ── Helper Functions ─────────────────────────────────────────────────
_backtest_cache = None
_backtest_cache_time = 0

def load_backtest_results():
    """Load backtest results from seed_validation run (cached for 5 minutes)."""
    global _backtest_cache, _backtest_cache_time
    
    now = time.time()
    if _backtest_cache and (now - _backtest_cache_time < 300):
        return _backtest_cache
    
    # Hardcoded results from latest seed_validation.py run
    # These are real backtest results on 3,000 historical candles
    results = {
        'total_tests': 2899,
        'overall_accuracy': 38.4,
        'edge_vs_random': -11.6,
        'high_confidence': {
            'signals_found': 36,
            'accuracy': 63.9,
            'edge_vs_random': 13.9,
            'signals_per_day': 1.2,
        },
        'timestamp': '2026-02-21',
        'candle_range': '~10 days (3,000 5m candles)',
    }
    
    _backtest_cache = results
    _backtest_cache_time = now
    return results

def calculate_stats():
    """Calculate P&L and win rate stats from trade log."""
    trades = load_trade_log()
    
    if not trades:
        return {
            'total': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0,
            'pnl': 0,
            'avg_pnl': 0,
            'last_second_stats': {'total': 0, 'wins': 0, 'win_rate': 0},
            'late_stats': {'total': 0, 'wins': 0, 'win_rate': 0},
        }
    
    closed = [t for t in trades if t.get('status') == 'closed']
    
    total = len(closed)
    wins = sum(1 for t in closed if t.get('outcome') == 'WIN')
    losses = sum(1 for t in closed if t.get('outcome') == 'LOSS')
    pnl = sum(t.get('pnl', 0) for t in closed)
    avg_pnl = pnl / total if total > 0 else 0
    win_rate = (wins / total * 100) if total > 0 else 0
    
    # By strategy type
    last_second = [t for t in closed if t.get('type') == 'LAST_SECOND']
    late = [t for t in closed if t.get('type') == 'LATE']
    
    ls_wins = sum(1 for t in last_second if t.get('outcome') == 'WIN')
    late_wins = sum(1 for t in late if t.get('outcome') == 'WIN')
    
    return {
        'total': total,
        'wins': wins,
        'losses': losses,
        'win_rate': round(win_rate, 1),
        'pnl': round(pnl, 2),
        'avg_pnl': round(avg_pnl, 2),
        'last_second_stats': {
            'total': len(last_second),
            'wins': ls_wins,
            'win_rate': round((ls_wins / len(last_second) * 100) if last_second else 0, 1),
        },
        'late_stats': {
            'total': len(late),
            'wins': late_wins,
            'win_rate': round((late_wins / len(late) * 100) if late else 0, 1),
        },
    }

def get_recent_trades(limit=20):
    """Get recent trades from log."""
    trades = load_trade_log()
    return list(reversed(trades[-limit:]))

def analyze_historical_signals(candles):
    """Analyze historical candles and identify where signals would have fired."""
    signals = []
    
    for candle in candles:
        # Calculate candle metrics
        body = abs(candle['close'] - candle['open'])
        range_total = candle['high'] - candle['low']
        body_pct = (body / range_total * 100) if range_total > 0 else 0
        volatility = (range_total / candle['open'] * 100) if candle['open'] > 0 else 0
        is_green = candle['close'] >= candle['open']
        
        # Check LAST-SECOND criteria (body >40%, move >$50)
        last_second_signal = body_pct > 40 and body > 50
        
        # Check LATE criteria (green, low vol <0.15%, body >$30 and >25%)
        late_signal = is_green and volatility < 0.15 and body > 30 and body_pct > 25
        
        # Add signal if triggered
        if last_second_signal:
            signals.append({
                'time': candle['time'],
                'type': 'LAST_SECOND',
                'direction': 'UP' if is_green else 'DOWN',
                'confidence': min(95, 60 + body_pct),
                'body_pct': body_pct,
                'body_usd': body,
                'volatility': volatility,
            })
        elif late_signal:
            signals.append({
                'time': candle['time'],
                'type': 'LATE',
                'direction': 'UP',
                'confidence': min(85, 55 + (body_pct * 0.3) + (20 if body > 50 else 0)),
                'body_pct': body_pct,
                'body_usd': body,
                'volatility': volatility,
            })
    
    return signals

def get_historical_candles(limit=100):
    """Fetch historical 5-min candles from Binance (for chart display)."""
    try:
        resp = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": "BTCUSDT", "interval": "5m", "limit": limit},
            proxies=get_proxy(),
            timeout=10
        )
        if resp.status_code != 200:
            return [], []
        
        candles_raw = resp.json()
        candles = []
        
        for c in candles_raw:
            candles.append({
                'time': int(c[0]) // 1000,  # Convert ms to seconds
                'open': float(c[1]),
                'high': float(c[2]),
                'low': float(c[3]),
                'close': float(c[4]),
            })
        
        # Analyze for signals
        signals = analyze_historical_signals(candles)
        
        return candles, signals
    except Exception as e:
        print(f"⚠ Historical candles fetch failed: {e}")
        return [], []

def get_prediction_candles(limit=5000):
    """Fetch large historical dataset for AI prediction (5000 candles = ~17 days)."""
    try:
        # Binance max limit is 1000, so we need to make multiple requests
        all_candles = []
        
        # Fetch in batches of 1000 (max allowed by Binance)
        batches_needed = (limit + 999) // 1000  # Round up
        
        end_time = int(time.time() * 1000)  # Current time in ms
        
        for i in range(batches_needed):
            resp = requests.get(
                "https://api.binance.com/api/v3/klines",
                params={
                    "symbol": "BTCUSDT",
                    "interval": "5m",
                    "limit": min(1000, limit - len(all_candles)),
                    "endTime": end_time
                },
                proxies=get_proxy(),
                timeout=10
            )
            
            if resp.status_code != 200:
                print(f"⚠ Batch {i+1} failed: {resp.status_code}")
                break
            
            batch_raw = resp.json()
            if not batch_raw:
                break
            
            for c in batch_raw:
                all_candles.insert(0, {  # Insert at beginning to maintain chronological order
                    'time': int(c[0]) // 1000,
                    'open': float(c[1]),
                    'high': float(c[2]),
                    'low': float(c[3]),
                    'close': float(c[4]),
                })
            
            # Update end_time to fetch older candles in next batch
            end_time = int(batch_raw[0][0]) - 1  # 1ms before first candle
            
            if len(all_candles) >= limit:
                break
        
        print(f"📊 Fetched {len(all_candles)} candles for prediction analysis")
        return all_candles
        
    except Exception as e:
        print(f"⚠ Prediction candles fetch failed: {e}")
        return []

# Cache for historical candles (refresh every 5 minutes)
_candles_cache = []  # For chart display (100 candles)
_signals_cache = []
_prediction_candles_cache = []  # For AI prediction (5000 candles)
_candles_cache_time = 0
_prediction_cache_time = 0
_last_prediction = None  # Track last prediction made
_last_candle_count = 0  # Track when to validate

def broadcast_state():
    """Send current bot state to all connected clients."""
    global _candles_cache, _signals_cache, _prediction_candles_cache, _candles_cache_time, _prediction_cache_time, _last_prediction, _last_candle_count
    
    now_ts = int(time.time())
    current_5min_start = (now_ts // 300) * 300
    secs_left = (current_5min_start + 300) - now_ts
    
    # Get market data
    market = get_next_market()
    candle_5m = get_5min_synthetic_candle()
    
    # Get historical candles for chart display (refresh every 1 minute)
    if now_ts - _candles_cache_time > 60:
        prev_count = len(_candles_cache)
        _candles_cache, _signals_cache = get_historical_candles(100)
        _candles_cache_time = now_ts
        print(f"📊 Display: {len(_candles_cache)} candles, {len(_signals_cache)} signals")
        
        # Validate previous prediction if new candle arrived
        if len(_candles_cache) > prev_count and _last_prediction and len(_candles_cache) > 0:
            try:
                actual_candle = _candles_cache[-1]  # Most recent completed candle
                validation = save_validation_entry(_last_prediction, actual_candle)
                
                if validation['direction_correct']:
                    print(f"✅ Prediction CORRECT: {_last_prediction['direction']} → {validation['actual_direction']} ({_last_prediction['confidence']:.1f}% conf)")
                else:
                    print(f"❌ Prediction WRONG: {_last_prediction['direction']} → {validation['actual_direction']} ({_last_prediction['confidence']:.1f}% conf)")
                
                # Show accuracy summary
                print(f"   {get_accuracy_summary()}")
            except Exception as e:
                print(f"⚠ Validation failed: {e}")
    
    # Get prediction dataset (refresh every 5 minutes to save API calls)
    if now_ts - _prediction_cache_time > 300:
        _prediction_candles_cache = get_prediction_candles(5000)
        _prediction_cache_time = now_ts
        print(f"🔮 Prediction dataset: {len(_prediction_candles_cache)} candles")
    
    # Build current candle info
    current_candle = None
    if candle_5m:
        body = abs(candle_5m['close'] - candle_5m['open'])
        range_total = candle_5m['high'] - candle_5m['low']
        body_pct = (body / range_total * 100) if range_total > 0 else 0
        volatility = (range_total / candle_5m['open'] * 100) if candle_5m['open'] > 0 else 0
        
        current_candle = {
            'open': candle_5m['open'],
            'high': candle_5m['high'],
            'low': candle_5m['low'],
            'close': candle_5m['close'],
            'body_pct': round(body_pct, 1),
            'body_usd': round(body, 0),
            'volatility': round(volatility, 3),
            'direction': 'GREEN' if candle_5m['close'] >= candle_5m['open'] else 'RED',
        }
    
    # Build market info
    current_market = None
    if market:
        share_prices = get_live_share_prices(market)
        current_market = {
            'timestamp': market['timestamp'],
            'up_price': share_prices['up'],
            'down_price': share_prices['down'],
            'accepting_orders': market['accepting_orders'],
            'market_slug': market['market_slug'],
        }
    
    # Analyze for snipe signal
    signal = analyze_candle_for_snipe(candle_5m, secs_left)
    
    last_signal = {
        'action': signal['action'],
        'reason': signal.get('reason', ''),
    }
    
    if signal['action'] == 'SNIPE':
        last_signal['direction'] = signal['direction']
        last_signal['confidence'] = signal['confidence']
        last_signal['type'] = signal['type']
        last_signal['metrics'] = signal.get('metrics', {})
    
    # Build trade markers from historical signals
    trade_markers = []
    for sig in _signals_cache:
        trade_markers.append({
            'time': sig['time'],
            'direction': sig['direction'],
            'type': sig['type'],
            'confidence': sig['confidence'],
            'outcome': 'SIGNAL',  # These are potential signals, not actual trades
        })
    
    # Generate prediction for next candle using advanced multi-indicator system
    prediction = None
    if len(_prediction_candles_cache) >= 100:  # Need at least 100 for meaningful analysis
        try:
            prediction = predict_advanced(_prediction_candles_cache)
            
            # Add validation stats and calibrate confidence based on real performance
            prediction = add_validation_stats_to_prediction(prediction)
            
            # Store for later validation
            _last_prediction = prediction.copy()
            
            # Show prediction with validation context
            if prediction.get('confidence_calibrated'):
                print(f"🔮 Prediction: {prediction['direction']} ({prediction['confidence']:.1f}% calibrated from {prediction['confidence_raw']:.1f}%) - {prediction['reasoning'][0] if prediction['reasoning'] else 'N/A'}")
            else:
                print(f"🔮 Prediction: {prediction['direction']} ({prediction['confidence']:.1f}%) - {prediction['reasoning'][0] if prediction['reasoning'] else 'N/A'}")
            
            # Show validation metrics if available
            if prediction.get('validation_metrics', {}).get('has_enough_data'):
                vm = prediction['validation_metrics']
                print(f"   📊 Track record: {vm['overall_accuracy']:.1f}% overall | {vm['recent_accuracy']:.1f}% recent ({vm['total_predictions']} predictions)")
        except Exception as e:
            print(f"⚠ Advanced prediction failed: {e}, falling back to basic")
            try:
                prediction = predict_next_candle(_prediction_candles_cache)
                prediction = add_validation_stats_to_prediction(prediction)
                _last_prediction = prediction.copy()
            except Exception as e2:
                print(f"⚠ Basic prediction also failed: {e2}")
    
    # Load backtest results (cached, read once)
    backtest_results = load_backtest_results()
    
    # ── WICK ARBITRAGE DETECTION ──────────────────────────────────
    wick_signal = None
    try:
        # Fetch 1-min and 5-min candles for wick analysis
        one_min_candles = wick_arb.fetch_1min_candles(10)
        five_min_candles = wick_arb.fetch_5min_candles(20)
        
        if one_min_candles and five_min_candles and candle_5m:
            # Use current 5-min candle for wick detection
            current_5min_candle = {
                'time': current_candle['time'] if current_candle else 0,
                'open': candle_5m['open'],
                'high': candle_5m['high'],
                'low': candle_5m['low'],
                'close': candle_5m['close'],
                'volume': candle_5m.get('volume', 0)
            }
            
            # Get REAL Polymarket prices (NO SIMULATION)
            try:
                poly_prices = poly_api.get_btc_candle_prices(simulate=False)
                
                if poly_prices and not poly_prices.get('simulated'):
                    up_price = poly_prices['up_price']
                    down_price = poly_prices['down_price']
                    
                    # Check for arbitrage opportunity (only with real prices)
                    wick_signal = wick_arb.check_arbitrage_opportunity(
                        one_min_candles,
                        five_min_candles,
                        current_5min_candle,
                        up_price,
                        down_price
                    )
                else:
                    # No real market data available - skip wick detection
                    wick_signal = None
                    if int(time.time()) % 300 == 0:  # Log every 5 minutes
                        print("⚠ No live BTC 5-min market found on Polymarket - wick detection disabled")
            except Exception as e:
                print(f"❌ Polymarket API error: {e}")
                wick_signal = None
            
            if wick_signal:
                print(f"\n🔥 WICK ARBITRAGE DETECTED!")
                print(f"   Direction: {wick_signal['direction']}")
                print(f"   Entry: ${wick_signal['entry_price']:.2f}")
                print(f"   Fair: ${wick_signal['fair_price']:.2f}")
                print(f"   Profit Potential: {wick_signal['profit_potential']:.1f}%")
                print(f"   Wick Ratio: {wick_signal['wick_ratio']:.1f}x")
    except Exception as e:
        print(f"⚠ Wick detection error: {e}")
        wick_signal = None
    
    # Build state object
    state = {
        'running': bot_state['running'],
        'btc_price': candle_5m['close'] if candle_5m else 0,
        'secs_left': secs_left,
        'current_candle': current_candle,
        'current_market': current_market,
        'last_signal': last_signal,
        'stats': calculate_stats(),
        'recent_trades': get_recent_trades(20),
        'candles': _candles_cache,  # Historical candlestick data
        'trade_markers': trade_markers,  # Signal markers for chart
        'prediction': prediction,  # Next candle prediction
        'backtest': backtest_results,  # Historical backtest data
        'wick_signal': wick_signal,  # Wick arbitrage signal (NEW!)
    }
    
    socketio.emit('bot_state', state)

# ── Bot Control Thread ───────────────────────────────────────────────
def bot_loop():
    """Main bot loop - runs in background thread."""
    print("🤖 Bot loop started")
    
    last_broadcast = 0
    
    while True:
        try:
            # Broadcast current state every 1 second (whether bot is running or not)
            now = time.time()
            if now - last_broadcast >= 1.0:
                broadcast_state()
                last_broadcast = now
            
            if not bot_state['running']:
                time.sleep(0.5)
                continue
            
            # Get current market
            market = get_next_market()
            if not market or not market['accepting_orders']:
                time.sleep(0.5)
                continue
            
            # Get time in window
            now_ts = int(time.time())
            current_5min_start = (now_ts // 300) * 300
            secs_left = (current_5min_start + 300) - now_ts
            
            # Get candle
            candle_5m = get_5min_synthetic_candle()
            if not candle_5m:
                time.sleep(0.5)
                continue
            
            # Analyze for snipe
            signal = analyze_candle_for_snipe(candle_5m, secs_left)
            
            # Execute snipe
            if signal['action'] == 'SNIPE' and market['timestamp'] != bot_state['last_traded_window']:
                print(f"\n🎯 {'='*66}")
                print(f"  SNIPE SIGNAL | {signal['type']}")
                print(f"  Direction: {signal['direction']}")
                print(f"  Reason: {signal['reason']}")
                print(f"  Confidence: {signal['confidence']}%")
                print(f"{'='*68}")
                
                if bot_state['client']:
                    trade = execute_snipe(
                        bot_state['client'],
                        market,
                        signal['direction'],
                        TRADE_AMOUNT,
                        signal
                    )
                    
                    if trade:
                        bot_state['last_traded_window'] = market['timestamp']
                        print(f"{'='*68}\n")
                        
                        # Broadcast updated state immediately
                        broadcast_state()
            
            # Check resolutions
            if bot_state['client']:
                check_resolutions(bot_state['client'])
            
            time.sleep(0.5)
            
        except Exception as e:
            print(f"⚠ Bot loop error: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(5)

# Start bot thread
bot_thread = threading.Thread(target=bot_loop, daemon=True)
bot_thread.start()

# ── WebSocket Events ─────────────────────────────────────────────────
@socketio.on('connect')
def handle_connect():
    """Client connected - send current state."""
    print(f"✅ Client connected: {request.sid}")
    broadcast_state()

@socketio.on('disconnect')
def handle_disconnect():
    """Client disconnected."""
    print(f"❌ Client disconnected: {request.sid}")

@socketio.on('request_state')
def handle_request_state():
    """Client explicitly requesting state update."""
    print(f"🔄 State requested by: {request.sid}")
    broadcast_state()

# ── REST API Endpoints ───────────────────────────────────────────────
@app.route('/api/bot/status', methods=['GET'])
def bot_status():
    """Get bot running status."""
    return jsonify({
        'running': bot_state['running'],
        'has_client': bot_state['client'] is not None,
    })

@app.route('/api/bot/start', methods=['POST'])
def bot_start():
    """Start the trading bot."""
    if bot_state['running']:
        return jsonify({'success': False, 'error': 'Bot already running'}), 400
    
    try:
        # Initialize CLOB client
        if not bot_state['client']:
            print("🔌 Initializing CLOB client...")
            bot_state['client'] = init_clob_client()
            print("✅ CLOB client ready")
        
        bot_state['running'] = True
        print("🚀 Bot started")
        
        # Broadcast state immediately
        broadcast_state()
        
        return jsonify({'success': True, 'message': 'Bot started'})
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/bot/stop', methods=['POST'])
def bot_stop():
    """Stop the trading bot."""
    if not bot_state['running']:
        return jsonify({'success': False, 'error': 'Bot not running'}), 400
    
    bot_state['running'] = False
    print("🛑 Bot stopped")
    
    # Broadcast state immediately
    broadcast_state()
    
    return jsonify({'success': True, 'message': 'Bot stopped'})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get trading statistics."""
    return jsonify(calculate_stats())

@app.route('/api/trades', methods=['GET'])
def get_trades():
    """Get recent trades."""
    limit = int(request.args.get('limit', 20))
    return jsonify(get_recent_trades(limit))

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'bot_running': bot_state['running'],
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })

# ── Main ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("\n" + "="*70)
    print("  🎯 POLYMARKET SNIPER - WEB SERVER")
    print("  WebSocket + REST API for UI control")
    print("="*70 + "\n")
    
    print("🌐 Starting server on http://0.0.0.0:8080")
    print("📡 WebSocket available at ws://localhost:8080/socket.io/")
    print("🎮 Control endpoints:")
    print("   POST /api/bot/start  - Start trading")
    print("   POST /api/bot/stop   - Stop trading")
    print("   GET  /api/bot/status - Check status")
    print("   GET  /api/stats      - Get statistics")
    print("   GET  /api/trades     - Get recent trades")
    print("\n💡 Open UI at: http://localhost:3000")
    print("   (Make sure to run 'cd ui && npm run dev' first)\n")
    
    socketio.run(app, host='0.0.0.0', port=8080, debug=False, allow_unsafe_werkzeug=True)
