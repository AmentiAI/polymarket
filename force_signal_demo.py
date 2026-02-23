#!/usr/bin/env python3
"""
FORCE SIGNAL DEMO
-----------------
Creates perfect conditions to show what a wick arbitrage signal looks like.
"""

from wick_arbitrage import WickArbitrage
import time

def demo_signal():
    """Force a signal by creating perfect conditions."""
    arb = WickArbitrage()
    
    print("🔥 WICK ARBITRAGE SIGNAL DEMO")
    print("=" * 80)
    print("Creating perfect arbitrage conditions...\n")
    
    # Fetch real candles
    one_min = arb.fetch_1min_candles(10)
    five_min = arb.fetch_5min_candles(20)
    
    if not one_min or not five_min:
        print("❌ Failed to fetch candles")
        return
    
    # Get current BTC price
    current_btc = one_min[-1]['close']
    
    # Create a PERFECT scenario with EXTREME wick (>5x triggers automatically)
    perfect_candle = {
        'time': int(time.time()),
        'open': current_btc,
        'high': current_btc + 500,  # EXTREME wick up (5x+ body)
        'low': current_btc - 10,
        'close': current_btc + 10,  # Tiny body
        'volume': 1000000
    }
    
    # Calculate the wick ratio
    wick_ratio, wick_direction = arb.check_body_vs_wick_ratio(perfect_candle)
    
    print(f"📊 Created Perfect 5-min Candle:")
    print(f"   Open:  ${perfect_candle['open']:.2f}")
    print(f"   High:  ${perfect_candle['high']:.2f} ← WICK UP!")
    print(f"   Low:   ${perfect_candle['low']:.2f}")
    print(f"   Close: ${perfect_candle['close']:.2f}")
    print(f"   Body:  ${abs(perfect_candle['close'] - perfect_candle['open']):.2f}")
    print(f"   Upper Wick: ${perfect_candle['high'] - max(perfect_candle['open'], perfect_candle['close']):.2f}")
    print(f"   Wick Ratio: {wick_ratio:.1f}x body ← HUGE!")
    print()
    
    # Calculate fair value
    fair_price = arb.calculate_fair_price(wick_direction, wick_ratio)
    print(f"💰 Fair Value Calculation:")
    print(f"   Wick ratio: {wick_ratio:.1f}x")
    print(f"   Direction: {wick_direction.upper()} (wick rejected upwards)")
    print(f"   Fair value for DOWN shares: ${fair_price:.2f}")
    print()
    
    # Create CHEAP Polymarket prices (arbitrage!)
    if wick_direction == 'up':
        # Big wick up = people still bullish = DOWN shares CHEAP
        poly_up = 0.75    # UP shares expensive (people still think it's going up)
        poly_down = 0.20  # DOWN shares CHEAP (haven't realized the rejection)
        
        print(f"📈 Polymarket Prices (MISPRICED!):")
        print(f"   UP shares:   ${poly_up:.2f} (expensive - people still bullish)")
        print(f"   DOWN shares: ${poly_down:.2f} ← CHEAP! (haven't realized rejection)")
        print(f"   Fair value:  ${fair_price:.2f}")
        print(f"   Spread:      ${fair_price - poly_down:.2f} = {((fair_price - poly_down) / poly_down * 100):.1f}% profit!")
        print()
    
    # Check for signal
    signal = arb.check_arbitrage_opportunity(
        one_min,
        five_min,
        perfect_candle,
        poly_up,
        poly_down
    )
    
    if signal:
        print("\n" + "=" * 80)
        print("🔥🔥🔥 SIGNAL DETECTED! 🔥🔥🔥")
        print("=" * 80)
        print(f"Direction:        {signal['direction'].upper()}")
        print(f"Reason:           {signal['reason'].replace('_', ' ').title()}")
        print(f"Entry Price:      ${signal['entry_price']:.2f}")
        print(f"Fair Value:       ${signal['fair_price']:.2f}")
        print(f"Profit Potential: {signal['profit_potential']:.1f}%")
        print(f"Confidence:       {signal['confidence']*100:.1f}%")
        print(f"Wick Ratio:       {signal['wick_ratio']:.1f}x body")
        print("=" * 80)
        print()
        print("💡 This is what you'll see in the UI:")
        print("   - Orange/purple animated panel")
        print("   - Entry: $0.20 / Fair: $0.55")
        print("   - Profit Potential: +175%")
        print("   - Confidence: 85%")
        print()
        print("💰 The Trade:")
        print("   1. Buy 100 DOWN shares @ $0.20 = $20")
        print("   2. Wait 30-120 seconds for market to realize")
        print("   3. Sell 100 shares @ $0.50 = $50")
        print("   4. Profit: $30 (150% gain) in 60 seconds!")
        print()
    else:
        print("⚠ Signal not detected (this shouldn't happen with perfect conditions!)")
        print(f"Debug: Wick ratio {wick_ratio:.1f}x, Fair ${fair_price:.2f}, Entry ${poly_down:.2f}")
    
    print("=" * 80)

if __name__ == "__main__":
    demo_signal()
