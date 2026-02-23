#!/usr/bin/env python3
"""
Seed validation log with historical backtesting
"""

from advanced_predictor import predict_advanced
from prediction_validator import backtest_predictions, save_validation_entry
from sniper_bot import get_proxy
import requests

print("🔬 Running historical backtest to seed validation data...")

# Fetch historical candles
try:
    all_candles = []
    
    for i in range(3):  # Fetch 3000 candles (about 10 days)
        resp = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={
                "symbol": "BTCUSDT",
                "interval": "5m",
                "limit": 1000,
                "endTime": int(all_candles[0]['time'] * 1000) - 1 if all_candles else None
            },
            proxies=get_proxy(),
            timeout=10
        )
        
        if resp.status_code != 200:
            print(f"⚠ Request {i+1} failed")
            break
        
        batch = resp.json()
        for c in batch:
            all_candles.insert(0, {
                'time': int(c[0]) // 1000,
                'open': float(c[1]),
                'high': float(c[2]),
                'low': float(c[3]),
                'close': float(c[4]),
            })
        
        if len(all_candles) >= 3000:
            break
        
        print(f"  Fetched batch {i+1}: {len(all_candles)} total candles")
    
    print(f"\n✅ Fetched {len(all_candles)} historical candles")
    
    # Run backtest
    print("\n🔬 Running backtest...")
    results = backtest_predictions(all_candles, predict_advanced)
    
    if 'error' in results:
        print(f"❌ Backtest failed: {results['error']}")
    else:
        print(f"\n📊 Backtest Results:")
        print(f"   Total tests: {results['total_tests']}")
        print(f"   Directional accuracy: {results['directional_accuracy']:.1f}%")
        print(f"   Range accuracy: {results['range_accuracy']:.1f}%")
        print(f"   High confidence (>70%) count: {results['high_confidence_count']}")
        print(f"   High confidence accuracy: {results['high_confidence_accuracy']:.1f}%")
        
        # Save results as validation entries for calibration
        print(f"\n💾 Saving backtest results to validation log...")
        
        # Take sample of results to seed the log
        sample_size = min(100, results['total_tests'])
        step = max(1, results['total_tests'] // sample_size)
        
        count = 0
        for i in range(100, len(all_candles) - 1, step):
            if count >= sample_size:
                break
            
            try:
                # Get historical data up to this point
                hist_data = all_candles[:i]
                
                # Make prediction
                pred = predict_advanced(hist_data)
                
                # Actual next candle
                actual = all_candles[i + 1]
                
                # Save validation entry
                save_validation_entry(pred, actual)
                count += 1
                
                if count % 10 == 0:
                    print(f"  Saved {count}/{sample_size} validation entries...")
            except:
                continue
        
        print(f"\n✅ Seeded validation log with {count} historical predictions!")
        print(f"   This provides real accuracy metrics based on actual backtest data.")
        
except Exception as e:
    print(f"❌ Failed to seed validation data: {e}")
    import traceback
    traceback.print_exc()
