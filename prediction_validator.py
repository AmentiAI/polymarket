#!/usr/bin/env python3
"""
Prediction Validator
Tracks prediction accuracy against actual outcomes and calibrates confidence
"""

import json
import statistics
from typing import List, Dict
from pathlib import Path

VALIDATION_LOG_PATH = Path("prediction_validation.json")

def load_validation_log():
    """Load historical predictions and outcomes."""
    if not VALIDATION_LOG_PATH.exists():
        return []
    
    try:
        with open(VALIDATION_LOG_PATH, 'r') as f:
            return json.load(f)
    except:
        return []

def save_validation_entry(prediction: Dict, actual_candle: Dict):
    """Save a prediction and its actual outcome."""
    log = load_validation_log()
    
    # Calculate actual direction
    actual_direction = 'UP' if actual_candle['close'] > actual_candle['open'] else 'DOWN' if actual_candle['close'] < actual_candle['open'] else 'NEUTRAL'
    
    # Calculate actual body
    actual_body = abs(actual_candle['close'] - actual_candle['open'])
    
    # Check if prediction was correct
    direction_correct = prediction['direction'] == actual_direction
    
    # Check if close was in predicted range
    predicted_range = prediction['expected_close_range']
    close_in_range = predicted_range[0] <= actual_candle['close'] <= predicted_range[1]
    
    entry = {
        'timestamp': actual_candle['time'],
        'predicted_direction': prediction['direction'],
        'predicted_confidence': prediction['confidence'],
        'predicted_close_range': predicted_range,
        'predicted_body_range': prediction['expected_body_range'],
        'actual_direction': actual_direction,
        'actual_close': actual_candle['close'],
        'actual_body': actual_body,
        'direction_correct': direction_correct,
        'close_in_range': close_in_range,
    }
    
    log.append(entry)
    
    # Keep only last 1000 entries
    if len(log) > 1000:
        log = log[-1000:]
    
    with open(VALIDATION_LOG_PATH, 'w') as f:
        json.dump(log, f, indent=2)
    
    return entry

def calculate_accuracy_metrics():
    """Calculate prediction accuracy from historical log."""
    log = load_validation_log()
    
    if len(log) < 10:
        return {
            'total_predictions': len(log),
            'directional_accuracy': 0,
            'range_accuracy': 0,
            'insufficient_data': True
        }
    
    # Overall metrics
    total = len(log)
    direction_correct = sum(1 for e in log if e['direction_correct'])
    range_correct = sum(1 for e in log if e['close_in_range'])
    
    # Accuracy by confidence bucket
    confidence_buckets = {
        'low': {'correct': 0, 'total': 0},      # < 50%
        'medium': {'correct': 0, 'total': 0},   # 50-70%
        'high': {'correct': 0, 'total': 0},     # 70-85%
        'very_high': {'correct': 0, 'total': 0}, # > 85%
    }
    
    for entry in log:
        conf = entry['predicted_confidence']
        correct = entry['direction_correct']
        
        if conf < 50:
            bucket = 'low'
        elif conf < 70:
            bucket = 'medium'
        elif conf < 85:
            bucket = 'high'
        else:
            bucket = 'very_high'
        
        confidence_buckets[bucket]['total'] += 1
        if correct:
            confidence_buckets[bucket]['correct'] += 1
    
    # Calculate bucket accuracy
    for bucket in confidence_buckets.values():
        if bucket['total'] > 0:
            bucket['accuracy'] = (bucket['correct'] / bucket['total']) * 100
        else:
            bucket['accuracy'] = 0
    
    # Recent performance (last 100)
    recent = log[-100:] if len(log) >= 100 else log
    recent_accuracy = (sum(1 for e in recent if e['direction_correct']) / len(recent)) * 100 if recent else 0
    
    return {
        'total_predictions': total,
        'directional_accuracy': (direction_correct / total) * 100,
        'range_accuracy': (range_correct / total) * 100,
        'recent_accuracy_100': recent_accuracy,
        'confidence_buckets': confidence_buckets,
        'insufficient_data': False
    }

