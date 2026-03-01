#!/usr/bin/env python3
"""Calculate how much SOL was spent buying the worthless token."""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

RPC_URL = os.getenv("SOLANA_RPC_URL")
TOKEN_MINT = "7JVEqoq1uZkGHa2DuVMsc22TyiDNZyCoGkkS3RXXpump"
WALLETS_PATH = "wallets.json"

# Wallets that hold the token
TOKEN_HOLDERS = ["3QHkG2h84pyyqgTyYTu6y3ckZi5ynpxbSqKEV5poLaZ6", "EHcUL53zmYExkZfLjSseQftokCYQ8c8ZjScqQqJ9uYsn"]

def get_signatures(address: str, limit: int = 200):
    """Get transaction signatures for an address."""
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

print(f"Analyzing losses for token: {TOKEN_MINT}\n")
print("="*80)

total_spent = 0.0
all_buys = []

for wallet_addr in TOKEN_HOLDERS:
    wallet_name = "W00" if wallet_addr.startswith("3QH") else "W01"
    print(f"\n{wallet_name}: {wallet_addr}")
    print(f"Fetching transactions...")
    
    sigs = get_signatures(wallet_addr, limit=200)
    print(f"Found {len(sigs)} total transactions. Analyzing...")
    
    buys_count = 0
    wallet_total = 0.0
    
    for i, sig_info in enumerate(sigs):
        sig = sig_info["signature"]
        tx = get_transaction(sig)
        
        if not tx:
            continue
        
        # Check if this transaction involves our token
        involves_token = False
        try:
            if "meta" in tx and "postTokenBalances" in tx["meta"]:
                for balance in tx["meta"]["postTokenBalances"]:
                    if balance.get("mint") == TOKEN_MINT:
                        involves_token = True
                        break
        except Exception:
            pass
        
        if not involves_token:
            continue
        
        # Calculate SOL spent (balance decrease)
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
                    sol_change = (post_balances[j] - pre_balances[j]) / 1_000_000_000
                    
                    # If balance decreased significantly (more than just fees), it's a buy
                    if sol_change < -0.001:
                        amount_spent = abs(sol_change)
                        wallet_total += amount_spent
                        buys_count += 1
                        all_buys.append({
                            "wallet": wallet_name,
                            "amount": amount_spent,
                            "tx": sig[:16] + "..."
                        })
                        print(f"  Buy #{buys_count}: {amount_spent:.6f} SOL - TX: {sig[:16]}...")
                    break
        except Exception as e:
            continue
    
    print(f"\n  {wallet_name} Total Spent: {wallet_total:.6f} SOL ({buys_count} buy transactions)")
    total_spent += wallet_total

print("\n" + "="*80)
print("LOSS CALCULATION:")
print("="*80)
print(f"\nTotal SOL Spent Buying Token: {total_spent:.6f} SOL")
print(f"Current Token Value: $0.00")
print(f"SOL Recovered (sweep): 0.1525 SOL")
print(f"\nNet Loss: {total_spent - 0.1525:.6f} SOL")
print(f"\nAt current SOL price (~$200):")
print(f"  Spent: ${total_spent * 200:.2f}")
print(f"  Recovered: ${0.1525 * 200:.2f}")
print(f"  NET LOSS: ${(total_spent - 0.1525) * 200:.2f}")
print("="*80)

if all_buys:
    print(f"\nDetailed Buy History ({len(all_buys)} transactions):")
    for buy in all_buys:
        print(f"  {buy['wallet']}: {buy['amount']:.6f} SOL - {buy['tx']}")
