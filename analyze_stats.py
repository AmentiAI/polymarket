#!/usr/bin/env python3
"""
Quick stats analyzer for snipe trades.
Usage: python analyze_stats.py
"""

import json
from datetime import datetime

def load_trades():
    try:
        with open('snipe_trades.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ No trades yet — run the bot first!")
        return []

def analyze():
    trades = load_trades()
    
    if not trades:
        return
    
    closed = [t for t in trades if t.get('status') == 'closed']
    wins = [t for t in closed if t.get('outcome') == 'WIN']
    losses = [t for t in closed if t.get('outcome') == 'LOSS']
    
    total_pnl = sum(t.get('pnl', 0) for t in closed)
    
    print("\n" + "="*70)
    print("  📊 SNIPER BOT PERFORMANCE")
    print("="*70)
    
    # Overall Stats
    print(f"\n📈 OVERALL:")
    print(f"  Total Trades: {len(closed)}")
    print(f"  Wins: {len(wins)} ({len(wins)/len(closed)*100:.1f}%)" if closed else "  No closed trades")
    print(f"  Losses: {len(losses)} ({len(losses)/len(closed)*100:.1f}%)" if closed else "")
    print(f"  P&L: ${total_pnl:+.2f}")
    print(f"  Avg P&L/Trade: ${total_pnl/len(closed):+.2f}" if closed else "")
    
    # By Type
    if closed:
        last_second = [t for t in closed if t.get('type') == 'LAST_SECOND']
        late = [t for t in closed if t.get('type') == 'LATE']
        
        print(f"\n🔥 LAST-SECOND SNIPES:")
        if last_second:
            ls_wins = sum(1 for t in last_second if t.get('outcome') == 'WIN')
            ls_pnl = sum(t.get('pnl', 0) for t in last_second)
            print(f"  Count: {len(last_second)}")
            print(f"  Win Rate: {ls_wins/len(last_second)*100:.1f}%")
            print(f"  P&L: ${ls_pnl:+.2f}")
        else:
            print(f"  No trades yet")
        
        print(f"\n💎 LATE SNIPES:")
        if late:
            late_wins = sum(1 for t in late if t.get('outcome') == 'WIN')
            late_pnl = sum(t.get('pnl', 0) for t in late)
            print(f"  Count: {len(late)}")
            print(f"  Win Rate: {late_wins/len(late)*100:.1f}%")
            print(f"  P&L: ${late_pnl:+.2f}")
        else:
            print(f"  No trades yet")
    
    # By Direction
    if closed:
        ups = [t for t in closed if t.get('direction') == 'UP']
        downs = [t for t in closed if t.get('direction') == 'DOWN']
        
        print(f"\n📊 BY DIRECTION:")
        if ups:
            up_wins = sum(1 for t in ups if t.get('outcome') == 'WIN')
            up_pnl = sum(t.get('pnl', 0) for t in ups)
            print(f"  UP: {len(ups)} trades | {up_wins/len(ups)*100:.1f}% WR | ${up_pnl:+.2f}")
        
        if downs:
            dn_wins = sum(1 for t in downs if t.get('outcome') == 'WIN')
            dn_pnl = sum(t.get('pnl', 0) for t in downs)
            print(f"  DOWN: {len(downs)} trades | {dn_wins/len(downs)*100:.1f}% WR | ${dn_pnl:+.2f}")
    
    # Recent Trades
    print(f"\n🕐 LAST 5 TRADES:")
    for t in reversed(closed[-5:]):
        outcome_icon = "✅" if t.get('outcome') == 'WIN' else "❌"
        ts = datetime.fromisoformat(t['timestamp'].replace('Z', '+00:00'))
        print(f"  {outcome_icon} {ts.strftime('%m/%d %H:%M')} | "
              f"{t.get('direction', '?'):>4} {t.get('type', '?'):>12} | "
              f"${t.get('pnl', 0):+6.2f} | "
              f"{t.get('confidence', 0):>4.1f}%")
    
    # Best/Worst
    if closed:
        best = max(closed, key=lambda t: t.get('pnl', -999))
        worst = min(closed, key=lambda t: t.get('pnl', 999))
        
        print(f"\n🏆 BEST TRADE: ${best.get('pnl', 0):+.2f} | "
              f"{best.get('direction', '?')} {best.get('type', '?')} | "
              f"{best.get('confidence', 0):.1f}% conf")
        
        print(f"💩 WORST TRADE: ${worst.get('pnl', 0):+.2f} | "
              f"{worst.get('direction', '?')} {worst.get('type', '?')} | "
              f"{worst.get('confidence', 0):.1f}% conf")
    
    # Confidence Analysis
    if closed:
        print(f"\n📊 BY CONFIDENCE:")
        
        high_conf = [t for t in closed if t.get('confidence', 0) >= 75]
        med_conf = [t for t in closed if 60 <= t.get('confidence', 0) < 75]
        low_conf = [t for t in closed if t.get('confidence', 0) < 60]
        
        for label, group in [("High (≥75%)", high_conf), 
                             ("Medium (60-75%)", med_conf), 
                             ("Low (<60%)", low_conf)]:
            if group:
                g_wins = sum(1 for t in group if t.get('outcome') == 'WIN')
                g_pnl = sum(t.get('pnl', 0) for t in group)
                print(f"  {label:>15}: {len(group):>2} trades | {g_wins/len(group)*100:>5.1f}% WR | ${g_pnl:+6.2f}")
    
    # Open Positions
    open_positions = [t for t in trades if t.get('status') == 'open']
    if open_positions:
        print(f"\n⏳ OPEN POSITIONS: {len(open_positions)}")
        for t in open_positions:
            print(f"  {t.get('direction', '?'):>4} {t.get('type', '?'):>12} | "
                  f"Entry: ${t.get('entry_cost', 0):.2f} @ ${t.get('entry_price', 0):.4f}")
    
    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    analyze()
