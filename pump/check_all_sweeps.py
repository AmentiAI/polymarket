#!/usr/bin/env python3
"""Check all 20 wallets for sweep transactions."""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

RPC_URL = os.getenv("SOLANA_RPC_URL")
WALLETS_PATH = "wallets.json"

def get_signatures(address: str, limit: int = 100):
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
        pass
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
        pass
    return None

with open(WALLETS_PATH) as f:
    wallets = json.load(f)["wallets"]

print("Checking all 20 wallets for sweep transactions...\n")

all_sweeps = []
total_swept = 0.0

for w in wallets:
    idx = w["index"]
    addr = w["address"]
    
    print(f"W{idx:02d}: {addr}...", end=" ", flush=True)
    
    sigs = get_signatures(addr, limit=100)
    
    # Find the largest outbound transfer (likely the sweep)
    largest_out = 0.0
    sweep_tx = None
    sweep_to = None
    
    for sig_info in sigs:
        sig = sig_info["signature"]
        tx = get_transaction(sig)
        
        if not tx:
            continue
        
        if "meta" in tx and "postBalances" in tx["meta"] and "preBalances" in tx["meta"]:
            pre = tx["meta"]["preBalances"]
            post = tx["meta"]["postBalances"]
            accounts = tx["transaction"]["message"]["accountKeys"]
            
            # Find this wallet's balance change
            for j, acct in enumerate(accounts):
                if isinstance(acct, dict):
                    acct_pubkey = acct.get("pubkey")
                else:
                    acct_pubkey = acct
                    
                if acct_pubkey == addr and j < len(pre) and j < len(post):
                    change = (post[j] - pre[j]) / 1_000_000_000
                    if change < largest_out:  # More negative = larger outbound
                        largest_out = change
                        sweep_tx = sig
                        
                        # Find recipient
                        for k, other_acct in enumerate(accounts):
                            if isinstance(other_acct, dict):
                                other_pubkey = other_acct.get("pubkey")
                            else:
                                other_pubkey = other_acct
                                
                            if k < len(pre) and k < len(post) and other_pubkey != addr:
                                other_change = (post[k] - pre[k]) / 1_000_000_000
                                if other_change > 0.001:
                                    sweep_to = other_pubkey
                                    break
                    break
    
    if largest_out < -0.001:
        amount = abs(largest_out)
        total_swept += amount
        all_sweeps.append({
            "wallet": f"W{idx:02d}",
            "address": addr,
            "amount": amount,
            "to": sweep_to,
            "tx": sweep_tx[:16] + "..." if sweep_tx else "N/A"
        })
        print(f"Swept {amount:.6f} SOL")
    else:
        print("No sweep found")

print(f"\n{'='*100}")
print("SWEEP SUMMARY:")
print(f"{'='*100}\n")

if all_sweeps:
    # Group by recipient
    by_recipient = {}
    for sweep in all_sweeps:
        recipient = sweep["to"] or "Unknown"
        if recipient not in by_recipient:
            by_recipient[recipient] = []
        by_recipient[recipient].append(sweep)
    
    for recipient, sweeps in by_recipient.items():
        recipient_total = sum(s["amount"] for s in sweeps)
        print(f"\nRecipient: {recipient}")
        print(f"Total received: {recipient_total:.9f} SOL from {len(sweeps)} wallets")
        print(f"\nDetails:")
        for s in sweeps:
            print(f"  {s['wallet']}: {s['amount']:.9f} SOL - TX: {s['tx']}")
    
    print(f"\n{'='*100}")
    print(f"GRAND TOTAL SWEPT: {total_swept:.9f} SOL from {len(all_sweeps)} wallets")
    print(f"{'='*100}")
else:
    print("No sweep transactions found.")
