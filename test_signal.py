#!/usr/bin/env python3
"""
FORCE TEST SIGNAL
-----------------
Shows what a wick arbitrage signal looks like by forcing one.
"""

from wick_arbitrage import WickArbitrage

def test_signal():
    """Force a test signal to show the UI."""
    arb = WickArbitrage()
    
    # Fetch real candles
    one_min = arb.fetch_1min_candles(10)
    five_min = arb.fetch_5min_candles(20)
    
    if not one_min or not five_min:
        print("❌ Failed to fetch candles")
        return
    
    current_5min = five_min[-1]
    
    # Check wick ratio
    wick_ratio, wick_direction = arb.check_body_vs_wick_ratio(current_5min)
    
    print(f"📊 Current 5-min candle:")
    print(f"   Open: ${current_5min['open']:.2f}")
    print(f"   High: ${current_5min['high']:.2f}")
    print(f"   Low: ${current_5min['low']:.2f}")
    print(f"   Close: ${current_5min['close']:.2f}")
    print(f"   Wick Ratio: {wick_ratio:.1f}x {wick_direction.upper()}")
    print()
    
    # Calculate fair price
    fair_price = arb.calculate_fair_price(wick_direction, wick_ratio)
    print(f"💰 Fair Price Calculation:")
    print(f"   Wick ratio: {wick_ratio:.1f}x")
    print(f"   Fair value for shares: ${fair_price:.2f}")
    print()
    
    # Create CHEAP mock prices to trigger signal
    if wick_direction == 'up':
        # Wick up = buy DOWN shares
        mock_up = 0.75  # UP shares expensive
        mock_down = 0.15  # DOWN shares CHEAP
        print(f"🎯 Mock Polymarket Prices (to trigger signal):")
        print(f"   UP shares: ${mock_up:.2f} (expensive)")
        print(f"   DOWN shares: ${mock_down:.2f} (CHEAP!)")
        print(f"   Fair value: ${fair_price:.2f}")
        print(f"   Arbitrage: DOWN is ${(fair_price - mock_down):.2f} below fair value!")
    else:
        # Wick down = buy UP shares
        mock_up = 0.15  # UP shares CHEAP
        mock_down = 0.75  # DOWN shares expensive
        print(f"🎯 Mock Polymarket Prices (to trigger signal):")
        print(f"   UP shares: ${mock_up:.2f} (CHEAP!)")
        print(f"   DOWN shares: ${mock_down:.2f} (expensive)")
        print(f"   Fair value: ${fair_price:.2f}")
        print(f"   Arbitrage: UP is ${(fair_price - mock_up):.2f} below fair value!")
    
    print()
    
    # Check for signal
    signal = arb.check_arbitrage_opportunity(
        one_min,
        five_min,
        current_5min,
        mock_up,
        mock_down
    )
    
    if signal:
        print("=" * 80)
        print("🔥 SIGNAL DETECTED!")
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
        print("💡 This signal would appear in the UI as an orange/purple panel!")
        print("   showing you the cheap entry and expected profit.")
    else:
        print("⚠ No signal detected - market conditions not met")
        print("   (This means the wick isn't extreme enough or prices aren't cheap enough)")
    
    print()

if __name__ == "__main__":
    test_signal()
