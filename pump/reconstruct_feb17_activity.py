#!/usr/bin/env python3
"""Reconstruct what happened on February 17 by analyzing all transactions."""
import os, json, requests
from dotenv import load_dotenv
import datetime

load_dotenv()

RPC_URL = os.getenv('SOLANA_RPC_URL')
TOKEN_MINT = '7JVEqoq1uZkGHa2DuVMsc22TyiDNZyCoGkkS3RXXpump'

with open('wallets.json') as f:
    wallets = json.load(f)['wallets']

def get_signatures(address: str, limit: int = 1000):
    """Get all transaction signatures."""
    payload = {
        'jsonrpc': '2.0', 'id': 1,
        'method': 'getSignaturesForAddress',
        'params': [address, {'limit': limit}]
    }
    try:
        resp = requests.post(RPC_URL, json=payload, timeout=20)
        if resp.ok:
            return resp.json().get('result', [])
    except Exception:
        pass
    return []

def get_transaction(sig: str):
    """Get transaction details."""
    payload = {
        'jsonrpc': '2.0', 'id': 1,
        'method': 'getTransaction',
        'params': [sig, {'encoding': 'jsonParsed', 'maxSupportedTransactionVersion': 0}]
    }
    try:
        resp = requests.post(RPC_URL, json=payload, timeout=20)
        if resp.ok:
            return resp.json().get('result')
    except Exception:
        pass
    return None

print("="*100)
print("RECONSTRUCTING FEBRUARY 17, 2026 PUMP BOT ACTIVITY")
print("="*100)

# Check all 6 wallets that have tokens
token_holders = [0, 1, 2, 3, 4, 5]

all_activity = []

for idx in token_holders:
    w = wallets[idx]
    addr = w['address']
    
    print(f"\n{'='*100}")
    print(f"WALLET W{idx:02d}: {addr}")
    print(f"{'='*100}")
    
    sigs = get_signatures(addr, limit=100)
    print(f"Found {len(sigs)} total transactions\n")
    
    if not sigs:
        print("  No transactions found")
        continue
    
    # Get first and last transaction times
    first_time = sigs[-1].get('blockTime', 0)
    last_time = sigs[0].get('blockTime', 0)
    
    first_dt = datetime.datetime.fromtimestamp(first_time)
    last_dt = datetime.datetime.fromtimestamp(last_time)
    
    print(f"Activity Timeline:")
    print(f"  First TX: {first_dt} ({first_time})")
    print(f"  Last TX:  {last_dt} ({last_time})")
    print(f"  Duration: {(last_time - first_time) / 60:.1f} minutes\n")
    
    # Analyze each transaction
    for i, sig_info in enumerate(sigs):
        sig = sig_info['signature']
        block_time = sig_info.get('blockTime', 0)
        dt = datetime.datetime.fromtimestamp(block_time)
        
        tx = get_transaction(sig)
        if not tx:
            continue
        
        # Analyze transaction
        try:
            pre_balances = tx['meta']['preBalances']
            post_balances = tx['meta']['postBalances']
            accounts = tx['transaction']['message']['accountKeys']
            
            # Find wallet's balance change
            for j, acct in enumerate(accounts):
                if isinstance(acct, dict):
                    acct_pubkey = acct.get('pubkey')
                else:
                    acct_pubkey = acct
                
                if acct_pubkey == addr and j < len(pre_balances) and j < len(post_balances):
                    sol_change = (post_balances[j] - pre_balances[j]) / 1_000_000_000
                    
                    # Check if token involved
                    token_involved = False
                    token_change = 0
                    
                    if 'postTokenBalances' in tx['meta']:
                        for tb in tx['meta']['postTokenBalances']:
                            if tb.get('mint') == TOKEN_MINT:
                                token_involved = True
                                # Try to get token change
                                pre_token = 0
                                for ptb in tx['meta'].get('preTokenBalances', []):
                                    if ptb.get('mint') == TOKEN_MINT:
                                        pre_token = float(ptb.get('uiTokenAmount', {}).get('uiAmountString', 0))
                                post_token = float(tb.get('uiTokenAmount', {}).get('uiAmountString', 0))
                                token_change = post_token - pre_token
                    
                    # Classify transaction
                    tx_type = "UNKNOWN"
                    details = ""
                    
                    if token_involved and sol_change < -0.001 and token_change > 0:
                        tx_type = "BUY"
                        details = f"Spent {abs(sol_change):.6f} SOL → Got {token_change:,.0f} tokens"
                    elif token_involved and sol_change > 0.001 and token_change < 0:
                        tx_type = "SELL"
                        details = f"Sold {abs(token_change):,.0f} tokens → Got {sol_change:.6f} SOL"
                    elif sol_change > 0.001 and not token_involved:
                        tx_type = "RECEIVE SOL"
                        details = f"Received {sol_change:.6f} SOL"
                    elif sol_change < -0.001 and not token_involved:
                        tx_type = "SEND SOL"
                        details = f"Sent {abs(sol_change):.6f} SOL"
                    elif token_involved and abs(sol_change) < 0.001:
                        if token_change > 0:
                            tx_type = "RECEIVE TOKENS"
                            details = f"Received {token_change:,.0f} tokens (airdrop/transfer)"
                        elif token_change < 0:
                            tx_type = "SEND TOKENS"
                            details = f"Sent {abs(token_change):,.0f} tokens"
                    else:
                        tx_type = "OTHER"
                        details = f"SOL: {sol_change:+.6f}"
                    
                    all_activity.append({
                        'wallet': f'W{idx:02d}',
                        'time': block_time,
                        'dt': dt,
                        'type': tx_type,
                        'details': details,
                        'sig': sig[:16] + '...'
                    })
                    
                    print(f"{dt.strftime('%H:%M:%S')} | {tx_type:15s} | {details} | {sig[:16]}...")
                    
                    break
        except Exception as e:
            continue

print(f"\n{'='*100}")
print("CHRONOLOGICAL TIMELINE OF ALL ACTIVITY")
print(f"{'='*100}\n")

all_activity.sort(key=lambda x: x['time'])

for activity in all_activity:
    print(f"{activity['dt'].strftime('%Y-%m-%d %H:%M:%S')} | {activity['wallet']} | {activity['type']:15s} | {activity['details']}")

print(f"\n{'='*100}")
print("SUMMARY")
print(f"{'='*100}")
print(f"Total transactions analyzed: {len(all_activity)}")
print(f"Wallets with activity: {len(set(a['wallet'] for a in all_activity))}")
print(f"Transaction types: {set(a['type'] for a in all_activity)}")
