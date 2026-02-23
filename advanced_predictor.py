#!/usr/bin/env python3
"""
Advanced Candle Prediction System
Multi-indicator ensemble with machine learning-inspired techniques
"""

import statistics
import math
from typing import List, Dict, Tuple

# ════════════════════════════════════════════════════════════════════
# TECHNICAL INDICATORS
# ════════════════════════════════════════════════════════════════════

def calculate_ema(prices: List[float], period: int) -> List[float]:
    """Calculate Exponential Moving Average."""
    if len(prices) < period:
        return [prices[-1]] if prices else [0]
    
    multiplier = 2 / (period + 1)
    ema_values = []
    
    # Start with SMA
    sma = statistics.mean(prices[:period])
    ema_values.append(sma)
    
    # Calculate EMA
    for price in prices[period:]:
        ema = (price * multiplier) + (ema_values[-1] * (1 - multiplier))
        ema_values.append(ema)
    
    return ema_values

def calculate_macd(prices: List[float]) -> Dict:
    """Calculate MACD (12, 26, 9)."""
    if len(prices) < 26:
        return {'macd': 0, 'signal': 0, 'histogram': 0, 'trend': 'NEUTRAL'}
    
    # Calculate EMAs
    ema_12 = calculate_ema(prices, 12)
    ema_26 = calculate_ema(prices, 26)
    
    # MACD line
    macd_line = ema_12[-1] - ema_26[-1]
    
    # Signal line (9-day EMA of MACD)
    macd_values = [ema_12[i] - ema_26[i] for i in range(len(ema_26))]
    signal_line = calculate_ema(macd_values, 9)[-1] if len(macd_values) >= 9 else 0
    
    # Histogram
    histogram = macd_line - signal_line
    
    # Determine trend
    if histogram > 0 and macd_line > 0:
        trend = 'STRONG_BULLISH'
    elif histogram > 0:
        trend = 'BULLISH'
    elif histogram < 0 and macd_line < 0:
        trend = 'STRONG_BEARISH'
    elif histogram < 0:
        trend = 'BEARISH'
    else:
        trend = 'NEUTRAL'
    
    return {
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram,
        'trend': trend
    }

def calculate_bollinger_bands(prices: List[float], period: int = 20, std_dev: float = 2) -> Dict:
    """Calculate Bollinger Bands."""
    if len(prices) < period:
        return {'upper': prices[-1], 'middle': prices[-1], 'lower': prices[-1], 'position': 0.5}
    
    recent = prices[-period:]
    sma = statistics.mean(recent)
    std = statistics.stdev(recent)
    
    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)
    
    current_price = prices[-1]
    
    # Position within bands (0 = lower, 0.5 = middle, 1 = upper)
    band_range = upper_band - lower_band
    if band_range > 0:
        position = (current_price - lower_band) / band_range
    else:
        position = 0.5
    
    return {
        'upper': upper_band,
        'middle': sma,
        'lower': lower_band,
        'position': position,
        'width': band_range / sma if sma > 0 else 0
    }

