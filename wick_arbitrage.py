"""
WICK ARBITRAGE STRATEGY
-----------------------
Exploit pricing inefficiency between real-time BTC price action and Polymarket share prices.

Core Idea:
- Monitor 1-min candles during 5-min candle formation
- Detect failed breakouts (wick formation) EARLY
- Buy mispriced shares before the market adjusts
- Sell when prices converge (30sec-2min later)
- Don't wait for candle close - profit from the wick itself

Entry Logic:
1. 5-min candle has directional bias (RSI/MACD setup)
2. 1-min shows failed breakout (higher high rejected OR lower low bounced)
3. Current 5-min body is small vs wick (indecision)
4. Polymarket shares are CHEAP relative to wick reality
5. Buy the mispriced shares immediately

Exit Logic:
- Sell when Polymarket prices adjust to match the wick
- Target: 50-100% profit on shares (buy $0.20, sell $0.40-0.60)
- Time: Usually within 30sec-2min of entry
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import time

class WickArbitrage:
    def __init__(self):
        self.current_5min_start = None
        self.one_min_candles = []  # Store last 10 1-min candles
        self.five_min_candles = []  # Store last 20 5-min candles
        
    def fetch_1min_candles(self, limit=10) -> List[Dict]:
        """Fetch recent 1-min BTC candles from Coinbase"""
        try:
            import time as time_module
            end_time = int(time_module.time())
            start_time = end_time - (limit * 60)  # 60 seconds per candle
            
            url = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
            params = {
                "start": start_time,
                "end": end_time,
                "granularity": 60  # 1 minute
            }
            r = requests.get(url, params=params, timeout=5)
            if r.status_code != 200:
                return []
            
            candles = []
            data = r.json()
            # Coinbase returns: [ time, low, high, open, close, volume ]
            for k in reversed(data[-limit:]):  # Reverse to get chronological order
                candles.append({
                    'time': k[0],
                    'open': float(k[3]),
                    'high': float(k[2]),
                    'low': float(k[1]),
                    'close': float(k[4]),
                    'volume': float(k[5])
                })
            return candles
        except Exception as e:
            print(f"Error fetching 1-min candles: {e}")
            return []
    
    def fetch_5min_candles(self, limit=20) -> List[Dict]:
        """Fetch recent 5-min BTC candles from Coinbase"""
        try:
            import time as time_module
            end_time = int(time_module.time())
            start_time = end_time - (limit * 300)  # 300 seconds per 5-min candle
            
            url = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
            params = {
                "start": start_time,
                "end": end_time,
                "granularity": 300  # 5 minutes
            }
            r = requests.get(url, params=params, timeout=5)
            if r.status_code != 200:
                return []
            
            candles = []
            data = r.json()
            # Coinbase returns: [ time, low, high, open, close, volume ]
            for k in reversed(data[-limit:]):  # Reverse to get chronological order
                candles.append({
                    'time': k[0],
                    'open': float(k[3]),
                    'high': float(k[2]),
                    'low': float(k[1]),
                    'close': float(k[4]),
                    'volume': float(k[5])
                })
            return candles
        except Exception as e:
            print(f"Error fetching 5-min candles: {e}")
            return []
    
    def calculate_rsi(self, prices: List[float], period=14) -> float:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, prices: List[float]) -> Tuple[float, float, float]:
        """Calculate MACD (12, 26, 9)"""
        if len(prices) < 26:
            return 0.0, 0.0, 0.0
        
        ema12 = self._ema(prices, 12)
        ema26 = self._ema(prices, 26)
        macd = ema12 - ema26
        
        # Signal line
        macd_values = [ema12 - ema26 for _ in range(9)]
        signal = self._ema(macd_values, 9)
        
        histogram = macd - signal
        return macd, signal, histogram
    
    def _ema(self, prices: List[float], period: int) -> float:
        """Calculate EMA"""
        if len(prices) < period:
            return sum(prices) / len(prices)
        
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def detect_failed_higher_high(self, one_min_candles: List[Dict], current_5min_high: float) -> bool:
        """
        Detect failed higher high (wick up forming)
        - Recent 1-min tried to break above current 5-min high
        - Got rejected (high wick, closed lower)
        """
        if len(one_min_candles) < 3:
            return False
        
        last_3 = one_min_candles[-3:]
        
        # Check if any tried to break current 5-min high
        breakout_attempt = False
        for candle in last_3:
            if candle['high'] > current_5min_high:
                breakout_attempt = True
                break
        
        if not breakout_attempt:
            return False
        
        # Check if the latest candle rejected (closed below high)
        latest = one_min_candles[-1]
        wick_size = latest['high'] - latest['close']
        body_size = abs(latest['close'] - latest['open'])
        
        # Wick should be at least 2x body size for rejection
        if body_size > 0 and wick_size / body_size > 2.0:
            return True
        
        return False
    
    def detect_failed_lower_low(self, one_min_candles: List[Dict], current_5min_low: float) -> bool:
        """
        Detect failed lower low (wick down forming)
        - Recent 1-min tried to break below current 5-min low
        - Got rejected (low wick, closed higher)
        """
        if len(one_min_candles) < 3:
            return False
        
        last_3 = one_min_candles[-3:]
        
        # Check if any tried to break current 5-min low
        breakout_attempt = False
        for candle in last_3:
            if candle['low'] < current_5min_low:
                breakout_attempt = True
                break
        
        if not breakout_attempt:
            return False
        
        # Check if the latest candle rejected (closed above low)
        latest = one_min_candles[-1]
        wick_size = latest['close'] - latest['low']
        body_size = abs(latest['close'] - latest['open'])
        
        # Wick should be at least 2x body size for rejection
        if body_size > 0 and wick_size / body_size > 2.0:
            return True
        
        return False
    
    def check_5min_setup(self, five_min_candles: List[Dict]) -> str:
        """
        Check if 5-min has directional bias
        Returns: 'bearish', 'bullish', or 'neutral'
        """
        if len(five_min_candles) < 20:
            return 'neutral'
        
        closes = [c['close'] for c in five_min_candles]
        rsi = self.calculate_rsi(closes)
        macd, signal, _ = self.calculate_macd(closes)
        
        # Bearish setup: high RSI + MACD crossed down or about to
        if rsi > 60 and macd < signal:
            return 'bearish'
        
        # Bullish setup: low RSI + MACD crossed up or about to
        if rsi < 40 and macd > signal:
            return 'bullish'
        
        return 'neutral'
    
    def check_body_vs_wick_ratio(self, candle: Dict) -> Tuple[float, str]:
        """
        Check if body is small relative to wick (indecision)
        Returns: (ratio, dominant_wick_direction)
        """
        body = abs(candle['close'] - candle['open'])
        upper_wick = candle['high'] - max(candle['open'], candle['close'])
        lower_wick = min(candle['open'], candle['close']) - candle['low']
        
        total_wick = upper_wick + lower_wick
        
        if body == 0 or body < 1:  # Tiny body = strong indecision
            return 999.0, 'up' if upper_wick > lower_wick else 'down'
        
        ratio = total_wick / body
        direction = 'up' if upper_wick > lower_wick else 'down'
        
        return ratio, direction
    
    def calculate_fair_price(self, wick_direction: str, wick_ratio: float) -> float:
        """
        Estimate what DOWN/UP shares SHOULD cost based on wick formation
        
        Logic:
        - Larger wick = higher confidence in reversal
        - wick_ratio > 3.0 = strong reversal = shares should be $0.50+
        - wick_ratio 2.0-3.0 = medium = shares should be $0.35-0.50
        - wick_ratio < 2.0 = weak = shares should be $0.20-0.35
        """
        if wick_ratio > 3.0:
            return 0.55  # Strong reversal
        elif wick_ratio > 2.0:
            return 0.42  # Medium reversal
        else:
            return 0.28  # Weak reversal
    
    def check_arbitrage_opportunity(
        self,
        one_min_candles: List[Dict],
        five_min_candles: List[Dict],
        current_5min_candle: Dict,
        polymarket_up_price: float,
        polymarket_down_price: float
    ) -> Optional[Dict]:
        """
        Main arbitrage detector
        
        Returns signal dict if opportunity exists:
        {
            'direction': 'buy_down' or 'buy_up',
            'reason': 'failed_higher_high' or 'failed_lower_low',
            'entry_price': 0.20,
            'fair_price': 0.50,
            'profit_potential': 150.0,  # % profit
            'confidence': 0.85
        }
        """
        
        # Check 5-min directional bias
        setup = self.check_5min_setup(five_min_candles)
        
        # Check current 5-min body vs wick
        wick_ratio, wick_direction = self.check_body_vs_wick_ratio(current_5min_candle)
        
        # Must have indecision (wick > 1.5x body) - LOWERED THRESHOLD
        if wick_ratio < 1.5:
            return None
        
        # EXTREME WICK OVERRIDE: If wick is huge (>5x), skip directional requirement
        extreme_wick = wick_ratio > 5.0
        
        # Calculate what shares SHOULD cost
        fair_price = self.calculate_fair_price(wick_direction, wick_ratio)
        
        # BEARISH SETUP + FAILED HIGHER HIGH = BUY DOWN
        # OR EXTREME WICK UP (>5x body) = BUY DOWN regardless of setup
        if (setup == 'bearish' or extreme_wick) and wick_direction == 'up':
            failed_hh = self.detect_failed_higher_high(
                one_min_candles,
                current_5min_candle['high']
            )
            
            # For extreme wicks, we don't need a failed breakout - the wick IS the signal
            if (failed_hh or extreme_wick) and polymarket_down_price < fair_price * 0.85:
                # DOWN shares are cheap!
                profit_potential = ((fair_price - polymarket_down_price) / polymarket_down_price) * 100
                
                reason = 'extreme_wick_up' if extreme_wick else 'failed_higher_high'
                
                return {
                    'direction': 'buy_down',
                    'reason': reason,
                    'entry_price': polymarket_down_price,
                    'fair_price': fair_price,
                    'profit_potential': profit_potential,
                    'confidence': min(0.95, 0.5 + (wick_ratio / 10)),
                    'wick_ratio': wick_ratio
                }
        
        # BULLISH SETUP + FAILED LOWER LOW = BUY UP
        # OR EXTREME WICK DOWN (>5x body) = BUY UP regardless of setup
        if (setup == 'bullish' or extreme_wick) and wick_direction == 'down':
            failed_ll = self.detect_failed_lower_low(
                one_min_candles,
                current_5min_candle['low']
            )
            
            # For extreme wicks, we don't need a failed breakout - the wick IS the signal
            if (failed_ll or extreme_wick) and polymarket_up_price < fair_price * 0.85:
                # UP shares are cheap!
                profit_potential = ((fair_price - polymarket_up_price) / polymarket_up_price) * 100
                
                reason = 'extreme_wick_down' if extreme_wick else 'failed_lower_low'
                
                return {
                    'direction': 'buy_up',
                    'reason': reason,
                    'entry_price': polymarket_up_price,
                    'fair_price': fair_price,
                    'profit_potential': profit_potential,
                    'confidence': min(0.95, 0.5 + (wick_ratio / 10)),
                    'wick_ratio': wick_ratio
                }
        
        return None
    
    def should_exit_position(
        self,
        entry_price: float,
        current_price: float,
        fair_price: float,
        seconds_held: int
    ) -> bool:
        """
        Determine if we should exit the position
        
        Exit conditions:
        1. Price reached 80% of fair value = take profit
        2. Price moved against us by 20% = stop loss
        3. Held for 120+ seconds and price hasn't moved = timeout
        """
        
        # Take profit: reached 80% of expected fair price
        if current_price >= fair_price * 0.8:
            return True
        
        # Stop loss: price moved against us by 20%
        if current_price < entry_price * 0.8:
            return True
        
        # Timeout: held too long without movement
        if seconds_held > 120 and current_price < entry_price * 1.1:
            return True
        
        return False


def run_wick_arbitrage_scanner():
    """
    Main loop to scan for wick arbitrage opportunities
    """
    arb = WickArbitrage()
    
    print("🎯 WICK ARBITRAGE SCANNER STARTED")
    print("=" * 60)
    print("Strategy: Buy mispriced shares during wick formation")
    print("Target: 50-100% profit in 30sec-2min")
    print("=" * 60)
    
    while True:
        try:
            # Fetch data
            one_min = arb.fetch_1min_candles(10)
            five_min = arb.fetch_5min_candles(20)
            
            if not one_min or not five_min:
                print("❌ Failed to fetch candles, retrying...")
                time.sleep(5)
                continue
            
            # Current 5-min candle (forming)
            current_5min = five_min[-1]
            
            # Get REAL Polymarket prices (NO MOCK DATA)
            from polymarket_api import PolymarketAPI
            poly_api = PolymarketAPI()
            
            try:
                poly_prices = poly_api.get_btc_candle_prices(simulate=False)
                
                if not poly_prices or poly_prices.get('simulated'):
                    print("⚠ No live BTC 5-min market - waiting...", end='\r')
                    time.sleep(30)
                    continue
                
                up_price = poly_prices['up_price']
                down_price = poly_prices['down_price']
                
            except Exception as e:
                print(f"❌ Polymarket API error: {e}")
                time.sleep(30)
                continue
            
            # Check for arbitrage
            signal = arb.check_arbitrage_opportunity(
                one_min,
                five_min,
                current_5min,
                up_price,
                down_price
            )
            
            if signal:
                print(f"\n🔥 ARBITRAGE OPPORTUNITY DETECTED!")
                print(f"Direction: {signal['direction'].upper()}")
                print(f"Reason: {signal['reason']}")
                print(f"Entry Price: ${signal['entry_price']:.2f}")
                print(f"Fair Price: ${signal['fair_price']:.2f}")
                print(f"Profit Potential: {signal['profit_potential']:.1f}%")
                print(f"Confidence: {signal['confidence']*100:.1f}%")
                print(f"Wick Ratio: {signal['wick_ratio']:.1f}x body")
                print("-" * 60)
            else:
                # Just show we're monitoring
                current_price = one_min[-1]['close']
                wick_ratio, wick_dir = arb.check_body_vs_wick_ratio(current_5min)
                print(f"⏳ Monitoring... BTC: ${current_price:.2f} | Wick: {wick_ratio:.1f}x ({wick_dir})", end='\r')
            
            time.sleep(5)  # Check every 5 seconds
            
        except KeyboardInterrupt:
            print("\n\n👋 Scanner stopped")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    run_wick_arbitrage_scanner()
