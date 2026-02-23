#!/usr/bin/env python3
"""
Candle Prediction System
Analyzes historical patterns to predict next candle characteristics
"""

import statistics
from typing import List, Dict, Optional

def calculate_rsi(candles: List[Dict], period: int = 14) -> float:
    """Calculate Relative Strength Index (optimized for large datasets)."""
    if len(candles) < period + 1:
        return 50.0
    
    # Use only recent candles for efficiency (last 500 is more than enough)
    recent = candles[-min(500, len(candles)):]
    
    gains = []
    losses = []
    
    for i in range(1, len(recent)):
        change = recent[i]['close'] - recent[i-1]['close']
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    avg_gain = statistics.mean(gains[-period:])
    avg_loss = statistics.mean(losses[-period:])
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

def detect_pattern(candles: List[Dict]) -> Dict:
    """Detect candlestick patterns in recent candles."""
    if len(candles) < 3:
        return {'pattern': 'UNKNOWN', 'signal': 'NEUTRAL'}
    
    c0 = candles[-1]  # Most recent
    c1 = candles[-2]  # Previous
    c2 = candles[-3]  # Two candles ago
    
    # Calculate bodies and ranges
    body0 = abs(c0['close'] - c0['open'])
    body1 = abs(c1['close'] - c1['open'])
    range0 = c0['high'] - c0['low']
    range1 = c1['high'] - c1['low']
    
    is_green0 = c0['close'] >= c0['open']
    is_green1 = c1['close'] >= c1['open']
    
    # Doji pattern (small body, indecision)
    if range0 > 0 and (body0 / range0) < 0.1:
        return {'pattern': 'DOJI', 'signal': 'NEUTRAL', 'confidence': 60}
    
    # Hammer (bullish reversal)
    lower_wick0 = (min(c0['open'], c0['close']) - c0['low'])
    if not is_green1 and range0 > 0 and lower_wick0 / range0 > 0.6 and body0 / range0 < 0.3:
        return {'pattern': 'HAMMER', 'signal': 'BULLISH', 'confidence': 70}
    
    # Shooting star (bearish reversal)
    upper_wick0 = (c0['high'] - max(c0['open'], c0['close']))
    if is_green1 and range0 > 0 and upper_wick0 / range0 > 0.6 and body0 / range0 < 0.3:
        return {'pattern': 'SHOOTING_STAR', 'signal': 'BEARISH', 'confidence': 70}
    
    # Engulfing patterns
    if is_green0 and not is_green1 and c0['open'] <= c1['close'] and c0['close'] >= c1['open']:
        return {'pattern': 'BULLISH_ENGULFING', 'signal': 'BULLISH', 'confidence': 75}
    
    if not is_green0 and is_green1 and c0['open'] >= c1['close'] and c0['close'] <= c1['open']:
        return {'pattern': 'BEARISH_ENGULFING', 'signal': 'BEARISH', 'confidence': 75}
    
    # Three white soldiers (strong bullish)
    if is_green0 and is_green1 and (c2['close'] >= c2['open']):
        if c0['close'] > c1['close'] > c2['close']:
            return {'pattern': 'THREE_SOLDIERS', 'signal': 'BULLISH', 'confidence': 80}
    
    # Three black crows (strong bearish)
    if not is_green0 and not is_green1 and (c2['close'] < c2['open']):
        if c0['close'] < c1['close'] < c2['close']:
            return {'pattern': 'THREE_CROWS', 'signal': 'BEARISH', 'confidence': 80}
    
    return {'pattern': 'NONE', 'signal': 'NEUTRAL', 'confidence': 50}

