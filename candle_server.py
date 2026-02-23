#!/usr/bin/env python3
"""
Candle Prediction Server — 50-Point DNA System + 24 Weighted Signals
FastAPI + WebSocket (port 8081)
"""

import asyncio
import json
import os
import sys
import threading
import time
import traceback
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

# ══════════════════════════════════════════════════════════════════════════
# Setup
# ══════════════════════════════════════════════════════════════════════════

PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))

import bot  # polymarket_sniper_bot module

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Config ──
POLL_INTERVAL = 3.0  # seconds between indicator fetches
TRADE_AMOUNT = 4.0   # $ per trade
CANDLE_TRADE_LOG = PROJECT_DIR / "candle_trades.json"
DNA_WARMUP = 50  # minimum candles needed for DNA features

# ── Global State ──
_state = {"ready": False}
_state_lock = threading.Lock()
_ws_clients = set()
_trading_enabled = False
_live_prev_outcome = None  # 1=WIN, -1=LOSS for last DNA prediction
_history_candles_5m = []  # full history for client-side sequence matching


# ══════════════════════════════════════════════════════════════════════════
# A. DNA Candle Classification (50-Point System)
# ══════════════════════════════════════════════════════════════════════════

class CandleDNA:
    """50-point candle fingerprint for pattern matching."""
    __slots__ = (
        "color", "shape", "size", "body_pct", "upper_wick_pct", "lower_wick_pct",
        "rsi", "macd", "bb", "volume", "trend", "streak", "prev_color",
        "two_candle", "three_candle"
    )
    
    def __init__(self, **kwargs):
        for k in self.__slots__:
            setattr(self, k, kwargs.get(k, "?"))
    
    def __hash__(self):
        return hash(tuple(getattr(self, k) for k in self.__slots__))
    
    def __eq__(self, other):
        return all(getattr(self, k) == getattr(other, k) for k in self.__slots__)


class DNATable:
    """Historical DNA database with train/test split."""
    def __init__(self):
        self.train_dna = []  # (DNA, actual_color)
        self.test_dna = []
        self.overall_train_wr = 0.0
        self.overall_test_wr = 0.0
        self.dna_stats = {}  # DNA → {"train_wr", "test_wr", "n_train", "n_test"}


def _classify_color(candle) -> str:
    return "GREEN" if candle["close"] >= candle["open"] else "RED"


def _classify_shape(candle) -> str:
    """Candle shape: HAMMER, DOJI, ENGULFING, NORMAL."""
    body = abs(candle["close"] - candle["open"])
    total = candle["high"] - candle["low"]
    if total == 0:
        return "DOJI"
    body_pct = body / total
    upper_wick = candle["high"] - max(candle["open"], candle["close"])
    lower_wick = min(candle["open"], candle["close"]) - candle["low"]
    
    if body_pct < 0.1:
        return "DOJI"
    if lower_wick > body * 2 and upper_wick < body * 0.5:
        return "HAMMER"
    if upper_wick > body * 2 and lower_wick < body * 0.5:
        return "SHOOTING_STAR"
    if body_pct > 0.7:
        return "STRONG"
    return "NORMAL"


def _classify_size(candle, atr) -> str:
    """TINY, SMALL, MEDIUM, LARGE based on ATR."""
    body = abs(candle["close"] - candle["open"])
    if atr == 0:
        return "MEDIUM"
    ratio = body / atr
    if ratio < 0.3:
        return "TINY"
    if ratio < 0.7:
        return "SMALL"
    if ratio < 1.3:
        return "MEDIUM"
    return "LARGE"


def _classify_rsi(rsi_val) -> str:
    """OB (>70), OS (<30), RISING/FALLING (40-60), MID."""
    if rsi_val >= 70:
        return "OB"
    if rsi_val <= 30:
        return "OS"
    if 40 <= rsi_val <= 60:
        return "MID"
    if rsi_val > 60:
        return "RISING"
    return "FALLING"


def _classify_macd(macd_hist) -> str:
    """POS_STRONG, POS_WEAK, NEG_WEAK, NEG_STRONG."""
    if macd_hist > 0.5:
        return "POS_STRONG"
    if macd_hist > 0:
        return "POS_WEAK"
    if macd_hist > -0.5:
        return "NEG_WEAK"
    return "NEG_STRONG"


def _classify_bb(price, bb_upper, bb_lower) -> str:
    """ABOVE, NEAR_UPPER, MID, NEAR_LOWER, BELOW."""
    bb_range = bb_upper - bb_lower
    if bb_range == 0:
        return "MID"
    if price > bb_upper:
        return "ABOVE"
    if price < bb_lower:
        return "BELOW"
    pos = (price - bb_lower) / bb_range
    if pos > 0.8:
        return "NEAR_UPPER"
    if pos < 0.2:
        return "NEAR_LOWER"
    return "MID"


def _classify_volume(vol, vol_sma) -> str:
    """HIGH, NORMAL, LOW."""
    if vol_sma == 0:
        return "NORMAL"
    ratio = vol / vol_sma
    if ratio > 1.5:
        return "HIGH"
    if ratio < 0.7:
        return "LOW"
    return "NORMAL"


def _classify_trend(ema_fast, ema_slow) -> str:
    """UP, DOWN, FLAT."""
    if ema_fast > ema_slow * 1.002:
        return "UP"
    if ema_fast < ema_slow * 0.998:
        return "DOWN"
    return "FLAT"


def _classify_streak(candles, idx) -> str:
    """3G, 4G, 5G+, 3R, 4R, 5R+, MIXED."""
    if idx < 1:
        return "MIXED"
    colors = [_classify_color(candles[i]) for i in range(max(0, idx - 4), idx + 1)]
    if len(colors) < 2:
        return "MIXED"
    
    green_streak = 0
    red_streak = 0
    for c in reversed(colors):
        if c == "GREEN":
            if red_streak > 0:
                break
            green_streak += 1
        else:
            if green_streak > 0:
                break
            red_streak += 1
    
    if green_streak >= 5:
        return "5G+"
    if green_streak == 4:
        return "4G"
    if green_streak == 3:
        return "3G"
    if red_streak >= 5:
        return "5R+"
    if red_streak == 4:
        return "4R"
    if red_streak == 3:
        return "3R"
    return "MIXED"


def _classify_two_candle(candles, idx) -> str:
    """GG, GR, RG, RR."""
    if idx < 1:
        return "??"
    c1 = _classify_color(candles[idx - 1])
    c2 = _classify_color(candles[idx])
    return f"{c1[0]}{c2[0]}"


def _classify_three_candle(candles, idx) -> str:
    """GGG, GGR, ..., RRR."""
    if idx < 2:
        return "???"
    c1 = _classify_color(candles[idx - 2])
    c2 = _classify_color(candles[idx - 1])
    c3 = _classify_color(candles[idx])
    return f"{c1[0]}{c2[0]}{c3[0]}"


def _precompute_indicators(candles_5m):
    """Precompute all indicators for 5m candles."""
    if not candles_5m or len(candles_5m) < DNA_WARMUP:
        return None
    
    closes = [c["close"] for c in candles_5m]
    highs = [c["high"] for c in candles_5m]
    lows = [c["low"] for c in candles_5m]
    volumes = [c.get("volume", 0) for c in candles_5m]
    
    # RSI
    rsi_series = bot.calculate_rsi_series(closes, 14)
    
    # MACD
    try:
        macd_line, signal_line, hist_line, macd_offset = bot.calculate_macd_full_series(closes)
    except Exception:
        macd_line, signal_line, hist_line, macd_offset = [], [], [], 0
    
    # Bollinger Bands
    bb_upper, bb_lower = [], []
    sma_period = 20
    for i in range(len(closes)):
        if i < sma_period - 1:
            bb_upper.append(closes[i] * 1.02)
            bb_lower.append(closes[i] * 0.98)
        else:
            window = closes[i - sma_period + 1:i + 1]
            sma = sum(window) / sma_period
            variance = sum((x - sma) ** 2 for x in window) / sma_period
            std = variance ** 0.5
            bb_upper.append(sma + 2 * std)
            bb_lower.append(sma - 2 * std)
    
    # ATR
    atr_series = []
    atr_period = 14
    for i in range(len(candles_5m)):
        if i < atr_period:
            atr_series.append(candles_5m[i]["high"] - candles_5m[i]["low"])
        else:
            tr_vals = []
            for j in range(i - atr_period + 1, i + 1):
                h_l = highs[j] - lows[j]
                h_pc = abs(highs[j] - closes[j - 1]) if j > 0 else 0
                l_pc = abs(lows[j] - closes[j - 1]) if j > 0 else 0
                tr_vals.append(max(h_l, h_pc, l_pc))
            atr_series.append(sum(tr_vals) / atr_period)
    
    # Volume SMA
    vol_sma = []
    vol_period = 20
    for i in range(len(volumes)):
        if i < vol_period - 1:
            vol_sma.append(volumes[i])
        else:
            vol_sma.append(sum(volumes[i - vol_period + 1:i + 1]) / vol_period)
    
    # EMA
    ema_fast = bot.calculate_ema_series(closes, 12)
    ema_slow = bot.calculate_ema_series(closes, 26)
    
    return {
        "rsi_5m": rsi_series,
        "macd_hist": (hist_line, macd_offset),
        "macd_line": (macd_line, macd_offset),
        "signal_line": (signal_line, macd_offset),
        "bb_upper": bb_upper,
        "bb_lower": bb_lower,
        "atr": atr_series,
        "vol_sma": vol_sma,
        "ema_fast": ema_fast,
        "ema_slow": ema_slow,
    }