def find_support_resistance(candles: List[Dict], lookback: int = 100) -> Dict:
    """Find key support and resistance levels."""
    if len(candles) < 10:
        return {'support': [], 'resistance': [], 'current_zone': 'NEUTRAL'}
    
    recent = candles[-min(lookback, len(candles)):]
    current_price = candles[-1]['close']
    
    # Find local highs and lows
    highs = []
    lows = []
    
    for i in range(2, len(recent) - 2):
        # Local high
        if (recent[i]['high'] > recent[i-1]['high'] and 
            recent[i]['high'] > recent[i-2]['high'] and
            recent[i]['high'] > recent[i+1]['high'] and
            recent[i]['high'] > recent[i+2]['high']):
            highs.append(recent[i]['high'])
        
        # Local low
        if (recent[i]['low'] < recent[i-1]['low'] and 
            recent[i]['low'] < recent[i-2]['low'] and
            recent[i]['low'] < recent[i+1]['low'] and
            recent[i]['low'] < recent[i+2]['low']):
            lows.append(recent[i]['low'])
    
    # Cluster levels (within 0.1% are considered same level)
    def cluster_levels(levels):
        if not levels:
            return []
        
        clustered = []
        levels_sorted = sorted(levels)
        
        current_cluster = [levels_sorted[0]]
        
        for level in levels_sorted[1:]:
            if (level - current_cluster[-1]) / current_cluster[-1] < 0.001:  # Within 0.1%
                current_cluster.append(level)
            else:
                clustered.append(statistics.mean(current_cluster))
                current_cluster = [level]
        
        clustered.append(statistics.mean(current_cluster))
        return clustered
    
    resistance_levels = cluster_levels(highs)
    support_levels = cluster_levels(lows)
    
    # Find nearest levels
    nearest_resistance = min([r for r in resistance_levels if r > current_price], default=current_price * 1.01)
    nearest_support = max([s for s in support_levels if s < current_price], default=current_price * 0.99)
    
    # Determine current zone
    resistance_distance = (nearest_resistance - current_price) / current_price
    support_distance = (current_price - nearest_support) / current_price
    
    if resistance_distance < 0.001:
        zone = 'AT_RESISTANCE'
    elif support_distance < 0.001:
        zone = 'AT_SUPPORT'
    elif resistance_distance < support_distance:
        zone = 'NEAR_RESISTANCE'
    elif support_distance < resistance_distance:
        zone = 'NEAR_SUPPORT'
    else:
        zone = 'NEUTRAL'
    
    return {
        'support': support_levels[-3:] if len(support_levels) >= 3 else support_levels,
        'resistance': resistance_levels[:3] if len(resistance_levels) >= 3 else resistance_levels,
        'nearest_support': nearest_support,
        'nearest_resistance': nearest_resistance,
        'current_zone': zone
    }

def calculate_volume_profile(candles: List[Dict], bins: int = 20) -> Dict:
    """Analyze volume distribution by price level."""
    if len(candles) < 50:
        return {'poc': candles[-1]['close'], 'high_volume_zone': False}
    
    # Note: We don't have volume data from Binance klines in current implementation
    # Using range as proxy for volume (larger range = more activity)
    
    recent = candles[-100:]
    
    # Create price bins
    all_prices = []
    for c in recent:
        all_prices.extend([c['open'], c['high'], c['low'], c['close']])
    
    min_price = min(all_prices)
    max_price = max(all_prices)
    bin_size = (max_price - min_price) / bins
    
    # Count candles in each bin (weighted by range)
    bin_volumes = [0] * bins
    
    for c in recent:
        candle_range = c['high'] - c['low']
        mid_price = (c['high'] + c['low']) / 2
        
        bin_idx = int((mid_price - min_price) / bin_size) if bin_size > 0 else 0
        bin_idx = min(bin_idx, bins - 1)
        
        bin_volumes[bin_idx] += candle_range
    
    # Find Point of Control (highest volume bin)
    poc_bin = bin_volumes.index(max(bin_volumes))
    poc_price = min_price + (poc_bin + 0.5) * bin_size
    
    current_price = candles[-1]['close']
    current_bin = int((current_price - min_price) / bin_size) if bin_size > 0 else 0
    current_bin = min(current_bin, bins - 1)
    
    # Check if current price is in high-volume zone
    avg_volume = statistics.mean(bin_volumes)
    high_volume_zone = bin_volumes[current_bin] > avg_volume * 1.5
    
    return {
        'poc': poc_price,
        'high_volume_zone': high_volume_zone,
        'distance_from_poc': (current_price - poc_price) / current_price
    }

