#!/usr/bin/env python3
"""
Polymarket CLOB API Integration  
--------------------------------
Fetches live share prices for BTC 5-min UP/DOWN markets.
"""

import requests
from typing import Dict, List, Optional
import time
from datetime import datetime, timedelta

class PolymarketAPI:
    """Interface to Polymarket CLOB API."""
    
    def __init__(self):
        self.clob_url = "https://clob.polymarket.com"
        self.gamma_url = "https://gamma-api.polymarket.com"
        self._cache = {}
        self._cache_time = 0
        self._cache_ttl = 5  # Cache for 5 seconds
    
    def get_btc_5min_markets(self) -> List[Dict]:
        """
        Get all active BTC 5-minute UP/DOWN markets.
        These markets run continuously every 5 minutes.
        """
        try:
            # Check cache first
            now = time.time()
            if self._cache and (now - self._cache_time < self._cache_ttl):
                return self._cache.get('markets', [])
            
            # Fetch from CLOB sampling markets endpoint
            url = f"{self.clob_url}/sampling-markets"
            resp = requests.get(url, timeout=10)
            
            if resp.status_code != 200:
                print(f"⚠ CLOB API error: {resp.status_code}")
                return []
            
            data = resp.json()
            all_markets = data.get('data', [])
            
            # Filter for BTC 5-minute markets
            # These have questions like "BTC 5 Minute Up or Down"
            btc_5min = []
            for market in all_markets:
                question = market.get('question', '').lower()
                
                # Look for BTC + 5 minute keywords
                if ('btc' in question or 'bitcoin' in question) and \
                   ('5 minute' in question or '5-minute' in question or '5min' in question):
                    
                    # Must be accepting orders and not closed
                    if market.get('accepting_orders') and not market.get('closed'):
                        btc_5min.append(market)
            
            # Cache results
            self._cache = {'markets': btc_5min}
            self._cache_time = now
            
            return btc_5min
            
        except Exception as e:
            print(f"❌ BTC 5-min markets fetch error: {e}")
            return []
    
    def get_current_btc_5min_market(self) -> Optional[Dict]:
        """
        Get the currently active BTC 5-minute market.
        Returns the market ending soonest (the current one).
        """
        try:
            markets = self.get_btc_5min_markets()
            
            if not markets:
                return None
            
            # Find the market ending soonest (current active market)
            now = datetime.utcnow()
            active_markets = []
            
            for market in markets:
                end_date_str = market.get('end_date_iso')
                if not end_date_str:
                    continue
                
                try:
                    end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                    
                    # Only consider markets ending in the future
                    if end_date > now:
                        time_until_end = (end_date - now).total_seconds()
                        market['_time_until_end'] = time_until_end
                        active_markets.append(market)
                except:
                    continue
            
            if not active_markets:
                return None
            
            # Return the one ending soonest
            current = min(active_markets, key=lambda m: m['_time_until_end'])
            return current
            
        except Exception as e:
            print(f"❌ Current market fetch error: {e}")
            return None
    
    def get_token_price(self, token_id: str) -> Optional[float]:
        """Get current mid price for a token."""
        try:
            url = f"{self.clob_url}/price"
            params = {"token_id": token_id}
            
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code != 200:
                return None
            
            data = resp.json()
            # Use mid price (average of bid/ask)
            return float(data.get('mid', 0.5))
            
        except Exception as e:
            print(f"❌ Token price fetch error: {e}")
            return None
    
    def get_btc_candle_prices(self, market_id: Optional[str] = None, simulate: bool = False) -> Optional[Dict]:
        """
        Get live prices for BTC 5-min UP/DOWN market.
        
        Returns:
            {
                'up_price': float,  # Price of UP shares
                'down_price': float,  # Price of DOWN shares
                'market': dict,  # Market info
                'simulated': False
            }
            
            Returns None if no live market found.
        """
        try:
            # Get current active market
            market = self.get_current_btc_5min_market()
            
            if not market:
                print("⚠ No active BTC 5-min market found")
                return None
            
            # Get tokens
            tokens = market.get('tokens', [])
            if len(tokens) < 2:
                print(f"⚠ Market has {len(tokens)} tokens (need 2)")
                return None
            
            # Identify UP and DOWN tokens
            # Usually first is UP/Yes, second is DOWN/No
            up_token = None
            down_token = None
            
            for token in tokens:
                outcome = token.get('outcome', '').lower()
                if 'up' in outcome or 'yes' in outcome:
                    up_token = token
                elif 'down' in outcome or 'no' in outcome:
                    down_token = token
            
            # Fallback if outcome names unclear
            if not up_token:
                up_token = tokens[0]
            if not down_token:
                down_token = tokens[1]
            
            # Get prices
            up_price = self.get_token_price(up_token['token_id'])
            down_price = self.get_token_price(down_token['token_id'])
            
            if up_price is None or down_price is None:
                print("⚠ Failed to fetch token prices")
                return None
            
            return {
                'up_price': up_price,
                'down_price': down_price,
                'market': {
                    'question': market['question'],
                    'condition_id': market['condition_id'],
                    'end_date': market.get('end_date_iso'),
                    'up_token': up_token['token_id'],
                    'down_token': down_token['token_id'],
                },
                'simulated': False,
            }
            
        except Exception as e:
            print(f"❌ BTC candle prices error: {e}")
            import traceback
            traceback.print_exc()
            return None


def test_api():
    """Test the API integration."""
    print("🔍 Testing Polymarket API Integration...")
    print("=" * 80)
    
    api = PolymarketAPI()
    
    # Get BTC 5-min markets
    print("\n📊 Fetching BTC 5-minute markets...")
    markets = api.get_btc_5min_markets()
    
    if markets:
        print(f"✅ Found {len(markets)} BTC 5-minute markets")
        for i, market in enumerate(markets[:5], 1):
            print(f"\n{i}. {market['question']}")
            print(f"   End date: {market.get('end_date_iso')}")
            print(f"   Accepting orders: {market.get('accepting_orders')}")
    else:
        print("❌ No BTC 5-minute markets found")
        return
    
    # Get current market
    print("\n\n🎯 Getting current active market...")
    current = api.get_current_btc_5min_market()
    
    if current:
        print(f"✅ Current market: {current['question']}")
        print(f"   Ends: {current.get('end_date_iso')}")
        print(f"   Time until end: {current.get('_time_until_end', 0):.0f} seconds")
    else:
        print("❌ No current market found")
        return
    
    # Get live prices
    print("\n\n💰 Fetching live prices...")
    prices = api.get_btc_candle_prices()
    
    if prices:
        print("✅ Live Prices:")
        print(f"   UP shares:   ${prices['up_price']:.4f}")
        print(f"   DOWN shares: ${prices['down_price']:.4f}")
        print(f"   Total:       ${prices['up_price'] + prices['down_price']:.4f}")
        print(f"\n📋 Market: {prices['market']['question']}")
        print(f"   Ends: {prices['market']['end_date']}")
        print(f"   UP token: {prices['market']['up_token'][:16]}...")
        print(f"   DOWN token: {prices['market']['down_token'][:16]}...")
    else:
        print("❌ Failed to fetch prices")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    test_api()
