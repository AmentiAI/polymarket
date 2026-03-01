#!/usr/bin/env python3
"""Find where funds were swept to by checking transaction history of wallet #0."""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

RPC_URL = os.getenv("SOLANA_RPC_URL")
SOURCE_WALLET = "3QHkG2h84pyyqgTyYTu6y3ckZi5ynpxbSqKEV5poLaZ6"

def get_signatures(address: str, limit: int = 50):
    """Get recent transaction signatures for an address."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [address, {"limit": limit}]
    }
    try:
        resp = requests.post(RPC_URL, json=payload, timeout=15)
        if resp.ok:
            return resp.json().get("result", [])
    except Exception as e:
        print(f"Error: {e}")
    return []

def get_transaction(sig: str):
    """Get transaction details."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]
    }
    try:
        resp = requests.post(RPC_URL, json=payload, timeout=15)
        if resp.ok:
            return resp.json().get("result")
    except Exception as e:
        print(f"Error: {e}")
    return None

print(f"Checking transaction history for wallet #0: {SOURCE_WALLET}\n")
print("Fetching signatures...")

sigs = get_signatures(SOURCE_WALLET, limit=100)
print(f"Found {len(sigs)} transactions\n")

# Look for outbound transfers (where SOURCE_WALLET sent SOL)
outbound_transfers = []

print("Analyzing transactions...\n")
for i, sig_info in enumerate(sigs):
    sig = sig_info["signature"]
    
    tx = get_transaction(sig)
    if not tx:
        continue
    
    # Check for SOL transfers
    if "meta" in tx and "postBalances" in tx["meta"] and "preBalances" in tx["meta"]:
        pre = tx["meta"]["preBalances"]
        post = tx["meta"]["postBalances"]
        accounts = tx["transaction"]["message"]["accountKeys"]
        
        # Check if wallet #0 had a balance decrease (sent funds)
        for j, acct in enumerate(accounts):
            if isinstance(acct, dict):
                acct_pubkey = acct.get("pubkey")
            else:
                acct_pubkey = acct
                
            if acct_pubkey == SOURCE_WALLET:
                if j < len(pre) and j < len(post):
                    change = (post[j] - pre[j]) / 1_000_000_000
                    if change < -0.001:  # Significant outbound (ignoring fees)
                        # Find recipient (account with positive change)
                        for k, other_acct in enumerate(accounts):
                            if isinstance(other_acct, dict):
                                other_pubkey = other_acct.get("pubkey")
                            else:
                                other_pubkey = other_acct
                                
                            if k < len(pre) and k < len(post) and other_pubkey != SOURCE_WALLET:
                                other_change = (post[k] - pre[k]) / 1_000_000_000
                                if other_change > 0.001:
                                    outbound_transfers.append({
                                        "sig": sig[:16] + "...",
                                        "to": other_pubkey,
                                        "amount": abs(change),
                                        "block": sig_info.get("blockTime", 0)
                                    })
                                    print(f"TX {i+1}: Sent {abs(change):.6f} SOL to {other_pubkey}")
                                    break
                        break

if outbound_transfers:
    print(f"\n{'='*80}")
    print("OUTBOUND TRANSFERS FROM WALLET #0:")
    print(f"{'='*80}\n")
    for tx in outbound_transfers:
        print(f"Recipient: {tx['to']}")
        print(f"Amount:    {tx['amount']:.9f} SOL")
        print(f"TX:        {tx['sig']}")
        print()
else:
    print("\nNo significant outbound transfers found.")
    print("Wallets may have been swept from a different wallet or method.")
