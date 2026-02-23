"""
Bot module - Provides indicator calculations and market data for candle_server.py
"""

import requests
import json
import time
from typing import List, Dict, Tuple, Optional
import numpy as np


# ══════════════════════════════════════════════════════════════════════════
# Binance API - Candle Data
# ══════════════════════════════════════════════════════════════════════════

def fetch_candles(symbol="BTCUSDT", interval="5m", limit=500) -> List[Dict]:
    """Fetch OHLCV candles from Binance."""
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        candles = []
        for k in data:
            candles.append({
                "timestamp": int(k[0]),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
            })
        
        return candles
    except Exception as e:
        print(f"[bot] fetch_candles error: {e}")
        return []


def get_indicators() -> Dict:
    """Get current indicators (price, RSI, MACD, candles)."""
    candles_5m = fetch_candles(interval="5m", limit=200)
    
    if not candles_5m:
        return {
            "price": 0,
            "candles_5m": [],
            "rsi_1m": 50,
            "rsi_5m": 50,
            "macd_1m": None,
            "macd_5m": None,
            "confluence_score": 0,
            "confluence_details": {},
        }
    
    price = candles_5m[-1]["close"]
    closes = [c["close"] for c in candles_5m]
    
    # RSI
    rsi_series = calculate_rsi_series(closes, 14)
    rsi_5m = rsi_series[-1] if rsi_series else 50
    
    # MACD
    macd_line, signal_line, hist_line, macd_offset = calculate_macd_full_series(closes)
    macd_5m = {"histogram": hist_line[-1]} if hist_line else None
    
    # 1m indicators
    candles_1m = fetch_candles(interval="1m", limit=100)
    if candles_1m:
        closes_1m = [c["close"] for c in candles_1m]
        rsi_1m_series = calculate_rsi_series(closes_1m, 14)
        rsi_1m = rsi_1m_series[-1] if rsi_1m_series else 50
        
        macd_1m_line, _, macd_1m_hist, _ = calculate_macd_full_series(closes_1m)
        macd_1m = {"histogram": macd_1m_hist[-1]} if macd_1m_hist else None
    else:
        rsi_1m = 50
        macd_1m = None
    
    # Confluence score (simple)
    conf_score = 0
    if rsi_5m > 60:
        conf_score -= 1.5
    elif rsi_5m < 40:
        conf_score += 1.5
    
    return {
        "price": price,
        "candles_5m": candles_5m,
        "rsi_1m": rsi_1m,
        "rsi_5m": rsi_5m,
        "macd_1m": macd_1m,
        "macd_5m": macd_5m,
        "confluence_score": conf_score,
        "confluence_details": {
            "rsi_5m": rsi_5m,
            "rsi_1m": rsi_1m,
        },
    }


# ══════════════════════════════════════════════════════════════════════════
# Technical Indicators
# ══════════════════════════════════════════════════════════════════════════

def calculate_rsi_series(prices: List[float], period: int = 14) -> List[float]:
    """Calculate RSI series."""
    if len(prices) < period + 1:
        return []
    
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gain = np.convolve(gains, np.ones(period) / period, mode='valid')
    avg_loss = np.convolve(losses, np.ones(period) / period, mode='valid')
    
    rs = np.where(avg_loss != 0, avg_gain / avg_loss, 100)
    rsi = 100 - (100 / (1 + rs))
    
    # Pad to match input length
    result = [50.0] * period
    result.extend(rsi.tolist())
    
    return result


def calculate_macd_full_series(prices: List[float], fast=12, slow=26, signal=9) -> Tuple[List[float], List[float], List[float], int]:
    """Calculate MACD line, signal line, and histogram."""
    if len(prices) < slow + signal:
        return [], [], [], 0
    
    prices_arr = np.array(prices)
    
    # EMA calculation
    ema_fast = _ema(prices_arr, fast)
    ema_slow = _ema(prices_arr, slow)
    
    # MACD line
    macd_line = ema_fast - ema_slow
    
    # Signal line
    signal_line = _ema(macd_line, signal)
    
    # Histogram
    histogram = macd_line - signal_line
    
    # Offset (number of initial values missing)
    offset = slow + signal - 1
    
    return macd_line.tolist(), signal_line.tolist(), histogram.tolist(), offset


def calculate_ema_series(prices: List[float], period: int) -> List[float]:
    """Calculate EMA series."""
    if len(prices) < period:
        return []
    
    prices_arr = np.array(prices)
    ema = _ema(prices_arr, period)
    return ema.tolist()


def _ema(data: np.ndarray, period: int) -> np.ndarray:
    """Calculate exponential moving average."""
    alpha = 2 / (period + 1)
    ema = np.zeros_like(data)
    ema[0] = data[0]
    
    for i in range(1, len(data)):
        ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
    
    return ema


# ══════════════════════════════════════════════════════════════════════════
# Streak Analysis (Placeholder)
# ══════════════════════════════════════════════════════════════════════════

def analyze_streak_reversals(candles: List[Dict]) -> Dict:
    """Analyze streak reversals (placeholder)."""
    return {}


def extract_winning_patterns(streak_results: Dict) -> List:
    """Extract winning patterns (placeholder)."""
    return []


# ══════════════════════════════════════════════════════════════════════════
# Polymarket CLOB API (Placeholder - needs real implementation)
# ══════════════════════════════════════════════════════════════════════════

def init_client():
    """Initialize Polymarket CLOB client (placeholder)."""
    return None


def get_clob_prices(token_id: str) -> Optional[Dict]:
    """Get CLOB prices for token (placeholder)."""
    # TODO: Real implementation needed
    return {"buy": 0.50, "sell": 0.50}


def get_active_market_clob_prices(event_slug: str) -> Optional[Dict]:
    """Get active market CLOB prices (placeholder)."""
    # TODO: Real implementation needed
    return None


def fetch_market_prices(event_slug: str) -> Optional[Dict]:
    """Fetch market prices (placeholder)."""
    # TODO: Real implementation needed
    return None


def fetch_market_by_slug(event_slug: str) -> Optional[Dict]:
    """Fetch market by slug (placeholder)."""
    # TODO: Real implementation needed
    return None


def buy_on_market(client, market: Dict, direction: str, amount: float) -> Optional[Dict]:
    """Buy on market (placeholder)."""
    # TODO: Real implementation needed
    return None


def market_sell(client, position: Dict) -> Optional[Dict]:
    """Sell position (placeholder)."""
    # TODO: Real implementation needed
    return None


def discord_notify(message: str):
    """Send Discord notification (placeholder)."""
    print(f"[NOTIFY] {message}")


# ══════════════════════════════════════════════════════════════════════════
# Export
# ══════════════════════════════════════════════════════════════════════════

__all__ = [
    "fetch_candles",
    "get_indicators",
    "calculate_rsi_series",
    "calculate_macd_full_series",
    "calculate_ema_series",
    "analyze_streak_reversals",
    "extract_winning_patterns",
    "init_client",
    "get_clob_prices",
    "get_active_market_clob_prices",
    "fetch_market_prices",
    "fetch_market_by_slug",
    "buy_on_market",
    "market_sell",
    "discord_notify",
]
