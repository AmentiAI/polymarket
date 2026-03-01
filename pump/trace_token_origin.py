#!/usr/bin/env python3
"""Find out how these wallets got the tokens - was it bought, airdropped, or transferred?"""
import os
import json
import requests
from dotenv import load_dotenv
import datetime

load_dotenv()

RPC_URL = os.getenv("SOLANA_RPC_URL")
TOKEN_MINT = "7JVEqoq1uZkGHa2DuVMsc22TyiDNZyCoGkkS3RXXpump"

# Wallets that hold the token
WALLETS = {
    "W00": "3QHkG2h84pyyqgTyYTu6y3ckZi5ynpxbSqKEV5poLaZ6",
    "W01": "EHcUL53zmYExkZfLjSseQftokCYQ8c8ZjScqQqJ9uYsn"
}

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

print(f"Tracing origin of token: {TOKEN_MINT}\n")
print("="*80)

for wallet_name, wallet_addr in WALLETS.items():
    print(f"\n{wallet_name}: {wallet_addr}")
    print(f"Fetching all transactions...")
    
    sigs = get_signatures(wallet_addr, limit=200)
    print(f"Found {len(sigs)} transactions. Looking for first token appearance...\n")
    
    # Reverse to check oldest first
    sigs_reversed = list(reversed(sigs))
    
    first_token_tx = None
    
    for sig_info in sigs_reversed:
        sig = sig_info["signature"]
        tx = get_transaction(sig)
        
        if not tx:
            continue
        
        # Check if token appeared in this transaction
        try:
            pre_token_balances = tx["meta"].get("preTokenBalances", [])
            post_token_balances = tx["meta"].get("postTokenBalances", [])
            
            # Find if our token appeared (wasn't there before, is there after)
            had_token_before = False
            has_token_after = False
            token_amount = 0
            
            for balance in pre_token_balances:
                if balance.get("mint") == TOKEN_MINT:
                    had_token_before = True
                    break
            
            for balance in post_token_balances:
                if balance.get("mint") == TOKEN_MINT:
                    has_token_after = True
                    token_amount = float(balance.get("uiTokenAmount", {}).get("uiAmountString", 0))
                    break
            
            # First appearance = when it goes from not having to having the token
            if not had_token_before and has_token_after:
                first_token_tx = {
                    "sig": sig,
                    "amount": token_amount,
                    "time": sig_info.get("blockTime", 0)
                }
                break
        except Exception:
            continue
    
    if first_token_tx:
        dt = datetime.datetime.fromtimestamp(first_token_tx["time"])
        print(f"✅ FIRST TOKEN APPEARANCE:")
        print(f"   Date: {dt}")
        print(f"   Amount: {first_token_tx['amount']:,.2f} tokens")
        print(f"   TX: {first_token_tx['sig']}")
        
        # Now analyze that specific transaction
        print(f"\n   Analyzing transaction details...")
        tx = get_transaction(first_token_tx["sig"])
        
        if tx:
            # Check balance changes
            pre_balances = tx["meta"]["preBalances"]
            post_balances = tx["meta"]["postBalances"]
            accounts = tx["transaction"]["message"]["accountKeys"]
            
            sol_spent = 0
            for j, acct in enumerate(accounts):
                if isinstance(acct, dict):
                    acct_pubkey = acct.get("pubkey")
                else:
                    acct_pubkey = acct
                
                if acct_pubkey == wallet_addr and j < len(pre_balances) and j < len(post_balances):
                    sol_change = (post_balances[j] - pre_balances[j]) / 1_000_000_000
                    sol_spent = abs(sol_change) if sol_change < 0 else 0
                    break
            
            if sol_spent > 0.001:
                print(f"   Type: BUY (spent {sol_spent:.6f} SOL)")
                print(f"   Price per token: ${sol_spent * 200 / first_token_tx['amount']:.8f}")
            else:
                print(f"   Type: AIRDROP or TRANSFER (no SOL spent)")
    else:
        print(f"❌ Could not trace token origin (may need more transaction history)")

print("\n" + "="*80)
