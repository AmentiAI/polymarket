#!/usr/bin/env python3
"""Check all wallets for token holdings (not just SOL)."""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

RPC_URL = os.getenv("SOLANA_RPC_URL")
WALLETS_PATH = "wallets.json"

def get_token_accounts(address: str):
    """Get all token accounts for an address."""
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
    except Exception as e:
        pass
    return []

with open(WALLETS_PATH) as f:
    wallets = json.load(f)["wallets"]

print("Checking all 20 wallets for token holdings...\n")
print(f"{'WALLET':<7} {'ADDRESS':<46} {'TOKENS'}")
print("="*100)

total_wallets_with_tokens = 0
all_tokens = []

for w in wallets:
    idx = w["index"]
    addr = w["address"]
    
    token_accounts = get_token_accounts(addr)
    
    if token_accounts:
        total_wallets_with_tokens += 1
        print(f"\nW{idx:02d}     {addr}")
        
        for acct in token_accounts:
            try:
                info = acct["account"]["data"]["parsed"]["info"]
                mint = info["mint"]
                balance = float(info["tokenAmount"]["uiAmountString"])
                decimals = info["tokenAmount"]["decimals"]
                
                if balance > 0:
                    print(f"        Token: {mint}")
                    print(f"        Balance: {balance:.{decimals}f}")
                    all_tokens.append({
                        "wallet": f"W{idx:02d}",
                        "address": addr,
                        "mint": mint,
                        "balance": balance
                    })
            except Exception as e:
                print(f"        Error parsing token: {e}")
    else:
        print(f"W{idx:02d}     {addr}  - No tokens")

print(f"\n{'='*100}")
print(f"Summary: {total_wallets_with_tokens} wallets have token holdings")

if all_tokens:
    print(f"\nTotal tokens found: {len(all_tokens)}")
    print("\nTo sweep these tokens, you would need to:")
    print("1. Identify which tokens have value (check dexscreener/birdeye)")
    print("2. Fund each wallet with ~0.002 SOL for transaction fees")
    print("3. Create a script to transfer tokens to your target address")
print("="*100)
