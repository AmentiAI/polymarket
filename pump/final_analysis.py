#!/usr/bin/env python3
"""Simple check: look at ALL transactions and find ANY that mention pump or have SOL outflows."""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

RPC_URL = os.getenv("SOLANA_RPC_URL")

WALLETS = {
    "W00": "3QHkG2h84pyyqgTyYTu6y3ckZi5ynpxbSqKEV5poLaZ6",
    "W01": "EHcUL53zmYExkZfLjSseQftokCYQ8c8ZjScqQqJ9uYsn"
}

def get_signatures(address: str):
    """Get ALL transaction signatures."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [address, {"limit": 1000}]
    }
    try:
        resp = requests.post(RPC_URL, json=payload, timeout=15)
        if resp.ok:
            return resp.json().get("result", [])
    except Exception:
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
    except Exception:
        pass
    return None

print("="*80)
print("FINAL LOSS ANALYSIS")
print("="*80)

total_sol_lost = 0

for wallet_name, wallet_addr in WALLETS.items():
    print(f"\n{wallet_name}: {wallet_addr}")
    
    sigs = get_signatures(wallet_addr)
    print(f"Total transactions: {len(sigs)}")
    
    # Check first and last transaction
    if sigs:
        first_time = sigs[-1].get("blockTime", 0)
        last_time = sigs[0].get("blockTime", 0)
        
        import datetime
        print(f"First TX: {datetime.datetime.fromtimestamp(first_time)}")
        print(f"Last TX: {datetime.datetime.fromtimestamp(last_time)}")
    
    # Look for significant SOL outflows (buys)
    sol_out = 0
    sol_in = 0
    
    for i, sig_info in enumerate(sigs):
        sig = sig_info["signature"]
        tx = get_transaction(sig)
        
        if not tx:
            continue
        
        try:
            pre_balances = tx["meta"]["preBalances"]
            post_balances = tx["meta"]["postBalances"]
            accounts = tx["transaction"]["message"]["accountKeys"]
            
            for j, acct in enumerate(accounts):
                if isinstance(acct, dict):
                    acct_pubkey = acct.get("pubkey")
                else:
                    acct_pubkey = acct
                
                if acct_pubkey == wallet_addr and j < len(pre_balances) and j < len(post_balances):
                    change = (post_balances[j] - pre_balances[j]) / 1_000_000_000
                    
                    if change < -0.001:  # Outflow
                        sol_out += abs(change)
                    elif change > 0.001:  # Inflow
                        sol_in += change
                    break
        except Exception:
            continue
    
    print(f"\nSOL Flows:")
    print(f"  Total OUT: {sol_out:.6f} SOL")
    print(f"  Total IN:  {sol_in:.6f} SOL")
    print(f"  Net:       {sol_in - sol_out:.6f} SOL")
    
    total_sol_lost += (sol_out - sol_in)

print("\n" + "="*80)
print("CONCLUSION:")
print("="*80)
print(f"\nTotal SOL OUT (both wallets): {total_sol_lost:.6f} SOL")
print(f"Current Token Value: $0.00")
print(f"SOL Recovered (sweep): 0.1525 SOL")
print(f"\nIf the token was purchased:")
print(f"  Loss = {total_sol_lost:.6f} SOL")
print(f"  At $200/SOL = ${total_sol_lost * 200:.2f}")
print(f"\nBUT: Token may have been airdropped/transferred for free")
print(f"The 0.15 SOL swept was likely just unused trading capital,")
print(f"not recovered from the token.")
print("="*80)
