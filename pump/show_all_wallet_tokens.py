#!/usr/bin/env python3
"""Show every wallet and what tokens it holds."""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

RPC_URL = os.getenv("SOLANA_RPC_URL")
WALLETS_PATH = "wallets.json"

def get_sol_balance(address: str) -> float:
    """Get SOL balance."""
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
    except Exception:
        pass
    return 0.0

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

print("="*100)
print("ALL WALLET HOLDINGS - COMPLETE BREAKDOWN")
print("="*100)

for w in wallets:
    idx = w["index"]
    addr = w["address"]
    
    print(f"\n{'='*100}")
    print(f"WALLET #{idx:02d}")
    print(f"{'='*100}")
    print(f"Address: {addr}")
    
    # SOL balance
    sol_bal = get_sol_balance(addr)
    print(f"\nSOL Balance: {sol_bal:.9f} SOL")
    if sol_bal > 0:
        print(f"             (${sol_bal * 200:.2f} USD at $200/SOL)")
    
    # Token balances
    token_accounts = get_token_accounts(addr)
    
    if token_accounts:
        print(f"\nTOKENS ({len(token_accounts)} found):")
        print("-" * 100)
        
        for acct in token_accounts:
            try:
                info = acct["account"]["data"]["parsed"]["info"]
                mint = info["mint"]
                balance = float(info["tokenAmount"]["uiAmountString"])
                decimals = info["tokenAmount"]["decimals"]
                
                if balance > 0:
                    print(f"\n  Token Mint: {mint}")
                    print(f"  Balance:    {balance:,.{decimals}f}")
                else:
                    print(f"\n  Token Mint: {mint}")
                    print(f"  Balance:    0 (empty/closed)")
            except Exception as e:
                print(f"\n  Error reading token: {e}")
    else:
        print(f"\nTOKENS: None")

print(f"\n{'='*100}")
print("SUMMARY")
print(f"{'='*100}")

# Count wallets with SOL
sol_count = sum(1 for w in wallets if get_sol_balance(w["address"]) > 0)
print(f"Wallets with SOL: {sol_count}/20")

# Count wallets with tokens
token_count = sum(1 for w in wallets if len(get_token_accounts(w["address"])) > 0)
print(f"Wallets with tokens: {token_count}/20")

print(f"{'='*100}")