def backtest_predictions(candles: List[Dict], predictor_func) -> Dict:
    """
    Backtest prediction system on historical data.
    
    Takes historical candles and tests how well predictions would have performed.
    """
    if len(candles) < 200:
        return {'error': 'Need at least 200 candles for backtesting'}
    
    results = []
    
    # Use sliding window: predict candle N+1 using candles 0..N
    for i in range(100, len(candles) - 1):
        # Data available for prediction
        historical_data = candles[:i]
        
        # Make prediction
        try:
            prediction = predictor_func(historical_data)
        except:
            continue
        
        # Actual next candle
        actual_next = candles[i + 1]
        
        # Validate
        actual_direction = 'UP' if actual_next['close'] > actual_next['open'] else 'DOWN' if actual_next['close'] < actual_next['open'] else 'NEUTRAL'
        direction_correct = prediction['direction'] == actual_direction
        
        predicted_range = prediction['expected_close_range']
        close_in_range = predicted_range[0] <= actual_next['close'] <= predicted_range[1]
        
        results.append({
            'index': i,
            'predicted_direction': prediction['direction'],
            'predicted_confidence': prediction['confidence'],
            'actual_direction': actual_direction,
            'direction_correct': direction_correct,
            'close_in_range': close_in_range,
        })
    
    # Aggregate results
    if not results:
        return {'error': 'No results from backtest'}
    
    total = len(results)
    correct = sum(1 for r in results if r['direction_correct'])
    in_range = sum(1 for r in results if r['close_in_range'])
    
    # Accuracy by confidence level
    high_conf = [r for r in results if r['predicted_confidence'] >= 70]
    high_conf_correct = sum(1 for r in high_conf if r['direction_correct']) if high_conf else 0
    
    return {
        'total_tests': total,
        'directional_accuracy': (correct / total) * 100,
        'range_accuracy': (in_range / total) * 100,
        'high_confidence_count': len(high_conf),
        'high_confidence_accuracy': (high_conf_correct / len(high_conf) * 100) if high_conf else 0,
        'sample_results': results[-10:],  # Last 10 for inspection
    }

def calibrate_confidence(raw_confidence: float, metrics: Dict) -> float:
    """
    Calibrate confidence based on actual historical accuracy.
    
    If the system says 70% but is only right 55% of the time, adjust down.
    """
    if metrics.get('insufficient_data'):
        return raw_confidence
    
    # Get actual accuracy for this confidence bucket
    if raw_confidence < 50:
        bucket = metrics['confidence_buckets']['low']
    elif raw_confidence < 70:
        bucket = metrics['confidence_buckets']['medium']
    elif raw_confidence < 85:
        bucket = metrics['confidence_buckets']['high']
    else:
        bucket = metrics['confidence_buckets']['very_high']
    
    # If we have enough data in this bucket
    if bucket['total'] >= 20:
        actual_accuracy = bucket['accuracy']
        
        # Calibrate: blend raw confidence with actual accuracy
        # Weight recent performance more heavily
        calibrated = (raw_confidence * 0.3) + (actual_accuracy * 0.7)
        
        return round(calibrated, 1)
    
    # Not enough data, use overall accuracy
    if metrics['total_predictions'] >= 50:
        overall_accuracy = metrics['directional_accuracy']
        calibrated = (raw_confidence * 0.5) + (overall_accuracy * 0.5)
        return round(calibrated, 1)
    
    # Not enough data at all, return raw
    return raw_confidence

def add_validation_stats_to_prediction(prediction: Dict) -> Dict:
    """Add validation metrics to prediction output."""
    metrics = calculate_accuracy_metrics()
    
    # Calibrate confidence based on real performance
    if not metrics.get('insufficient_data'):
        original_confidence = prediction['confidence']
        calibrated_confidence = calibrate_confidence(original_confidence, metrics)
        
        prediction['confidence_raw'] = original_confidence
        prediction['confidence'] = calibrated_confidence
        prediction['confidence_calibrated'] = True
    else:
        prediction['confidence_calibrated'] = False
    
    # Add accuracy context
    prediction['validation_metrics'] = {
        'total_predictions': metrics['total_predictions'],
        'overall_accuracy': round(metrics.get('directional_accuracy', 0), 1),
        'recent_accuracy': round(metrics.get('recent_accuracy_100', 0), 1),
        'has_enough_data': not metrics.get('insufficient_data', True),
    }
    
    return prediction

def get_accuracy_summary() -> str:
    """Get human-readable accuracy summary."""
    metrics = calculate_accuracy_metrics()
    
    if metrics.get('insufficient_data'):
        return "⏳ Collecting prediction data... (need 10+ predictions)"
    
    total = metrics['total_predictions']
    acc = metrics['directional_accuracy']
    recent = metrics['recent_accuracy_100']
    
    # Color code based on performance
    if acc >= 70:
        emoji = "🟢"
    elif acc >= 55:
        emoji = "🟡"
    else:
        emoji = "🔴"
    
    summary = f"{emoji} Accuracy: {acc:.1f}% ({total} predictions)"
    
    if total >= 100:
        summary += f" | Recent: {recent:.1f}%"
    
    return summary
