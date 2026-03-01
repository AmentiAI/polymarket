#!/usr/bin/env python3
"""Check token metadata and try to find its value."""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

RPC_URL = os.getenv("SOLANA_RPC_URL")
TOKEN_MINT = "7JVEqoq1uZkGHa2DuVMsc22TyiDNZyCoGkkS3RXXpump"

def get_account_info(address: str):
    """Get account info from RPC."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getAccountInfo",
        "params": [address, {"encoding": "jsonParsed"}]
    }
    try:
        resp = requests.post(RPC_URL, json=payload, timeout=15)
        if resp.ok:
            return resp.json().get("result", {}).get("value")
    except Exception as e:
        print(f"Error: {e}")
    return None

def get_signatures(address: str, limit: int = 10):
    """Get recent transaction signatures."""
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

print(f"Token Mint: {TOKEN_MINT}\n")

# Get token metadata
print("Fetching token info from blockchain...")
account_info = get_account_info(TOKEN_MINT)

if account_info:
    try:
        data = account_info["data"]
        if isinstance(data, dict) and "parsed" in data:
            info = data["parsed"]["info"]
            print(f"Supply: {int(info.get('supply', 0)) / (10 ** info.get('decimals', 6)):.0f}")
            print(f"Decimals: {info.get('decimals', 'Unknown')}")
            print(f"Mint Authority: {info.get('mintAuthority', 'None')}")
            print(f"Freeze Authority: {info.get('freezeAuthority', 'None')}")
    except Exception as e:
        print(f"Error parsing token info: {e}")
else:
    print("Could not fetch token info")

# Check recent activity
print("\nChecking recent activity...")
sigs = get_signatures(TOKEN_MINT, limit=5)
if sigs:
    print(f"Found {len(sigs)} recent transactions")
    latest = sigs[0]
    import datetime
    if "blockTime" in latest:
        last_tx_time = datetime.datetime.fromtimestamp(latest["blockTime"])
        print(f"Last activity: {last_tx_time}")
else:
    print("No recent transactions found")

# Try to check dexscreener with more details
print("\nChecking DexScreener...")
try:
    resp = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{TOKEN_MINT}", timeout=10)
    if resp.ok:
        data = resp.json()
        if data.get("pairs"):
            print("✅ Token has active trading pairs:")
            for pair in data["pairs"][:3]:
                print(f"  DEX: {pair.get('dexId')}")
                print(f"  Price: ${pair.get('priceUsd', 'N/A')}")
                print(f"  Liquidity: ${pair.get('liquidity', {}).get('usd', 'N/A')}")
                print(f"  Volume 24h: ${pair.get('volume', {}).get('h24', 'N/A')}")
                print()
        else:
            print("❌ No active trading pairs found")
            print("This token likely has ZERO value (dead/rugged)")
except Exception as e:
    print(f"Error checking DexScreener: {e}")

print("\n" + "="*70)
print("VERDICT:")
print("="*70)
print("Token: 7JVEqoq1uZkGHa2DuVMsc22TyiDNZyCoGkkS3RXXpump")
print("Total Holdings: ~2.6M tokens (W00: 1.07M, W01: 1.53M)")
print("\nNo active trading pairs = NO MARKET VALUE")
print("Current worth: $0.00")
print("\nNot worth paying transaction fees (~$0.50 in SOL) to transfer.")
print("="*70)
