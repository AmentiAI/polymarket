#!/usr/bin/env python3
"""Scan all 20 wallets for ALL token holdings."""
import os
import json
import requests
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

RPC_URL = os.getenv("SOLANA_RPC_URL")
WALLETS_PATH = "wallets.json"

def get_token_accounts(address: str):
    """Get all token accounts."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            address,
            {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
            {"encoding": "jsonParsed"}
        ]
    }
    try:
        resp = requests.post(RPC_URL, json=payload, timeout=15)
        if resp.ok:
            return resp.json().get("result", {}).get("value", [])
    except Exception:
        pass
    return []

with open(WALLETS_PATH) as f:
    wallets = json.load(f)["wallets"]

# Group tokens by mint
tokens_by_mint = defaultdict(list)

print("Scanning all 20 wallets for token holdings...\n")

for w in wallets:
    idx = w["index"]
    addr = w["address"]
    
    token_accounts = get_token_accounts(addr)
    
    for acct in token_accounts:
        try:
            info = acct["account"]["data"]["parsed"]["info"]
            mint = info["mint"]
            balance = float(info["tokenAmount"]["uiAmountString"])
            
            if balance > 0:
                tokens_by_mint[mint].append({
                    "wallet": f"W{idx:02d}",
                    "address": addr,
                    "balance": balance
                })
        except Exception:
            continue

print("="*80)
print("ALL TOKENS FOUND:")
print("="*80)

for mint, holders in tokens_by_mint.items():
    total_balance = sum(h["balance"] for h in holders)
    print(f"\nToken: {mint}")
    print(f"Total Balance: {total_balance:,.2f}")
    print(f"Held by {len(holders)} wallets:")
    
    # Calculate percentages
    for holder in sorted(holders, key=lambda x: x["balance"], reverse=True):
        pct = (holder["balance"] / total_balance) * 100
        print(f"  {holder['wallet']}: {holder['balance']:,.2f} ({pct:.2f}%)")

print("\n" + "="*80)
print(f"Found {len(tokens_by_mint)} unique tokens across your wallets")
print("="*80)
