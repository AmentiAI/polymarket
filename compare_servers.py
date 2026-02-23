#!/usr/bin/env python3
"""
Compare predictions from both servers (8080 vs 8081)
"""

import requests
import json
import time
from datetime import datetime

def get_verdict(port):
    """Fetch verdict from server."""
    try:
        r = requests.get(f"http://localhost:{port}/api/state", timeout=2)
        data = r.json()
        verdict = data.get("verdict", {})
        return {
            "direction": verdict.get("direction", "?"),
            "confidence": verdict.get("confidence", 0),
            "n_signals": len(verdict.get("signals", [])) if "signals" in verdict else verdict.get("n_signals", 0),
            "hijacked": verdict.get("hijacked", False),
            "rsi_flipped": verdict.get("rsi_zone_flipped", False),
        }
    except Exception as e:
        return {"error": str(e)}

def main():
    print("═" * 80)
    print("  Polymarket Sniper — Dual Server Comparison")
    print("  Port 8080: Flask (current) | Port 8081: FastAPI (candle server)")
    print("═" * 80)
    print("")
    
    while True:
        try:
            now = datetime.now().strftime("%H:%M:%S")
            
            current = get_verdict(8080)
            candle = get_verdict(8081)
            
            print(f"[{now}]")
            print(f"  Current (8080): {current.get('direction', '?'):5s} {current.get('confidence', 0):5.1f}% "
                  f"| {current.get('n_signals', 0)} signals")
            
            hijack_tag = " [HIJACKED]" if candle.get("hijacked") else ""
            rsi_tag = " [RSI-FLIP]" if candle.get("rsi_flipped") else ""
            print(f"  Candle  (8081): {candle.get('direction', '?'):5s} {candle.get('confidence', 0):5.1f}% "
                  f"| {candle.get('n_signals', 0)} signals{hijack_tag}{rsi_tag}")
            
            # Agreement check
            if current.get("direction") == candle.get("direction"):
                print(f"  ✓ AGREE on {current['direction']}")
            else:
                print(f"  ✗ DISAGREE: {current.get('direction')} vs {candle.get('direction')}")
            
            print("")
            time.sleep(5)
            
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
