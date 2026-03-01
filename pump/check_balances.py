#!/usr/bin/env python3
"""Check balances of all wallets."""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

WALLETS_PATH = "wallets.json"
RPC_URL = os.getenv("SOLANA_RPC_URL")

def get_balance(address: str) -> float:
    """Get SOL balance for an address."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getBalance",
        "params": [address]
    }
    try:
        resp = requests.post(RPC_URL, json=payload, timeout=10)
        if resp.ok:
            lamports = resp.json().get("result", {}).get("value", 0)
            return lamports / 1_000_000_000
    except Exception as e:
        print(f"Error checking {address}: {e}")
    return 0.0

with open(WALLETS_PATH) as f:
    wallets = json.load(f)["wallets"]

print(f"{'IDX':<5} {'ADDRESS':<46} {'BALANCE (SOL)':>15}")
print("=" * 70)

total_sol = 0.0
funded_wallets = []

for w in wallets:
    idx = w["index"]
    addr = w["address"]
    bal = get_balance(addr)
    total_sol += bal
    
    if bal > 0:
        funded_wallets.append((idx, addr, bal))
    
    print(f"W{idx:<4} {addr}  {bal:>15.9f}")

print("=" * 70)
print(f"TOTAL: {total_sol:.9f} SOL across {len(funded_wallets)} funded wallets")

if funded_wallets:
    print(f"\nFunded wallets:")
    for idx, addr, bal in funded_wallets:
        print(f"  W{idx}: {addr} - {bal:.9f} SOL")