def find_similar_patterns(candles: List[Dict], window: int = 10) -> Dict:
    """Find historical patterns similar to current situation."""
    if len(candles) < window * 3:
        return {'similar_found': False, 'next_direction': 'NEUTRAL', 'confidence': 0}
    
    # Get current pattern (last 'window' candles)
    current_pattern = candles[-window:]
    
    # Normalize current pattern
    current_changes = []
    for i in range(1, len(current_pattern)):
        change = (current_pattern[i]['close'] - current_pattern[i-1]['close']) / current_pattern[i-1]['close']
        current_changes.append(change)
    
    # Search historical data for similar patterns
    best_correlation = -1
    best_match_idx = -1
    
    for i in range(len(candles) - window - 10):
        historical_pattern = candles[i:i+window]
        
        # Normalize historical pattern
        hist_changes = []
        for j in range(1, len(historical_pattern)):
            change = (historical_pattern[j]['close'] - historical_pattern[j-1]['close']) / historical_pattern[j-1]['close']
            hist_changes.append(change)
        
        # Calculate correlation
        if len(hist_changes) != len(current_changes):
            continue
        
        # Simple correlation (dot product of normalized vectors)
        correlation = sum(a * b for a, b in zip(current_changes, hist_changes))
        
        if correlation > best_correlation:
            best_correlation = correlation
            best_match_idx = i
    
    # If we found a good match, look at what happened next
    if best_match_idx >= 0 and best_correlation > 0.5:
        next_candle = candles[best_match_idx + window]
        prev_candle = candles[best_match_idx + window - 1]
        
        next_change = (next_candle['close'] - prev_candle['close']) / prev_candle['close']
        
        if next_change > 0.0005:  # > 0.05%
            direction = 'UP'
        elif next_change < -0.0005:
            direction = 'DOWN'
        else:
            direction = 'NEUTRAL'
        
        confidence = min(95, best_correlation * 100)
        
        return {
            'similar_found': True,
            'next_direction': direction,
            'confidence': confidence,
            'correlation': best_correlation
        }
    
    return {'similar_found': False, 'next_direction': 'NEUTRAL', 'confidence': 0}

# ════════════════════════════════════════════════════════════════════
# ENSEMBLE PREDICTION
# ════════════════════════════════════════════════════════════════════