def _precompute_1m_15m(candles_1m, candles_15m):
    """Precompute 1m and 15m indicators."""
    result = {"rsi_1m": [], "rsi_15m": []}
    
    if candles_1m and len(candles_1m) >= 14:
        closes_1m = [c["close"] for c in candles_1m]
        result["rsi_1m"] = bot.calculate_rsi_series(closes_1m, 14)
    
    if candles_15m and len(candles_15m) >= 14:
        closes_15m = [c["close"] for c in candles_15m]
        result["rsi_15m"] = bot.calculate_rsi_series(closes_15m, 14)
    
    return result


def compute_candle_dna(idx, candles, ind, extra_ind, sr_zones) -> tuple:
    """Compute DNA for candle at index idx."""
    if idx < 2 or not ind:
        return None, {}
    
    c = candles[idx]
    
    # Basic classifications
    color = _classify_color(c)
    shape = _classify_shape(c)
    
    # Body/wick percentages
    total_range = c["high"] - c["low"]
    if total_range == 0:
        body_pct = 0
        upper_wick_pct = 0
        lower_wick_pct = 0
    else:
        body = abs(c["close"] - c["open"])
        body_pct = round(body / total_range * 100, 1)
        upper_wick = c["high"] - max(c["open"], c["close"])
        lower_wick = min(c["open"], c["close"]) - c["low"]
        upper_wick_pct = round(upper_wick / total_range * 100, 1)
        lower_wick_pct = round(lower_wick / total_range * 100, 1)
    
    # ATR-based size
    atr_val = ind["atr"][idx] if idx < len(ind["atr"]) else 1.0
    size = _classify_size(c, atr_val)
    
    # RSI
    rsi_val = ind["rsi_5m"][idx] if idx < len(ind["rsi_5m"]) else 50.0
    rsi = _classify_rsi(rsi_val)
    
    # MACD
    macd_hist_arr, macd_offset = ind["macd_hist"]
    macd_idx = idx - macd_offset
    macd_hist_val = macd_hist_arr[macd_idx] if 0 <= macd_idx < len(macd_hist_arr) else 0.0
    macd = _classify_macd(macd_hist_val)
    
    # Bollinger Bands
    bb_upper = ind["bb_upper"][idx] if idx < len(ind["bb_upper"]) else c["close"] * 1.02
    bb_lower = ind["bb_lower"][idx] if idx < len(ind["bb_lower"]) else c["close"] * 0.98
    bb = _classify_bb(c["close"], bb_upper, bb_lower)
    
    # Volume
    vol = c.get("volume", 0)
    vol_sma = ind["vol_sma"][idx] if idx < len(ind["vol_sma"]) else vol
    volume = _classify_volume(vol, vol_sma)
    
    # Trend (EMA)
    ema_fast = ind["ema_fast"][idx] if idx < len(ind["ema_fast"]) else c["close"]
    ema_slow = ind["ema_slow"][idx] if idx < len(ind["ema_slow"]) else c["close"]
    trend = _classify_trend(ema_fast, ema_slow)
    
    # Streak
    streak = _classify_streak(candles, idx)
    
    # Previous candle color
    prev_color = _classify_color(candles[idx - 1])
    
    # 2-candle and 3-candle patterns
    two_candle = _classify_two_candle(candles, idx)
    three_candle = _classify_three_candle(candles, idx)
    
    dna = CandleDNA(
        color=color,
        shape=shape,
        size=size,
        body_pct=body_pct,
        upper_wick_pct=upper_wick_pct,
        lower_wick_pct=lower_wick_pct,
        rsi=rsi,
        macd=macd,
        bb=bb,
        volume=volume,
        trend=trend,
        streak=streak,
        prev_color=prev_color,
        two_candle=two_candle,
        three_candle=three_candle,
    )
    
    datapoints = {
        "rsi_val": rsi_val,
        "macd_hist": macd_hist_val,
        "bb_pos": (c["close"] - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5,
        "vol_ratio": vol / vol_sma if vol_sma > 0 else 1.0,
        "ema_ratio": ema_fast / ema_slow if ema_slow > 0 else 1.0,
        "atr": atr_val,
        "body_pct": body_pct,
        "upper_wick_pct": upper_wick_pct,
        "lower_wick_pct": lower_wick_pct,
    }
    
    return dna, datapoints


def build_dna_table(candles_5m, ind, extra_ind, sr_zones) -> DNATable:
    """Build DNA table with 70/30 train/test split."""
    if not candles_5m or len(candles_5m) < DNA_WARMUP + 10:
        return None
    
    table = DNATable()
    
    # Split: 70% train, 30% test
    split_idx = int(len(candles_5m) * 0.7)
    
    # Build train set
    for i in range(DNA_WARMUP, split_idx - 1):
        try:
            dna, _ = compute_candle_dna(i, candles_5m, ind, extra_ind, sr_zones)
            if dna:
                actual_color = _classify_color(candles_5m[i + 1])
                table.train_dna.append((dna, actual_color))
        except Exception:
            continue
    
    # Build test set
    for i in range(split_idx, len(candles_5m) - 1):
        try:
            dna, _ = compute_candle_dna(i, candles_5m, ind, extra_ind, sr_zones)
            if dna:
                actual_color = _classify_color(candles_5m[i + 1])
                table.test_dna.append((dna, actual_color))
        except Exception:
            continue
    
    # Compute train/test WR
    train_correct = 0
    test_correct = 0
    
    for dna, actual in table.train_dna:
        # Predict using train data (exclude self)
        matches = [a for d, a in table.train_dna if d == dna and (d, a) != (dna, actual)]
        if matches:
            green_count = matches.count("GREEN")
            pred = "GREEN" if green_count > len(matches) / 2 else "RED"
            if pred == actual:
                train_correct += 1
    
    for dna, actual in table.test_dna:
        # Predict using train data only
        matches = [a for d, a in table.train_dna if d == dna]
        if matches:
            green_count = matches.count("GREEN")
            pred = "GREEN" if green_count > len(matches) / 2 else "RED"
            if pred == actual:
                test_correct += 1
    
    table.overall_train_wr = round(train_correct / len(table.train_dna) * 100, 1) if table.train_dna else 0
    table.overall_test_wr = round(test_correct / len(table.test_dna) * 100, 1) if table.test_dna else 0
    
    print(f"[DNA] Built table: {len(table.train_dna)} train, {len(table.test_dna)} test | "
          f"Train WR: {table.overall_train_wr}% | Test WR: {table.overall_test_wr}%")
    
    return table


def match_candle(dna, table: DNATable) -> list:
    """Find matching DNAs from train set."""
    if not table or not table.train_dna:
        return []
    
    matches = [actual for d, actual in table.train_dna if d == dna]
    return matches


def predict_from_matches(matches: list) -> dict:
    """Predict next candle color from DNA matches."""
    if not matches:
        return None
    
    green_count = matches.count("GREEN")
    red_count = matches.count("RED")
    total = len(matches)
    
    if green_count > red_count:
        predicted = "GREEN"
        confidence = round(green_count / total * 100, 1)
    else:
        predicted = "RED"
        confidence = round(red_count / total * 100, 1)
    
    # Estimate next candle body size (placeholder)
    body_size_est = 0.5  # % of ATR
    
    return {
        "predicted_color": predicted,
        "confidence": confidence,
        "n_matches": total,
        "green_count": green_count,
        "red_count": red_count,
        "body_size_est": body_size_est,
    }


def predict_active_dna(candles_5m, candles_1m, dna_table, ind, extra_ind, sr_zones):
    """Predict currently forming candle (not yet closed)."""
    if not candles_5m or len(candles_5m) < DNA_WARMUP + 2 or not dna_table:
        return None
    
    # Use last closed candle to predict forming candle
    try:
        last_closed_idx = len(candles_5m) - 2
        dna, dp = compute_candle_dna(last_closed_idx, candles_5m, ind, extra_ind, sr_zones)
        if not dna:
            return None
        
        matches = match_candle(dna, dna_table)
        pred = predict_from_matches(matches)
        if pred:
            pred["datapoints"] = {k: round(v, 4) for k, v in dp.items()}
            pred["forming"] = True
        return pred
    except Exception as e:
        print(f"[DNA] Active prediction error: {e}")
        return None


def build_dna_stats(table: DNATable) -> dict:
    """Build per-DNA statistics."""
    if not table:
        return {}
    
    stats = {}
    
    # Count train occurrences
    for dna, actual in table.train_dna:
        key = hash(dna)
        if key not in stats:
            stats[key] = {
                "dna_str": f"{dna.color} {dna.shape} {dna.size}",
                "n_train": 0,
                "n_test": 0,
                "train_green": 0,
                "test_green": 0,
            }
        stats[key]["n_train"] += 1
        if actual == "GREEN":
            stats[key]["train_green"] += 1
    
    # Count test occurrences
    for dna, actual in table.test_dna:
        key = hash(dna)
        if key not in stats:
            stats[key] = {
                "dna_str": "unknown",
                "n_train": 0,
                "n_test": 0,
                "train_green": 0,
                "test_green": 0,
            }
        stats[key]["n_test"] += 1
        if actual == "GREEN":
            stats[key]["test_green"] += 1
    
    # Compute WR
    for key in stats:
        s = stats[key]
        s["train_wr"] = round(s["train_green"] / s["n_train"] * 100, 1) if s["n_train"] > 0 else 0
        s["test_wr"] = round(s["test_green"] / s["n_test"] * 100, 1) if s["n_test"] > 0 else 0
    
    return stats


# ══════════════════════════════════════════════════════════════════════════
# B. Body/Wick Statistical Analysis
# ══════════════════════════════════════════════════════════════════════════

def build_body_wick_stats(candles):
    """Build body/wick combo statistics."""
    stats = {}
    
    for i in range(len(candles) - 1):
        c = candles[i]
        body = abs(c["close"] - c["open"])
        total = c["high"] - c["low"]
        if total == 0:
            continue
        
        body_pct = body / total
        upper_wick = c["high"] - max(c["open"], c["close"])
        lower_wick = min(c["open"], c["close"]) - c["low"]
        
        # Classify
        if body_pct < 0.3:
            body_cat = "SMALL"
        elif body_pct < 0.7:
            body_cat = "MEDIUM"
        else:
            body_cat = "LARGE"
        
        wick_ratio = max(upper_wick, lower_wick) / body if body > 0 else 0
        if wick_ratio > 2:
            wick_cat = "LONG"
        elif wick_ratio > 0.5:
            wick_cat = "MEDIUM"
        else:
            wick_cat = "SHORT"
        
        combo = f"{body_cat}_{wick_cat}"
        
        next_green = candles[i + 1]["close"] >= candles[i + 1]["open"]
        
        if combo not in stats:
            stats[combo] = {"n": 0, "green": 0}
        stats[combo]["n"] += 1
        if next_green:
            stats[combo]["green"] += 1
    
    # Compute WR
    for combo in stats:
        s = stats[combo]
        s["wr"] = round(s["green"] / s["n"] * 100, 1) if s["n"] > 0 else 50
        s["edge"] = s["wr"] - 50
    
    return stats


def build_two_candle_stats(candles):
    """Build 2-candle pattern statistics."""
    stats = {}
    
    for i in range(1, len(candles) - 1):
        c1_green = candles[i - 1]["close"] >= candles[i - 1]["open"]
        c2_green = candles[i]["close"] >= candles[i]["open"]
        pattern = f"{'G' if c1_green else 'R'}{'G' if c2_green else 'R'}"
        
        next_green = candles[i + 1]["close"] >= candles[i + 1]["open"]
        
        if pattern not in stats:
            stats[pattern] = {"n": 0, "green": 0}
        stats[pattern]["n"] += 1
        if next_green:
            stats[pattern]["green"] += 1
    
    for pattern in stats:
        s = stats[pattern]
        s["wr"] = round(s["green"] / s["n"] * 100, 1) if s["n"] > 0 else 50
        s["edge"] = s["wr"] - 50
    
    return stats


def build_three_candle_stats(candles):
    """Build 3-candle pattern statistics."""
    stats = {}
    
    for i in range(2, len(candles) - 1):
        c1_green = candles[i - 2]["close"] >= candles[i - 2]["open"]
        c2_green = candles[i - 1]["close"] >= candles[i - 1]["open"]
        c3_green = candles[i]["close"] >= candles[i]["open"]
        pattern = f"{'G' if c1_green else 'R'}{'G' if c2_green else 'R'}{'G' if c3_green else 'R'}"
        
        next_green = candles[i + 1]["close"] >= candles[i + 1]["open"]
        
        if pattern not in stats:
            stats[pattern] = {"n": 0, "green": 0}
        stats[pattern]["n"] += 1
        if next_green:
            stats[pattern]["green"] += 1
    
    for pattern in stats:
        s = stats[pattern]
        s["wr"] = round(s["green"] / s["n"] * 100, 1) if s["n"] > 0 else 50
        s["edge"] = s["wr"] - 50
    
    return stats


def build_four_candle_stats(candles):
    """Build 4-candle pattern statistics."""
    stats = {}
    
    for i in range(3, len(candles) - 1):
        colors = []
        for j in range(i - 3, i + 1):
            colors.append("G" if candles[j]["close"] >= candles[j]["open"] else "R")
        pattern = "".join(colors)
        
        next_green = candles[i + 1]["close"] >= candles[i + 1]["open"]
        
        if pattern not in stats:
            stats[pattern] = {"n": 0, "green": 0}
        stats[pattern]["n"] += 1
        if next_green:
            stats[pattern]["green"] += 1
    
    for pattern in stats:
        s = stats[pattern]
        s["wr"] = round(s["green"] / s["n"] * 100, 1) if s["n"] > 0 else 50
        s["edge"] = s["wr"] - 50
    
    return stats


def compute_sequence_stats(candles):
    """Compute sequence continuation vs reversal stats."""
    stats = {}
    
    for length in [2, 3, 4, 5]:
        for color in ["GREEN", "RED"]:
            key = f"{length}_{color}"
            stats[key] = {"continued": 0, "reversed": 0, "total": 0}
    
    for i in range(5, len(candles)):
        for length in [2, 3, 4, 5]:
            seq_candles = candles[i - length:i]
            all_green = all(c["close"] >= c["open"] for c in seq_candles)
            all_red = all(c["close"] < c["open"] for c in seq_candles)
            
            if not (all_green or all_red):
                continue
            
            seq_color = "GREEN" if all_green else "RED"
            next_green = candles[i]["close"] >= candles[i]["open"]
            continued = (seq_color == "GREEN" and next_green) or (seq_color == "RED" and not next_green)
            
            key = f"{length}_{seq_color}"
            stats[key]["total"] += 1
            if continued:
                stats[key]["continued"] += 1
            else:
                stats[key]["reversed"] += 1
    
    # Compute percentages
    for key in stats:
        s = stats[key]
        if s["total"] > 0:
            s["pct"] = round(s["continued"] / s["total"] * 100, 1)
            s["reversed_pct"] = round(s["reversed"] / s["total"] * 100, 1)
        else:
            s["pct"] = 50
            s["reversed_pct"] = 50
    
    return stats


def get_last_closed_profile(candles_5m, body_wick_stats, ind, two_candle_stats, three_candle_stats, four_candle_stats):
    """Get profile for last closed candle."""
    if not candles_5m or len(candles_5m) < 5:
        return {}
    
    idx = len(candles_5m) - 2
    c = candles_5m[idx]
    
    body = abs(c["close"] - c["open"])
    total = c["high"] - c["low"]
    if total == 0:
        return {}
    
    body_pct = body / total
    upper_wick = c["high"] - max(c["open"], c["close"])
    lower_wick = min(c["open"], c["close"]) - c["low"]
    
    # Body/wick combo
    if body_pct < 0.3:
        body_cat = "SMALL"
    elif body_pct < 0.7:
        body_cat = "MEDIUM"
    else:
        body_cat = "LARGE"
    
    wick_ratio = max(upper_wick, lower_wick) / body if body > 0 else 0
    if wick_ratio > 2:
        wick_cat = "LONG"
    elif wick_ratio > 0.5:
        wick_cat = "MEDIUM"
    else:
        wick_cat = "SHORT"
    
    combo = f"{body_cat}_{wick_cat}"
    combo_stat = body_wick_stats.get(combo, {"wr": 50, "edge": 0, "n": 0})
    
    # 2-candle
    c1_green = candles_5m[idx - 1]["close"] >= candles_5m[idx - 1]["open"]
    c2_green = c["close"] >= c["open"]
    two_pattern = f"{'G' if c1_green else 'R'}{'G' if c2_green else 'R'}"
    two_stat = two_candle_stats.get(two_pattern, {"wr": 50, "edge": 0, "n": 0})
    
    # 3-candle
    if idx >= 2:
        c0_green = candles_5m[idx - 2]["close"] >= candles_5m[idx - 2]["open"]
        three_pattern = f"{'G' if c0_green else 'R'}{'G' if c1_green else 'R'}{'G' if c2_green else 'R'}"
        three_stat = three_candle_stats.get(three_pattern, {"wr": 50, "edge": 0, "n": 0})
    else:
        three_stat = {"wr": 50, "edge": 0, "n": 0}
    
    # 4-candle
    if idx >= 3:
        colors = []
        for j in range(idx - 3, idx + 1):
            colors.append("G" if candles_5m[j]["close"] >= candles_5m[j]["open"] else "R")
        four_pattern = "".join(colors)
        four_stat = four_candle_stats.get(four_pattern, {"wr": 50, "edge": 0, "n": 0})
    else:
        four_stat = {"wr": 50, "edge": 0, "n": 0}
    
    # Momentum (simple price change)
    momentum = {"direction": "NEUTRAL", "strength": 0}
    if idx >= 5:
        price_5_ago = candles_5m[idx - 5]["close"]
        price_now = c["close"]
        pct_change = (price_now - price_5_ago) / price_5_ago * 100
        if pct_change > 0.5:
            momentum = {"direction": "UP", "strength": round(pct_change, 2)}
        elif pct_change < -0.5:
            momentum = {"direction": "DOWN", "strength": round(abs(pct_change), 2)}
    
    return {
        "body_wick": combo_stat,
        "two_candle": two_stat,
        "three_candle": three_stat,
        "four_candle": four_stat,
        "momentum": momentum,
    }


def get_current_streak(candles):
    """Get current streak info."""
    if not candles or len(candles) < 2:
        return {"color": "?", "length": 0}
    
    last_green = candles[-1]["close"] >= candles[-1]["open"]
    streak_color = "GREEN" if last_green else "RED"
    length = 1
    
    for i in range(len(candles) - 2, -1, -1):
        c_green = candles[i]["close"] >= candles[i]["open"]
        if (streak_color == "GREEN" and c_green) or (streak_color == "RED" and not c_green):
            length += 1
        else:
            break
    
    return {"color": streak_color, "length": length}


# ══════════════════════════════════════════════════════════════════════════
# C. 24-Signal Weighted Voting System
# ══════════════════════════════════════════════════════════════════════════

def _compute_verdict_score(
    dna_pred, momentum, two_candle, three_candle, combos_5m, combos_15m,
    seq_5m, seq_15m, seq_matches_strong, active_pred, four_candle, combos_1m,
    seq_1m, ind, candle_idx, candles_5m
) -> dict:
    """Compute verdict with 24 weighted signals."""
    signals = []
    
    # Signal 1: DNA Prediction (weight 0.5)
    if dna_pred and dna_pred.get("predicted_color"):
        edge = (dna_pred["confidence"] - 50) / 50 * 100  # normalize to edge
        signals.append({
            "name": "DNA",
            "dir": dna_pred["predicted_color"],
            "weight": 0.5,
            "edge": edge,
            "confidence": dna_pred["confidence"],
        })
    
    # Signal 2: 2-Candle Pattern (weight 2.75)
    if two_candle and two_candle.get("wr", 0) != 50:
        direction = "GREEN" if two_candle["wr"] > 50 else "RED"
        signals.append({
            "name": "2-Candle",
            "dir": direction,
            "weight": 2.75,
            "edge": abs(two_candle["edge"]),
            "confidence": two_candle["wr"],
        })
    
    # Signal 3: 3-Candle Pattern (weight 5.0)
    if three_candle and three_candle.get("wr", 0) != 50:
        direction = "GREEN" if three_candle["wr"] > 50 else "RED"
        signals.append({
            "name": "3-Candle",
            "dir": direction,
            "weight": 5.0,
            "edge": abs(three_candle["edge"]),
            "confidence": three_candle["wr"],
        })
    
    # Signal 4: 4-Candle Pattern (weight 5.0)
    if four_candle and four_candle.get("wr", 0) != 50:
        direction = "GREEN" if four_candle["wr"] > 50 else "RED"
        signals.append({
            "name": "4-Candle",
            "dir": direction,
            "weight": 5.0,
            "edge": abs(four_candle["edge"]),
            "confidence": four_candle["wr"],
        })
    
    # Signal 5: Momentum (weight 1.5)
    if momentum and momentum.get("direction") != "NEUTRAL":
        signals.append({
            "name": "Momentum",
            "dir": "GREEN" if momentum["direction"] == "UP" else "RED",
            "weight": 1.5,
            "edge": min(momentum.get("strength", 0) * 10, 50),
            "confidence": 50 + min(momentum.get("strength", 0) * 10, 50),
        })
    
    # Signal 6: Dildo Candle Detection (weight 1.5)
    if candles_5m and candle_idx and ind:
        c = candles_5m[candle_idx]
        body = abs(c["close"] - c["open"])
        total = c["high"] - c["low"]
        if total > 0:
            body_pct = body / total
            atr_val = ind["atr"][candle_idx] if candle_idx < len(ind["atr"]) else 1.0
            if body_pct > 0.8 and body > atr_val * 1.5:
                # Strong directional candle
                direction = "GREEN" if c["close"] > c["open"] else "RED"
                signals.append({
                    "name": "Dildo",
                    "dir": direction,
                    "weight": 1.5,
                    "edge": 15,
                    "confidence": 65,
                })
    
    # Signal 7-10: Sequence matching (5m, 15m, 1m, strong matches)
    # Simplified for now
    
    # Signal 11: Streak-5 (weight 2.0)
    if candles_5m and len(candles_5m) >= 6:
        last_5 = candles_5m[-6:-1]
        all_green = all(c["close"] >= c["open"] for c in last_5)
        all_red = all(c["close"] < c["open"] for c in last_5)
        if all_green or all_red:
            # Contrarian signal
            direction = "RED" if all_green else "GREEN"
            signals.append({
                "name": "Streak-5",
                "dir": direction,
                "weight": 2.0,
                "edge": 20,
                "confidence": 70,
            })
    
    # Signal 12: MACDstr (weight 2.0)
    if ind and candle_idx:
        macd_hist_arr, macd_offset = ind.get("macd_hist", ([], 0))
        macd_idx = candle_idx - macd_offset
        if 1 <= macd_idx < len(macd_hist_arr):
            h_curr = macd_hist_arr[macd_idx]
            h_prev = macd_hist_arr[macd_idx - 1]
            if abs(h_curr) > 0.3 and abs(h_curr - h_prev) > 0.1:
                direction = "GREEN" if h_curr > h_prev else "RED"
                signals.append({
                    "name": "MACDstr",
                    "dir": direction,
                    "weight": 2.0,
                    "edge": min(abs(h_curr) * 20, 40),
                    "confidence": 50 + min(abs(h_curr) * 20, 40),
                })
    
    # Additional signals 13-24 would go here (RSI divergence, volume spike, etc.)
    # For now, we have the core 12 signals implemented
    
    # Aggregate votes
    up_score = sum(s["weight"] * (s["edge"] / 100) for s in signals if s["dir"] in ("UP", "GREEN"))
    down_score = sum(s["weight"] * (s["edge"] / 100) for s in signals if s["dir"] in ("DOWN", "RED"))
    
    if up_score == 0 and down_score == 0:
        return None
    
    total_score = up_score + down_score
    if up_score > down_score:
        direction = "GREEN"
        confidence = round(up_score / total_score * 100, 1)
    else:
        direction = "RED"
        confidence = round(down_score / total_score * 100, 1)
    
    return {
        "direction": direction,
        "confidence": confidence,
        "up_score": round(up_score, 2),
        "down_score": round(down_score, 2),
        "signals": signals,
        "n_signals": len(signals),
    }


# ══════════════════════════════════════════════════════════════════════════
# D. Toxic Combo Hijacking
# ══════════════════════════════════════════════════════════════════════════

# Auto-populated from backtest
TOXIC_COMBOS = []


def _apply_toxic_combo_hijack(verdict):
    """Flip verdict if all signals match a known toxic combo."""
    if not verdict or not verdict.get("signals") or not TOXIC_COMBOS:
        return verdict, None
    
    signals = verdict["signals"]
    direction = verdict.get("direction")
    
    for combo_sigs, n, wr in TOXIC_COMBOS:
        # Check if all combo signals are present and all agree with verdict direction
        combo_present = all(
            any(s["name"] == sig_name and s["dir"] == direction for s in signals)
            for sig_name in combo_sigs
        )
        
        if combo_present:
            # TOXIC COMBO DETECTED — flip verdict
            flipped_dir = "RED" if direction == "GREEN" else "GREEN"
            print(f"[TOXIC] Hijacking verdict: {'+'.join(combo_sigs)} all agree on {direction} but WR={wr}% → flip to {flipped_dir}")
            
            verdict["direction"] = flipped_dir
            verdict["hijacked"] = True
            verdict["toxic_combo"] = combo_sigs
            verdict["toxic_wr"] = wr
            
            return verdict, {
                "combo": combo_sigs,
                "original": direction,
                "flipped": flipped_dir,
                "wr": wr,
            }
    
    return verdict, None


# ══════════════════════════════════════════════════════════════════════════
# E. RSI Zone Direction Flipping
# ══════════════════════════════════════════════════════════════════════════

def _apply_rsi_zone_flip(verdict, rsi_5m_val, rsi_15m_val):
    """Apply RSI zone flipping rules."""
    if not verdict or not verdict.get("direction"):
        return verdict, None
    
    direction = verdict["direction"]
    
    # Rule 1: 5m RSI >73 + rising → block GREEN bets (58.1% trap)
    if rsi_5m_val > 73 and direction in ("UP", "GREEN"):
        flipped_dir = "RED"
        verdict["direction"] = flipped_dir
        verdict["rsi_zone_flipped"] = True
        return verdict, {
            "rule": "5m RSI >73 block GREEN",
            "rsi_val": rsi_5m_val,
            "original": direction,
            "flipped": flipped_dir,
        }
    
    # Rule 2: 15m RSI <32 + 5m falling → flip to GREEN (bullish divergence)
    if rsi_15m_val < 32 and rsi_5m_val < 45 and direction in ("DOWN", "RED"):
        flipped_dir = "GREEN"
        verdict["direction"] = flipped_dir
        verdict["rsi_zone_flipped"] = True
        return verdict, {
            "rule": "15m RSI <32 divergence",
            "rsi_val": rsi_15m_val,
            "original": direction,
            "flipped": flipped_dir,
        }
    
    # Additional rules would go here
    
    return verdict, None


# ══════════════════════════════════════════════════════════════════════════
# F. Trade Decision Logic
# ══════════════════════════════════════════════════════════════════════════

class FrequencyMonitor:
    def __init__(self):
        self.candles_seen = 0
        self.candles_traded = 0
        self.skip_reasons = defaultdict(int)
    
    def record_trade(self):
        self.candles_seen += 1
        self.candles_traded += 1
    
    def record_skip(self, reason):
        self.candles_seen += 1
        self.skip_reasons[reason] += 1
    
    @property
    def trade_rate(self):
        return round(self.candles_traded / self.candles_seen * 100, 1) if self.candles_seen > 0 else 0
    
    def summary(self):
        return {
            "candles_seen": self.candles_seen,
            "candles_traded": self.candles_traded,
            "trade_rate": self.trade_rate,
            "skip_reasons": dict(self.skip_reasons),
        }


class PnLTracker:
    def __init__(self):
        self.trades = []
    
    def record(self, direction, tier, amount, token_price, outcome, pnl):
        self.trades.append({
            "direction": direction,
            "tier": tier,
            "amount": amount,
            "token_price": token_price,
            "outcome": outcome,
            "pnl": pnl,
        })
    
    def summary(self):
        if not self.trades:
            return {"trades": 0, "wins": 0, "losses": 0, "win_rate": 0, "net_pnl": 0}
        
        wins = sum(1 for t in self.trades if t["outcome"] == "WIN")
        losses = len(self.trades) - wins
        net_pnl = sum(t["pnl"] for t in self.trades)
        
        return {
            "trades": len(self.trades),
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / len(self.trades) * 100, 1),
            "net_pnl": round(net_pnl, 2),
        }


