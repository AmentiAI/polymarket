#!/usr/bin/env python3
"""
LIVE WICK MONITOR
-----------------
Shows real-time wick formation and arbitrage opportunities.
Updates every 5 seconds with current market conditions.
"""

import os
import sys
from wick_arbitrage import WickArbitrage
from polymarket_api import PolymarketAPI
import time
from datetime import datetime

def clear_screen():
    """Clear terminal screen."""
    os.system('clear' if os.name != 'nt' else 'cls')

def color_text(text, color_code):
    """Add ANSI color to text."""
    return f"\033[{color_code}m{text}\033[0m"

def monitor_wicks():
    """Real-time wick monitoring with visual feedback."""
    arb = WickArbitrage()
    poly_api = PolymarketAPI()
    
    print(color_text("=" * 80, "1;36"))  # Cyan
    print(color_text("🔥 LIVE WICK ARBITRAGE MONITOR", "1;33"))  # Yellow
    print(color_text("=" * 80, "1;36"))
    print(color_text("Strategy: Detect wick formation → Buy mispriced shares → Quick profit", "0;37"))
    print(color_text("Updates: Every 5 seconds", "0;37"))
    print(color_text("Prices: REAL Polymarket API only (NO SIMULATION)", "0;37"))
    print(color_text("=" * 80, "1;36"))
    print()
    
    signal_count = 0
    
    while True:
        try:
            # Fetch candles
            one_min = arb.fetch_1min_candles(10)
            five_min = arb.fetch_5min_candles(20)
            
            if not one_min or not five_min:
                print(color_text("⚠ Failed to fetch candles, retrying...", "1;31"))
                time.sleep(5)
                continue
            
            # Current 5-min candle (forming)
            current_5min = five_min[-1]
            current_btc = one_min[-1]['close']
            
            # Calculate wick stats
            wick_ratio, wick_direction = arb.check_body_vs_wick_ratio(current_5min)
            
            # Check 5-min setup
            setup = arb.check_5min_setup(five_min)
            
            # Check for failed breakouts
            failed_hh = arb.detect_failed_higher_high(one_min, current_5min['high'])
            failed_ll = arb.detect_failed_lower_low(one_min, current_5min['low'])
            
            # Get REAL Polymarket prices (NO SIMULATION)
            signal = None  # Default to no signal
            
            try:
                poly_prices = poly_api.get_btc_candle_prices(simulate=False)
                
                if poly_prices and not poly_prices.get('simulated'):
                    up_price = poly_prices['up_price']
                    down_price = poly_prices['down_price']
                    
                    # Only check for arbitrage with real prices
                    signal = arb.check_arbitrage_opportunity(
                        one_min,
                        five_min,
                        current_5min,
                        up_price,
                        down_price
                    )
                else:
                    # No real market data - skip this iteration
                    up_price = None
                    down_price = None
                    
            except Exception as e:
                up_price = None
                down_price = None
            
            # Display current state
            now = datetime.now().strftime("%H:%M:%S")
            
            # Clear and redraw
            print(f"\r\033[K", end='')  # Clear line
            print(f"⏰ {now} | BTC: ${current_btc:,.2f}", end=' | ')
            
            # Wick status
            if wick_ratio >= 2.0:
                wick_color = "1;32" if wick_ratio >= 3.0 else "1;33"  # Green or yellow
                print(color_text(f"WICK: {wick_ratio:.1f}x {wick_direction.upper()}", wick_color), end=' | ')
            else:
                print(color_text(f"Wick: {wick_ratio:.1f}x {wick_direction}", "0;37"), end=' | ')
            
            # Setup bias
            if setup == 'bearish':
                print(color_text("📉 BEARISH", "1;31"), end=' | ')
            elif setup == 'bullish':
                print(color_text("📈 BULLISH", "1;32"), end=' | ')
            else:
                print(color_text("━ Neutral", "0;37"), end=' | ')
            
            # Failed breakouts
            if failed_hh:
                print(color_text("❌ Failed HH", "1;35"), end=' | ')
            if failed_ll:
                print(color_text("✅ Failed LL", "1;36"), end=' | ')
            
            # Polymarket prices
            if up_price is not None and down_price is not None:
                print(color_text(f"UP ${up_price:.2f} / DOWN ${down_price:.2f}", "0;36"), end=' | ')
            else:
                print(color_text("⚠ No live market", "1;33"), end=' | ')
            
            # SIGNAL DETECTED
            if signal:
                signal_count += 1
                print()  # New line
                print(color_text("\n" + "=" * 80, "1;33"))
                print(color_text(f"🔥 SIGNAL #{signal_count} DETECTED!", "1;33"))
                print(color_text("=" * 80, "1;33"))
                print(color_text(f"Direction:       {signal['direction'].upper()}", "1;37"))
                print(color_text(f"Reason:          {signal['reason'].replace('_', ' ').title()}", "1;37"))
                print(color_text(f"Entry Price:     ${signal['entry_price']:.2f}", "0;36"))
                print(color_text(f"Fair Value:      ${signal['fair_price']:.2f}", "1;32"))
                print(color_text(f"Profit Potential: {signal['profit_potential']:.1f}%", "1;32"))
                print(color_text(f"Confidence:      {signal['confidence']*100:.1f}%", "1;37"))
                print(color_text(f"Wick Ratio:      {signal['wick_ratio']:.1f}x body", "1;37"))
                print(color_text("=" * 80, "1;33"))
                print()
            else:
                print(color_text("⏳ Monitoring...", "0;37"), end='')
            
            sys.stdout.flush()
            time.sleep(5)
            
        except KeyboardInterrupt:
            print(color_text("\n\n👋 Monitor stopped", "1;36"))
            print(color_text(f"Total signals detected: {signal_count}", "1;37"))
            break
        except Exception as e:
            print(color_text(f"\n❌ Error: {e}", "1;31"))
            time.sleep(5)

if __name__ == "__main__":
    monitor_wicks()