def calculate_momentum(candles: List[Dict], short_period: int = 5, long_period: int = 50) -> Dict:
    """Calculate price momentum and trend strength using multiple timeframes."""
    if len(candles) < short_period:
        return {'direction': 'NEUTRAL', 'strength': 0, 'pct_change': 0, 'green_ratio': 0.5}
    
    # Short-term momentum (last 5 candles)
    recent_short = candles[-short_period:]
    green_short = sum(1 for c in recent_short if c['close'] >= c['open'])
    red_short = short_period - green_short
    
    # Long-term momentum (last 50 candles if available)
    if len(candles) >= long_period:
        recent_long = candles[-long_period:]
        green_long = sum(1 for c in recent_long if c['close'] >= c['open'])
        long_trend = 'BULLISH' if green_long > long_period * 0.55 else 'BEARISH' if green_long < long_period * 0.45 else 'NEUTRAL'
    else:
        long_trend = 'NEUTRAL'
    
    # Calculate price change
    price_change = recent_short[-1]['close'] - recent_short[0]['open']
    pct_change = (price_change / recent_short[0]['open']) * 100
    
    # Determine direction and strength (weight short-term more, but consider long-term)
    short_score = 0
    if green_short > red_short * 1.5:
        short_score = 2
    elif red_short > green_short * 1.5:
        short_score = -2
    
    long_score = 0
    if long_trend == 'BULLISH':
        long_score = 1
    elif long_trend == 'BEARISH':
        long_score = -1
    
    total_score = short_score + long_score
    
    if total_score > 1.5:
        direction = 'BULLISH'
        strength = min(100, (green_short / short_period) * 100 + abs(pct_change) * 10)
    elif total_score < -1.5:
        direction = 'BEARISH'
        strength = min(100, (red_short / short_period) * 100 + abs(pct_change) * 10)
    else:
        direction = 'NEUTRAL'
        strength = 40
    
    return {
        'direction': direction,
        'strength': strength,
        'pct_change': pct_change,
        'green_ratio': green_short / short_period
    }

def calculate_volatility_trend(candles: List[Dict], period: int = 10) -> Dict:
    """Analyze if volatility is increasing or decreasing."""
    if len(candles) < period:
        return {'trend': 'STABLE', 'current': 0, 'avg': 0}
    
    recent = candles[-period:]
    
    # Calculate range % for each candle
    volatilities = []
    for c in recent:
        vol = ((c['high'] - c['low']) / c['open']) * 100
        volatilities.append(vol)
    
    current_vol = volatilities[-1]
    avg_vol = statistics.mean(volatilities)
    
    # Check trend (compare recent 3 vs previous 7)
    recent_avg = statistics.mean(volatilities[-3:])
    older_avg = statistics.mean(volatilities[:7]) if len(volatilities) >= 7 else avg_vol
    
    if recent_avg > older_avg * 1.2:
        trend = 'INCREASING'
    elif recent_avg < older_avg * 0.8:
        trend = 'DECREASING'
    else:
        trend = 'STABLE'
    
    return {
        'trend': trend,
        'current': current_vol,
        'avg': avg_vol,
        'recent_avg': recent_avg
    }

