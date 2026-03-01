#!/usr/bin/env python3
"""Check ALL 20 wallets carefully for the specific token."""
import os, json, requests, time
from dotenv import load_dotenv

load_dotenv()

RPC_URL = os.getenv('SOLANA_RPC_URL')
TOKEN_MINT = '7JVEqoq1uZkGHa2DuVMsc22TyiDNZyCoGkkS3RXXpump'

with open('wallets.json') as f:
    wallets = json.load(f)['wallets']

results = []

print("Checking all 20 wallets for token holdings...")
print(f"Token: {TOKEN_MINT}\n")

for w in wallets:
    idx = w['index']
    addr = w['address']
    
    # Check specifically for THIS token mint
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
    
    try:
        resp = requests.post(RPC_URL, json=token_payload, timeout=15)
        if resp.ok:
            data = resp.json()
            accounts = data.get('result', {}).get('value', [])
            
            if accounts:
                info = accounts[0]['account']['data']['parsed']['info']
                balance = float(info['tokenAmount']['uiAmountString'])
                
                if balance > 0:
                    results.append({
                        'idx': idx,
                        'addr': addr,
                        'wif': w['wif'],
                        'balance': balance
                    })
                    print(f"W{idx:02d}: {balance:,.2f} tokens ✓")
                else:
                    print(f"W{idx:02d}: Token account exists but empty")
            else:
                print(f"W{idx:02d}: No tokens")
        else:
            print(f"W{idx:02d}: RPC error")
        
        time.sleep(0.2)  # Rate limiting
        
    except Exception as e:
        print(f"W{idx:02d}: Exception - {e}")
        time.sleep(0.2)

print(f"\n{'='*100}")
print(f"COMPLETE RESULTS:")
print(f"{'='*100}\n")

if results:
    total = sum(r['balance'] for r in results)
    
    print(f"{len(results)} wallets hold {total:,.2f} tokens total\n")
    
    for r in sorted(results, key=lambda x: x['balance'], reverse=True):
        pct = (r['balance'] / total) * 100
        print(f"W{r['idx']:02d} ({pct:.2f}% of total)")
        print(f"  Address: {r['addr']}")
        print(f"  Private Key: {r['wif']}")
        print(f"  Balance: {r['balance']:,.2f} tokens\n")
else:
    print("No wallets have this token")