def predict_advanced(candles: List[Dict]) -> Dict:
    """
    Advanced ensemble prediction using multiple indicators.
    
    Combines:
    - RSI (momentum)
    - MACD (trend)
    - Bollinger Bands (volatility + mean reversion)
    - Support/Resistance (price action)
    - Volume Profile (institutional levels)
    - Pattern Matching (historical similarity)
    - EMA crossovers (trend confirmation)
    """
    
    if len(candles) < 100:
        return {
            'direction': 'NEUTRAL',
            'confidence': 20,
            'expected_body_range': [20, 60],
            'expected_volatility': 0.1,
            'expected_close_range': [0, 0],
            'reasoning': ['Insufficient data for advanced analysis'],
            'indicators': {}
        }
    
    # Extract price series
    closes = [c['close'] for c in candles]
    current_price = closes[-1]
    
    # ═══ CALCULATE ALL INDICATORS ═══
    
    # 1. RSI
    from predictor import calculate_rsi
    rsi = calculate_rsi(candles, 14)
    
    # 2. MACD
    macd = calculate_macd(closes)
    
    # 3. Bollinger Bands
    bb = calculate_bollinger_bands(closes, 20, 2)
    
    # 4. Support/Resistance
    sr = find_support_resistance(candles, 100)
    
    # 5. Volume Profile
    vp = calculate_volume_profile(candles)
    
    # 6. Pattern Matching
    pm = find_similar_patterns(candles, 10)
    
    # 7. EMA Analysis
    ema_9 = calculate_ema(closes, 9)[-1]
    ema_21 = calculate_ema(closes, 21)[-1]
    ema_50 = calculate_ema(closes, 50)[-1]
    
    # ═══ VOTING SYSTEM ═══
    
    votes = []  # List of (direction, confidence) tuples
    reasoning = []
    
    # Vote 1: RSI
    if rsi < 30:
        votes.append(('UP', 75))
        reasoning.append(f'RSI oversold ({rsi:.1f}) → reversal UP')
    elif rsi > 70:
        votes.append(('DOWN', 75))
        reasoning.append(f'RSI overbought ({rsi:.1f}) → reversal DOWN')
    else:
        votes.append(('NEUTRAL', 40))
        reasoning.append(f'RSI neutral ({rsi:.1f})')
    
    # Vote 2: MACD
    if macd['trend'] == 'STRONG_BULLISH':
        votes.append(('UP', 85))
        reasoning.append(f"MACD strong bullish ({macd['histogram']:.2f})")
    elif macd['trend'] == 'BULLISH':
        votes.append(('UP', 65))
        reasoning.append(f"MACD bullish")
    elif macd['trend'] == 'STRONG_BEARISH':
        votes.append(('DOWN', 85))
        reasoning.append(f"MACD strong bearish ({macd['histogram']:.2f})")
    elif macd['trend'] == 'BEARISH':
        votes.append(('DOWN', 65))
        reasoning.append(f"MACD bearish")
    else:
        votes.append(('NEUTRAL', 40))
    
    # Vote 3: Bollinger Bands (mean reversion)
    if bb['position'] > 0.9:
        votes.append(('DOWN', 70))
        reasoning.append(f"Price at upper BB ({bb['position']*100:.0f}%) → mean reversion DOWN")
    elif bb['position'] < 0.1:
        votes.append(('UP', 70))
        reasoning.append(f"Price at lower BB ({bb['position']*100:.0f}%) → mean reversion UP")
    elif bb['width'] < 0.01:
        votes.append(('NEUTRAL', 60))
        reasoning.append(f"BB squeeze → breakout pending")
    else:
        votes.append(('NEUTRAL', 45))
    
    # Vote 4: Support/Resistance
    if sr['current_zone'] == 'AT_RESISTANCE':
        votes.append(('DOWN', 80))
        reasoning.append(f"At resistance ${sr['nearest_resistance']:.0f} → rejection likely")
    elif sr['current_zone'] == 'AT_SUPPORT':
        votes.append(('UP', 80))
        reasoning.append(f"At support ${sr['nearest_support']:.0f} → bounce likely")
    elif sr['current_zone'] == 'NEAR_RESISTANCE':
        votes.append(('DOWN', 60))
        reasoning.append(f"Near resistance → resistance ahead")
    elif sr['current_zone'] == 'NEAR_SUPPORT':
        votes.append(('UP', 60))
        reasoning.append(f"Near support → support ahead")
    else:
        votes.append(('NEUTRAL', 45))
    
    # Vote 5: Volume Profile
    if vp['high_volume_zone']:
        votes.append(('NEUTRAL', 50))
        reasoning.append(f"High volume zone → consolidation likely")
    else:
        poc_distance = vp['distance_from_poc']
        if poc_distance > 0.003:
            votes.append(('DOWN', 60))
            reasoning.append(f"Above POC → pull back to ${vp['poc']:.0f}")
        elif poc_distance < -0.003:
            votes.append(('UP', 60))
            reasoning.append(f"Below POC → move up to ${vp['poc']:.0f}")
        else:
            votes.append(('NEUTRAL', 45))
    
    # Vote 6: Pattern Matching
    if pm['similar_found']:
        if pm['next_direction'] == 'UP':
            votes.append(('UP', pm['confidence']))
            reasoning.append(f"Historical pattern match → {pm['next_direction']} ({pm['confidence']:.0f}%)")
        elif pm['next_direction'] == 'DOWN':
            votes.append(('DOWN', pm['confidence']))
            reasoning.append(f"Historical pattern match → {pm['next_direction']} ({pm['confidence']:.0f}%)")
        else:
            votes.append(('NEUTRAL', pm['confidence']))
    else:
        votes.append(('NEUTRAL', 35))
    
    # Vote 7: EMA Crossovers
    if ema_9 > ema_21 > ema_50:
        votes.append(('UP', 75))
        reasoning.append(f"Bullish EMA alignment (9>21>50)")
    elif ema_9 < ema_21 < ema_50:
        votes.append(('DOWN', 75))
        reasoning.append(f"Bearish EMA alignment (9<21<50)")
    elif current_price > ema_9:
        votes.append(('UP', 55))
        reasoning.append(f"Price above EMA9")
    elif current_price < ema_9:
        votes.append(('DOWN', 55))
        reasoning.append(f"Price below EMA9")
    else:
        votes.append(('NEUTRAL', 40))
    
    # ═══ AGGREGATE VOTES ═══
    
    up_score = sum(conf for dir, conf in votes if dir == 'UP')
    down_score = sum(conf for dir, conf in votes if dir == 'DOWN')
    neutral_score = sum(conf for dir, conf in votes if dir == 'NEUTRAL')
    
    # FORCE BINARY CHOICE: Distribute neutral votes to UP/DOWN based on which is stronger
    # Candles are ALWAYS green or red, never neutral!
    if neutral_score > 0:
        if up_score >= down_score:
            up_score += neutral_score
        else:
            down_score += neutral_score
    
    total_score = up_score + down_score
    
    # Weighted direction (ALWAYS UP or DOWN, never NEUTRAL)
    if up_score > down_score:
        direction = 'UP'
        confidence = min(95, (up_score / total_score) * 100) if total_score > 0 else 50
    else:
        direction = 'DOWN'
        confidence = min(95, (down_score / total_score) * 100) if total_score > 0 else 50
    
    # Boost confidence if multiple strong signals agree
    up_votes = sum(1 for dir, conf in votes if dir == 'UP' and conf > 70)
    down_votes = sum(1 for dir, conf in votes if dir == 'DOWN' and conf > 70)
    
    if direction == 'UP' and up_votes >= 3:
        confidence = min(95, confidence + 10)
        reasoning.append(f"✓ {up_votes} strong bullish signals converge")
    elif direction == 'DOWN' and down_votes >= 3:
        confidence = min(95, confidence + 10)
        reasoning.append(f"✓ {down_votes} strong bearish signals converge")
    
    # Calculate expected ranges
    avg_body = statistics.mean([abs(c['close'] - c['open']) for c in candles[-20:]])
    avg_range = statistics.mean([c['high'] - c['low'] for c in candles[-20:]])
    
    expected_body_min = avg_body * 0.7
    expected_body_max = avg_body * 1.3
    
    if direction == 'UP':
        expected_close_min = current_price + expected_body_min * 0.5
        expected_close_max = current_price + expected_body_max
    else:  # direction == 'DOWN'
        expected_close_min = current_price - expected_body_max
        expected_close_max = current_price - expected_body_min * 0.5
    
    expected_volatility = (avg_range / current_price) * 100
    
    return {
        'direction': direction,
        'confidence': round(confidence, 1),
        'expected_body_range': [round(expected_body_min, 2), round(expected_body_max, 2)],
        'expected_volatility': round(expected_volatility, 4),
        'expected_close_range': [round(expected_close_min, 2), round(expected_close_max, 2)],
        'reasoning': reasoning[:5],  # Top 5 reasons
        'indicators': {
            'rsi': round(rsi, 1),
            'macd': macd,
            'bollinger': bb,
            'support_resistance': sr,
            'volume_profile': vp,
            'pattern_match': pm,
            'ema_9': round(ema_9, 2),
            'ema_21': round(ema_21, 2),
            'ema_50': round(ema_50, 2),
            'votes': {
                'up_score': round(up_score, 1),
                'down_score': round(down_score, 1),
                'neutral_score': round(neutral_score, 1),
                'up_votes': up_votes,
                'down_votes': down_votes
            }
        }
    }