def predict_next_candle(candles: List[Dict]) -> Dict:
    """
    Main prediction function - analyzes patterns and predicts next candle.
    
    Supports large datasets (up to 5000 candles = ~17 days of 5-min data).
    Uses multi-timeframe analysis for more accurate predictions.
    
    Returns:
        - direction: 'UP', 'DOWN', 'NEUTRAL'
        - confidence: 0-100
        - expected_body_range: [min, max] in USD
        - expected_volatility: expected range %
        - reasoning: list of factors
    """
    if len(candles) < 10:
        return {
            'direction': 'NEUTRAL',
            'confidence': 30,
            'expected_body_range': [20, 60],
            'expected_volatility': 0.1,
            'expected_close_range': [0, 0],
            'reasoning': ['Insufficient data'],
            'indicators': {
                'rsi': 50,
                'pattern': {'pattern': 'NONE', 'signal': 'NEUTRAL', 'confidence': 50},
                'momentum': {'direction': 'NEUTRAL', 'strength': 0, 'pct_change': 0, 'green_ratio': 0.5},
                'volatility': {'trend': 'STABLE', 'current': 0, 'avg': 0, 'recent_avg': 0},
                'direction_score': 0
            }
        }
    
    # Get current price
    current_price = candles[-1]['close']
    
    # Analyze components
    rsi = calculate_rsi(candles, 14)
    pattern = detect_pattern(candles)
    momentum = calculate_momentum(candles, 5)
    volatility = calculate_volatility_trend(candles, 10)
    
    # Calculate average body size for prediction
    recent_bodies = []
    for c in candles[-10:]:
        body = abs(c['close'] - c['open'])
        recent_bodies.append(body)
    avg_body = statistics.mean(recent_bodies)
    
    # Build prediction
    reasoning = []
    confidence_factors = []
    direction_score = 0  # Positive = bullish, negative = bearish
    
    # Add dataset size context
    reasoning.append(f'Analyzed {len(candles)} candles ({len(candles) * 5 // 60:.1f}h data)')
    
    # 1. RSI Analysis
    if rsi > 70:
        direction_score -= 2
        reasoning.append(f'RSI overbought ({rsi:.1f})')
        confidence_factors.append(60)
    elif rsi < 30:
        direction_score += 2
        reasoning.append(f'RSI oversold ({rsi:.1f})')
        confidence_factors.append(60)
    else:
        reasoning.append(f'RSI neutral ({rsi:.1f})')
        confidence_factors.append(40)
    
    # 2. Pattern Analysis
    if pattern['signal'] == 'BULLISH':
        direction_score += 2
        reasoning.append(f"{pattern['pattern']} pattern (bullish)")
        confidence_factors.append(pattern['confidence'])
    elif pattern['signal'] == 'BEARISH':
        direction_score -= 2
        reasoning.append(f"{pattern['pattern']} pattern (bearish)")
        confidence_factors.append(pattern['confidence'])
    else:
        reasoning.append('No clear pattern')
        confidence_factors.append(30)
    
    # 3. Momentum Analysis
    if momentum['direction'] == 'BULLISH':
        direction_score += 1.5
        reasoning.append(f"Bullish momentum ({momentum['strength']:.0f}%)")
        confidence_factors.append(momentum['strength'])
    elif momentum['direction'] == 'BEARISH':
        direction_score -= 1.5
        reasoning.append(f"Bearish momentum ({momentum['strength']:.0f}%)")
        confidence_factors.append(momentum['strength'])
    else:
        reasoning.append('Neutral momentum')
        confidence_factors.append(35)
    
    # 4. Volatility Analysis
    if volatility['trend'] == 'INCREASING':
        reasoning.append(f"Volatility increasing ({volatility['current']:.3f}%)")
        expected_vol = volatility['current'] * 1.1
        confidence_factors.append(50)
    elif volatility['trend'] == 'DECREASING':
        reasoning.append(f"Volatility decreasing ({volatility['current']:.3f}%)")
        expected_vol = volatility['current'] * 0.9
        confidence_factors.append(55)
    else:
        reasoning.append(f"Volatility stable ({volatility['current']:.3f}%)")
        expected_vol = volatility['current']
        confidence_factors.append(45)
    
    # Determine final direction
    if direction_score > 1.5:
        direction = 'UP'
    elif direction_score < -1.5:
        direction = 'DOWN'
    else:
        direction = 'NEUTRAL'
    
    # Calculate confidence (average of all factors, weighted by strength)
    base_confidence = statistics.mean(confidence_factors) if confidence_factors else 50
    
    # Boost confidence if multiple signals agree
    if abs(direction_score) > 3:
        base_confidence = min(95, base_confidence + 15)
    elif abs(direction_score) > 2:
        base_confidence = min(90, base_confidence + 10)
    
    # Calculate expected body range
    expected_body_min = avg_body * 0.7
    expected_body_max = avg_body * 1.3
    
    return {
        'direction': direction,
        'confidence': round(base_confidence, 1),
        'expected_body_range': [round(expected_body_min, 2), round(expected_body_max, 2)],
        'expected_volatility': round(expected_vol, 4),
        'expected_close_range': [
            round(current_price - (expected_body_max if direction == 'DOWN' else expected_body_min), 2),
            round(current_price + (expected_body_max if direction == 'UP' else expected_body_min), 2)
        ],
        'reasoning': reasoning,
        'indicators': {
            'rsi': round(rsi, 1),
            'pattern': pattern,
            'momentum': momentum,
            'volatility': volatility,
            'direction_score': round(direction_score, 2)
        }
    }