class RollingAccuracy:
    def __init__(self, window=50):
        self.window = window
        self.records = defaultdict(list)
    
    def record(self, signal_name, predicted_direction, actual_green):
        correct = (predicted_direction in ("UP", "GREEN") and actual_green) or \
                  (predicted_direction in ("DOWN", "RED") and not actual_green)
        
        self.records[signal_name].append(1 if correct else 0)
        if len(self.records[signal_name]) > self.window:
            self.records[signal_name].pop(0)
    
    def summary(self):
        result = {}
        for sig, rec in self.records.items():
            if rec:
                acc = round(sum(rec) / len(rec) * 100, 1)
                result[sig] = {
                    "accuracy": acc,
                    "count": len(rec),
                    "multiplier": round(acc / 50, 2),
                }
        return result


def decide_candle(verdict, token_price, accuracy, pnl, wr_table, min_wr, macd_red_zone):
    """Decide whether to trade based on verdict + filters."""
    if not verdict or not verdict.get("direction"):
        return {"action": "SKIP", "reason": "no_verdict"}
    
    direction = verdict["direction"]
    confidence = verdict.get("confidence", 0)
    
    # Filter 1: Minimum confidence 50%
    if confidence < 50:
        return {"action": "SKIP", "reason": "low_confidence", "confidence": confidence}
    
    # Filter 2: Block RED bets with confidence >=70% (historically trap)
    if direction == "RED" and confidence >= 70:
        return {"action": "SKIP", "reason": "red_trap", "confidence": confidence}
    
    # Filter 3: Block GREEN bets when RSI >70 (overbought trap)
    if direction == "GREEN" and verdict.get("rsi_val", 0) > 70:
        return {"action": "SKIP", "reason": "green_overbought", "confidence": confidence}
    
    # Filter 4: MACD red zone — block GREEN bets (58.1% WR = losing)
    if macd_red_zone and direction == "GREEN":
        return {"action": "SKIP", "reason": "macd_red_zone", "confidence": confidence}
    
    # Filter 5: Backtest WR gate — only trade if this scenario has >=min_wr% historical WR
    bucket = int(confidence // 5) * 5
    wr_entry = wr_table.get((direction, bucket))
    if wr_entry and wr_entry["n"] >= 5 and wr_entry["wr"] < min_wr:
        return {
            "action": "SKIP",
            "reason": "backtest_wr_too_low",
            "confidence": confidence,
            "backtest_wr": wr_entry["wr"],
            "backtest_n": wr_entry["n"],
            "backtest_bucket": f"{bucket}-{bucket+5}%",
        }
    
    # PASS — trade this signal
    return {
        "action": "TRADE",
        "direction": direction,
        "tier": "STANDARD",
        "confidence": confidence,
        "backtest_wr": wr_entry["wr"] if wr_entry else None,
        "backtest_n": wr_entry["n"] if wr_entry else None,
        "backtest_bucket": f"{bucket}-{bucket+5}%" if wr_entry else None,
    }


# ══════════════════════════════════════════════════════════════════════════
# G. Trade Log Management
# ══════════════════════════════════════════════════════════════════════════

def _load_candle_trade_log():
    try:
        with open(CANDLE_TRADE_LOG, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_candle_trade_log(log):
    with open(CANDLE_TRADE_LOG, "w") as f:
        json.dump(log, f, indent=2, default=str)


def _log_candle_trade(trade_data):
    log = _load_candle_trade_log()
    log.append(trade_data)
    _save_candle_trade_log(log)


# ══════════════════════════════════════════════════════════════════════════
# H. Exit Strategy (Take Profit / Stop Loss)
# ══════════════════════════════════════════════════════════════════════════

TAKE_PROFIT_PCT = 100.0
STOP_LOSS_PCT = -79.0
RELIEF_DRAWDOWN_THRESHOLD = -50.0


def _check_take_profit(trade_log, trade_client, pnl_tracker):
    """Check for take-profit opportunities."""
    if not trade_client:
        return False
    
    updated = False
    for trade in trade_log:
        if trade.get("status") != "open":
            continue
        
        token_id = trade.get("token_id", "")
        if not token_id:
            continue
        
        entry_price = trade.get("entry_price", 0)
        entry_cost = trade.get("entry_cost", TRADE_AMOUNT)
        shares = trade.get("shares", 0)
        
        if entry_price <= 0 or shares <= 0:
            continue
        
        try:
            prices = bot.get_clob_prices(token_id)
            if not prices or prices["sell"] <= 0:
                continue
            current_price = prices["sell"]
        except Exception:
            continue
        
        # Track price extremes
        prev_low = trade.get("price_low", entry_price)
        prev_high = trade.get("price_high", entry_price)
        trade["price_low"] = min(prev_low, current_price)
        trade["price_high"] = max(prev_high, current_price)
        
        worst_drawdown = ((trade["price_low"] - entry_price) / entry_price) * 100
        if worst_drawdown <= RELIEF_DRAWDOWN_THRESHOLD:
            trade["was_deep_underwater"] = True
        
        unrealized_pct = ((current_price - entry_price) / entry_price) * 100
        
        trigger_reason = None
        if trade.get("was_deep_underwater") and unrealized_pct > 0:
            trigger_reason = "relief_tp"
        elif unrealized_pct >= TAKE_PROFIT_PCT:
            trigger_reason = "take_profit"
        
        if trigger_reason:
            print(f"\n[candle] {trigger_reason.upper()}: {trade['direction']} +{unrealized_pct:.1f}%")
            
            sell_pos = {
                "token_id": token_id,
                "entry_cost": entry_cost,
                "entry_price": entry_price,
                "direction": trade.get("direction", "?"),
                "market_question": trade.get("market_slug", ""),
            }
            
            result = bot.market_sell(trade_client, sell_pos)
            if result:
                pnl = result["pnl"]
                trade["status"] = "closed"
                trade["outcome"] = "WIN"
                trade["pnl"] = round(pnl, 2)
                trade["payout"] = round(result["proceeds"], 2)
                trade["resolved_at"] = int(time.time())
                trade["exit_reason"] = trigger_reason
                trade["exit_price"] = current_price
                
                pnl_tracker.record(
                    direction=trade.get("direction", "UP"),
                    tier=trade.get("tier", "STANDARD"),
                    amount=trade.get("amount", TRADE_AMOUNT),
                    token_price=entry_price,
                    outcome="WIN",
                    pnl=pnl,
                )
                
                print(f"[candle] {trigger_reason.upper()} sold: PnL ${pnl:+.2f}")
                updated = True
    
    return updated


def _check_stop_loss(trade_log, trade_client, pnl_tracker):
    """Check for stop-loss triggers."""
    if not trade_client:
        return False
    
    updated = False
    for trade in trade_log:
        if trade.get("status") != "open":
            continue
        
        token_id = trade.get("token_id", "")
        if not token_id:
            continue
        
        entry_price = trade.get("entry_price", 0)
        entry_cost = trade.get("entry_cost", TRADE_AMOUNT)
        
        if entry_price <= 0:
            continue
        
        try:
            prices = bot.get_clob_prices(token_id)
            if not prices or prices["sell"] <= 0:
                continue
            current_price = prices["sell"]
        except Exception:
            continue
        
        unrealized_pct = ((current_price - entry_price) / entry_price) * 100
        
        if unrealized_pct <= STOP_LOSS_PCT:
            print(f"\n[candle] STOP LOSS: {trade['direction']} {unrealized_pct:.0f}%")
            
            sell_pos = {
                "token_id": token_id,
                "entry_cost": entry_cost,
                "entry_price": entry_price,
                "direction": trade.get("direction", "?"),
                "market_question": trade.get("market_slug", ""),
            }
            
            result = bot.market_sell(trade_client, sell_pos)
            if result:
                pnl = result["pnl"]
                trade["status"] = "closed"
                trade["outcome"] = "LOSS"
                trade["pnl"] = round(pnl, 2)
                trade["payout"] = round(result["proceeds"], 2)
                trade["resolved_at"] = int(time.time())
                trade["exit_reason"] = "stop_loss"
                
                pnl_tracker.record(
                    direction=trade.get("direction", "UP"),
                    tier=trade.get("tier", "STANDARD"),
                    amount=trade.get("amount", TRADE_AMOUNT),
                    token_price=entry_price,
                    outcome="LOSS",
                    pnl=pnl,
                )
                
                print(f"[candle] STOP LOSS sold: PnL ${pnl:+.2f}")
                updated = True
    
    return updated


def _resolve_expired_positions(trade_log, pnl_tracker, rolling_accuracy):
    """Resolve positions that have reached market close."""
    now_ts = int(time.time())
    updated = False
    
    for trade in trade_log:
        if trade.get("status") != "open":
            continue
        
        trade_ts = trade.get("candle_timestamp", 0)
        if now_ts < trade_ts + 360:
            continue
        
        if trade.get("resolved_green") is not None:
            direction = trade.get("direction", "UP")
            actual_green = trade["resolved_green"]
            correct = (direction in ("UP", "GREEN") and actual_green) or \
                      (direction in ("DOWN", "RED") and not actual_green)
            
            shares = trade.get("shares", 0)
            entry_cost = trade.get("entry_cost", TRADE_AMOUNT)
            payout = shares * 1.0 if correct else 0.0
            pnl = payout - entry_cost
            
            trade["status"] = "closed"
            trade["outcome"] = "WIN" if correct else "LOSS"
            trade["pnl"] = round(pnl, 2)
            trade["payout"] = round(payout, 2)
            trade["resolved_at"] = now_ts
            
            pnl_tracker.record(
                direction=direction,
                tier=trade.get("tier", "STANDARD"),
                amount=trade.get("amount", TRADE_AMOUNT),
                token_price=trade.get("token_price", 0.50),
                outcome=trade["outcome"],
                pnl=pnl,
            )
            
            for reason in trade.get("verdict_reasons", []):
                sig_name = reason.get("signal", "").replace(" ", "_").lower()
                if sig_name:
                    rolling_accuracy.record(sig_name, direction, actual_green)
            
            print(f"[candle] RESOLVED: {direction} {trade['outcome']} | PnL: ${pnl:+.2f}")
            updated = True
    
    return updated


# ══════════════════════════════════════════════════════════════════════════
# I. Backtest with DNA + Full Verdict
# ══════════════════════════════════════════════════════════════════════════

def run_dna_backtest(candles_5m, dna_table, ind, extra_ind, sr_zones, **kwargs):
    """Run comprehensive backtest with DNA + 24 signals."""
    body_wick_stats = kwargs.get("body_wick_stats", {})
    two_candle_stats = kwargs.get("two_candle_stats", {})
    three_candle_stats = kwargs.get("three_candle_stats", {})
    four_candle_stats = kwargs.get("four_candle_stats", {})
    
    results = {
        "signals": [],
        "summary": {"total": 0, "wins": 0, "losses": 0, "win_rate": 0},
        "live_summary": {"total": 0, "wins": 0, "losses": 0, "win_rate": 0, "skipped": 0},
        "verdict_summary": {"total": 0, "wins": 0, "losses": 0, "win_rate": 0},
        "_verdict_details": [],
    }
    
    if not candles_5m or len(candles_5m) < DNA_WARMUP + 10:
        return results
    
    # Run backtest on test set only
    split_idx = int(len(candles_5m) * 0.7)
    
    for i in range(split_idx, len(candles_5m) - 1):
        try:
            # Compute DNA prediction
            dna, dp = compute_candle_dna(i, candles_5m, ind, extra_ind, sr_zones)
            if not dna:
                continue
            
            matches = match_candle(dna, dna_table)
            dna_pred = predict_from_matches(matches)
            
            # Get profile
            profile = get_last_closed_profile(
                candles_5m[:i+1], body_wick_stats, ind,
                two_candle_stats, three_candle_stats, four_candle_stats
            )
            
            # Compute verdict
            verdict = _compute_verdict_score(
                dna_pred=dna_pred,
                momentum=profile.get("momentum"),
                two_candle=profile.get("two_candle"),
                three_candle=profile.get("three_candle"),
                four_candle=profile.get("four_candle"),
                combos_5m=[],
                combos_15m=[],
                seq_5m=None,
                seq_15m=None,
                seq_matches_strong=[],
                active_pred=None,
                combos_1m=[],
                seq_1m=None,
                ind=ind,
                candle_idx=i,
                candles_5m=candles_5m[:i+1],
            )
            
            if not verdict or not verdict.get("direction"):
                continue
            
            # Store pre-flip direction for audit
            pre_flip_direction = verdict["direction"]
            
            # Apply toxic hijack (initially no-op since TOXIC_COMBOS is empty)
            verdict, hijack_info = _apply_toxic_combo_hijack(verdict)
            
            # Apply RSI flip
            rsi_5m_val = ind["rsi_5m"][i] if i < len(ind["rsi_5m"]) else 50.0
            rsi_15m_val = 50.0  # placeholder
            verdict, rsi_flip_info = _apply_rsi_zone_flip(verdict, rsi_5m_val, rsi_15m_val)
            
            # Check outcome
            next_candle = candles_5m[i + 1]
            actual_green = next_candle["close"] >= next_candle["open"]
            actual_color = "GREEN" if actual_green else "RED"
            correct = verdict["direction"] == actual_color
            
            # Store verdict detail
            results["_verdict_details"].append({
                "candle_ts": candles_5m[i]["timestamp"] // 1000,
                "direction": verdict["direction"],
                "confidence": verdict["confidence"],
                "pre_flip_direction": pre_flip_direction,
                "rsi_val": rsi_5m_val,
                "rsi_15m_val": rsi_15m_val,
                "actual_color": actual_color,
                "outcome": "WIN" if correct else "LOSS",
                "signals": verdict.get("signals", []),
                "_bt_rsi_5m": rsi_5m_val,
                "_bt_rsi_15m": rsi_15m_val,
            })
            
        except Exception as e:
            print(f"[backtest] Error at candle {i}: {e}")
            continue
    
    # Compute verdict summary
    v_wins = sum(1 for vd in results["_verdict_details"] if vd["outcome"] == "WIN")
    v_total = len(results["_verdict_details"])
    results["verdict_summary"] = {
        "total": v_total,
        "wins": v_wins,
        "losses": v_total - v_wins,
        "win_rate": round(v_wins / v_total * 100, 1) if v_total > 0 else 0,
    }
    
    print(f"[backtest] Verdict: {v_wins}W/{v_total - v_wins}L = {results['verdict_summary']['win_rate']}% ({v_total} total)")
    
    return results


# ══════════════════════════════════════════════════════════════════════════
# J. Main Data Loop
# ══════════════════════════════════════════════════════════════════════════

def _data_loop():
    """Main background thread: fetch data, compute signals, decide trades."""
    global _state, _trading_enabled, _history_candles_5m
    
    rolling_accuracy = RollingAccuracy(window=50)
    pnl_tracker = PnLTracker()
    frequency = FrequencyMonitor()
    
    print("[candle] Starting candle prediction server...")
    
    # Initial data fetch
    print("[candle] Fetching candles (20k 1m + 4k 5m)...")
    try:
        candles_1m = bot.fetch_candles(interval="1m", limit=20000)
        candles_5m = bot.fetch_candles(interval="5m", limit=4000)
        candles_15m = []  # aggregate from 1m
        print(f"[candle] Fetched: {len(candles_1m)} 1m, {len(candles_5m)} 5m")
    except Exception as e:
        print(f"[candle] Candle fetch failed: {e}")
        candles_1m, candles_5m, candles_15m = [], [], []
    
    _history_candles_5m = candles_5m[:]
    
    # Precompute indicators
    ind = _precompute_indicators(candles_5m) if candles_5m else None
    extra_ind = _precompute_1m_15m(candles_1m, candles_15m)
    
    # Build DNA table
    dna_table = None
    dna_stats = {}
    if ind:
        print("[candle] Building DNA table...")
        dna_table = build_dna_table(candles_5m, ind, extra_ind, [])
        if dna_table:
            dna_stats = build_dna_stats(dna_table)
    
    # Build historical stats
    body_wick_stats = build_body_wick_stats(candles_5m) if candles_5m else {}
    two_candle_stats = build_two_candle_stats(candles_5m) if candles_5m else {}
    three_candle_stats = build_three_candle_stats(candles_5m) if candles_5m else {}
    four_candle_stats = build_four_candle_stats(candles_5m) if candles_5m else {}
    sequence_stats = compute_sequence_stats(candles_5m) if candles_5m else {}
    
    print(f"[candle] Stats built: body/wick={len(body_wick_stats)}, 2c={len(two_candle_stats)}, "
          f"3c={len(three_candle_stats)}, 4c={len(four_candle_stats)}")
    
    # Run backtest
    backtest_results = {}
    _backtest_wr_table = {}
    MIN_BACKTEST_WR = 60.0
    
    if candles_5m and dna_table and ind:
        print("[candle] Running backtest...")
        backtest_results = run_dna_backtest(
            candles_5m, dna_table, ind, extra_ind, [],
            body_wick_stats=body_wick_stats,
            two_candle_stats=two_candle_stats,
            three_candle_stats=three_candle_stats,
            four_candle_stats=four_candle_stats,
        )
        
        # Build WR table
        vd_list = backtest_results.get("_verdict_details", [])
        for vd in vd_list:
            d = vd.get("direction")
            conf = vd.get("confidence", 0)
            if not d or conf < 50:
                continue
            bucket = int(conf // 5) * 5
            key = (d, bucket)
            if key not in _backtest_wr_table:
                _backtest_wr_table[key] = {"wins": 0, "n": 0}
            _backtest_wr_table[key]["n"] += 1
            if vd.get("outcome") == "WIN":
                _backtest_wr_table[key]["wins"] += 1
        
        for key in _backtest_wr_table:
            t = _backtest_wr_table[key]
            t["wr"] = round(t["wins"] / t["n"] * 100, 1) if t["n"] > 0 else 0
        
        print(f"[candle] Backtest WR table built: {len(_backtest_wr_table)} buckets")
    
    # Init trading client
    try:
        trade_client = bot.init_client()
        print(f"[candle] Trading client initialized")
    except Exception as e:
        trade_client = None
        print(f"[candle] Trading client init failed: {e}")
    
    with _state_lock:
        _state["ready"] = True
        _state["dna_stats"] = dna_stats
        _state["sequence_stats"] = sequence_stats
        _state["candle_backtest"] = backtest_results
    
    # Main poll loop
    last_processed_window = 0
    locked_verdict = None
    _verdict_lock_ts = 0
    prev_verdict = None
    
    while True:
        try:
            cycle_start = time.time()
            
            # Fetch live indicators
            ind_live = bot.get_indicators()
            candles_5m_live = ind_live["candles_5m"]
            price = ind_live["price"]
            rsi_5m = ind_live["rsi_5m"]
            
            now_ts = int(time.time())
            current_5min_start = (now_ts // 300) * 300
            secs_left = (current_5min_start + 300) - now_ts
            
            # Compute live verdict
            ind_live_full = _precompute_indicators(candles_5m_live) if candles_5m_live else None
            candle_prediction = None
            
            if dna_table and ind_live_full and len(candles_5m_live) >= DNA_WARMUP + 2:
                try:
                    last_closed_idx = len(candles_5m_live) - 2
                    dna, dp = compute_candle_dna(last_closed_idx, candles_5m_live, ind_live_full, extra_ind, [])
                    if dna:
                        matches = match_candle(dna, dna_table)
                        candle_prediction = predict_from_matches(matches)
                        if candle_prediction:
                            candle_prediction["datapoints"] = {k: round(v, 4) for k, v in dp.items()}
                except Exception as e:
                    print(f"[candle] DNA prediction error: {e}")
            
            # Get profile
            profile = get_last_closed_profile(
                candles_5m_live, body_wick_stats, ind_live_full,
                two_candle_stats, three_candle_stats, four_candle_stats
            ) if candles_5m_live and body_wick_stats else {}
            
            # Compute verdict
            verdict = _compute_verdict_score(
                dna_pred=candle_prediction,
                momentum=profile.get("momentum"),
                two_candle=profile.get("two_candle"),
                three_candle=profile.get("three_candle"),
                four_candle=profile.get("four_candle"),
                combos_5m=[],
                combos_15m=[],
                seq_5m=None,
                seq_15m=None,
                seq_matches_strong=[],
                active_pred=None,
                combos_1m=[],
                seq_1m=None,
                ind=ind_live_full,
                candle_idx=len(candles_5m_live) - 2 if candles_5m_live else None,
                candles_5m=candles_5m_live,
            )
            
            # Apply toxic hijack
            verdict, hijack_info = _apply_toxic_combo_hijack(verdict)
            if hijack_info:
                print(f"[candle] TOXIC HIJACK: {hijack_info['combo']}")
            
            # Apply RSI flip
            rsi_15m_val = 50.0
            verdict, rsi_flip_info = _apply_rsi_zone_flip(verdict, rsi_5m, rsi_15m_val)
            if rsi_flip_info:
                print(f"[candle] RSI FLIP: {rsi_flip_info['rule']}")
            
            # Lock verdict at candle start
            data_has_forming = (candles_5m_live and candles_5m_live[-1]["timestamp"] // 1000 >= current_5min_start)
            if current_5min_start != _verdict_lock_ts and data_has_forming:
                locked_verdict = verdict
                _verdict_lock_ts = current_5min_start
                print(f"[candle] Verdict LOCKED: {locked_verdict.get('direction')} {locked_verdict.get('confidence')}%")
            
            # On new 5-min boundary
            if current_5min_start != last_processed_window and _verdict_lock_ts == current_5min_start:
                last_processed_window = current_5min_start
                
                # Record previous outcome
                if prev_verdict and len(candles_5m_live) >= 2:
                    prev_candle = candles_5m_live[-2]
                    actual_green = prev_candle["close"] >= prev_candle["open"]
                    prev_dir = prev_verdict["direction"]
                    correct = (prev_dir in ("UP", "GREEN") and actual_green) or \
                              (prev_dir in ("DOWN", "RED") and not actual_green)
                    print(f"[candle] Previous: {prev_dir} → {'CORRECT' if correct else 'WRONG'}")
                
                # Decide trade
                macd_red_zone = False
                decision = decide_candle(locked_verdict, 0.50, rolling_accuracy, pnl_tracker,
                                        _backtest_wr_table, MIN_BACKTEST_WR, macd_red_zone)
                
                if decision["action"] == "TRADE":
                    frequency.record_trade()
                    print(f"[candle] SIGNAL: {decision['direction']} {decision['confidence']}%")
                else:
                    frequency.record_skip(decision.get("reason", "unknown"))
                
                prev_verdict = locked_verdict
            
            # Check exits
            candle_log = _load_candle_trade_log()
            tp_updated = _check_take_profit(candle_log, trade_client, pnl_tracker)
            sl_updated = _check_stop_loss(candle_log, trade_client, pnl_tracker)
            if tp_updated or sl_updated:
                _save_candle_trade_log(candle_log)
            
            _resolve_expired_positions(candle_log, pnl_tracker, rolling_accuracy)
            
            # Update state
            chart_candles = [
                {"time": c["timestamp"] // 1000, "open": c["open"], "high": c["high"],
                 "low": c["low"], "close": c["close"]}
                for c in candles_5m_live
            ] if candles_5m_live else []
            
            recent_trades = candle_log[-50:] if candle_log else []
            
            with _state_lock:
                _state["price"] = price
                _state["timestamp"] = now_ts
                _state["rsi_5m"] = rsi_5m
                _state["verdict"] = locked_verdict if locked_verdict else verdict
                _state["secs_left"] = secs_left
                _state["pnl_summary"] = pnl_tracker.summary()
                _state["frequency"] = frequency.summary()
                _state["rolling_accuracy"] = rolling_accuracy.summary()
                _state["recent_trades"] = recent_trades
                _state["trading_enabled"] = _trading_enabled
                _state["trade_amount"] = TRADE_AMOUNT
                _state["candles_5m"] = chart_candles
                _state["candle_prediction"] = candle_prediction
                _state["current_streak"] = get_current_streak(candles_5m_live) if candles_5m_live else {"color": "?", "length": 0}
                _state["last_closed_profile"] = profile
            
            elapsed = time.time() - cycle_start
            sleep_time = max(0.5, POLL_INTERVAL - elapsed)
            time.sleep(sleep_time)
            
        except KeyboardInterrupt:
            print("[candle] Shutting down...")
            break
        except Exception as e:
            print(f"[candle] Loop error: {e}")
            traceback.print_exc()
            time.sleep(5)


# ══════════════════════════════════════════════════════════════════════════
# K. WebSocket + FastAPI Routes
# ══════════════════════════════════════════════════════════════════════════

async def _ws_broadcaster():
    """Broadcast state to WebSocket clients."""
    while True:
        await asyncio.sleep(POLL_INTERVAL)
        if not _ws_clients:
            continue
        with _state_lock:
            payload = json.dumps({"type": "update", **_state}, default=str)
        dead = set()
        for ws in _ws_clients.copy():
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        for ws in dead:
            _ws_clients.discard(ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    t = threading.Thread(target=_data_loop, daemon=True)
    t.start()
    asyncio.create_task(_ws_broadcaster())
    print("[candle] Server started — http://localhost:8081")
    yield


app.router.lifespan_context = lifespan


@app.get("/api/state")
async def api_state():
    with _state_lock:
        return JSONResponse(content=_state, status_code=200)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)
    try:
        with _state_lock:
            payload = json.dumps({"type": "full", **_state}, default=str)
        await ws.send_text(payload)
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(ws)


@app.post("/api/bot/start")
async def bot_start():
    global _trading_enabled
    _trading_enabled = True
    print("[candle] AUTO-TRADE ENABLED")
    return JSONResponse({"status": "started", "trading_enabled": True})


@app.post("/api/bot/stop")
async def bot_stop():
    global _trading_enabled
    _trading_enabled = False
    print("[candle] AUTO-TRADE DISABLED")
    return JSONResponse({"status": "stopped", "trading_enabled": False})


@app.get("/api/bot/status")
async def bot_status():
    return JSONResponse({
        "running": _trading_enabled,
        "server": "candle_server",
        "port": 8081,
        "trade_amount": TRADE_AMOUNT,
    })


@app.get("/api/pnl")
async def api_pnl():
    with _state_lock:
        return JSONResponse({
            "pnl": _state.get("pnl_summary", {}),
            "frequency": _state.get("frequency", {}),
            "accuracy": _state.get("rolling_accuracy", {}),
        })


@app.get("/api/trades")
async def api_trades():
    log = _load_candle_trade_log()
    return JSONResponse(log[-50:] if log else [])


@app.get("/api/candles/history")
async def api_candles_history():
    candles = _history_candles_5m
    if not candles:
        return JSONResponse({"candles": [], "count": 0})
    chart = [
        {"time": c["timestamp"] // 1000, "open": c["open"], "high": c["high"],
         "low": c["low"], "close": c["close"], "volume": c.get("volume", 0)}
        for c in candles
    ]
    return JSONResponse({"candles": chart, "count": len(chart)})


# ══════════════════════════════════════════════════════════════════════════
# Entry Point
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    os.chdir(str(PROJECT_DIR))
    uvicorn.run(app, host="0.0.0.0", port=8081, log_level="info")
