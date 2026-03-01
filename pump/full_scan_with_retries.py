#!/usr/bin/env python3
"""Complete scan of all 20 wallets with retries for reliability."""
import os, json, requests, time
from dotenv import load_dotenv

load_dotenv()

RPC_URL = os.getenv('SOLANA_RPC_URL')
TOKEN_MINT = '7JVEqoq1uZkGHa2DuVMsc22TyiDNZyCoGkkS3RXXpump'

with open('wallets.json') as f:
    wallets = json.load(f)['wallets']

def check_wallet(addr, max_retries=3):
    """Check a wallet with retries."""
    for attempt in range(max_retries):
        try:
            token_payload = {
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'getTokenAccountsByOwner',
                'params': [
                    addr,
                    {'mint': TOKEN_MINT},
                    {'encoding': 'jsonParsed'}
                ]
            }
            
            resp = requests.post(RPC_URL, json=token_payload, timeout=20)
            if resp.ok:
                accounts = resp.json().get('result', {}).get('value', [])
                if accounts:
                    info = accounts[0]['account']['data']['parsed']['info']
                    balance = float(info['tokenAmount']['uiAmountString'])
                    return balance
                return 0.0
            
            time.sleep(1)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                print(f"  Failed after {max_retries} attempts: {str(e)[:40]}")
                return None
    return None

print("="*100)
print("COMPLETE SCAN OF ALL 20 WALLETS")
print("="*100)
print(f"Token: {TOKEN_MINT}")
print(f"Scanning with 3 retries per wallet...\n")

results = []

for w in wallets:
    idx = w['index']
    addr = w['address']
    
    print(f"W{idx:02d}: Checking...", end=" ", flush=True)
    
    balance = check_wallet(addr, max_retries=3)
    
    if balance is None:
        print("❌ ERROR - Could not fetch")
    elif balance > 0:
        results.append({
            'idx': idx,
            'addr': addr,
            'wif': w['wif'],
            'balance': balance
        })
        print(f"✓ {balance:,.2f} tokens")
    else:
        print("No tokens")
    
    time.sleep(0.3)  # Small delay between wallets

print(f"\n{'='*100}")
print("COMPLETE RESULTS:")
print(f"{'='*100}\n")

if results:
    total = sum(r['balance'] for r in results)
    
    print(f"Found {len(results)} wallets with {total:,.2f} tokens total\n")
    print(f"{'='*100}")
    
    for r in sorted(results, key=lambda x: x['balance'], reverse=True):
        pct = (r['balance'] / total) * 100
        print(f"\nW{r['idx']:02d} ({pct:.2f}% of total)")
        print(f"Address: {r['addr']}")
        print(f"Private Key: {r['wif']}")
        print(f"Balance: {r['balance']:,.2f} tokens")
    
    print(f"\n{'='*100}")
    print(f"TOTAL HOLDINGS: {total:,.2f} tokens across {len(results)} wallets")
    print(f"{'='*100}")
else:
    print("No wallets with tokens found")
