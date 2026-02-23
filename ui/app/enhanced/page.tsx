'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { createChart, type IChartApi, type ISeriesApi, type SeriesMarker, type CandlestickData, type Time } from 'lightweight-charts';

// ── Types ────────────────────────────────────────────────────────────
interface Trade {
  trade_id: string;
  timestamp: string;
  candle_timestamp: number;
  direction: 'UP' | 'DOWN';
  type: 'LAST_SECOND' | 'LATE';
  reason: string;
  confidence: number;
  entry_price: number;
  entry_cost: number;
  shares: number;
  status: 'open' | 'closed' | 'holding';
  outcome?: 'WIN' | 'LOSS';
  pnl?: number;
  exit_price?: number;
  metrics: {
    body_pct: number;
    body_usd: number;
    volatility: number;
  };
}

interface BotState {
  running: boolean;
  btc_price: number;
  secs_left: number;
  current_candle: {
    open: number;
    high: number;
    low: number;
    close: number;
    body_pct: number;
    body_usd: number;
    volatility: number;
    direction: 'GREEN' | 'RED';
  } | null;
  current_market: {
    timestamp: number;
    up_price: number;
    down_price: number;
    accepting_orders: boolean;
    market_slug: string;
  } | null;
  last_signal: {
    action: 'SNIPE' | 'WAIT';
    direction?: 'UP' | 'DOWN';
    reason: string;
    confidence?: number;
    type?: 'LAST_SECOND' | 'LATE';
    metrics?: {
      body_pct: number;
      body_usd: number;
      volatility: number;
    };
  } | null;
  stats: {
    total: number;
    wins: number;
    losses: number;
    win_rate: number;
    pnl: number;
    avg_pnl: number;
    last_second_stats: {
      total: number;
      wins: number;
      win_rate: number;
    };
    late_stats: {
      total: number;
      wins: number;
      win_rate: number;
    };
  };
  recent_trades: Trade[];
  candles: {
    time: number;
    open: number;
    high: number;
    low: number;
    close: number;
  }[];
  trade_markers: {
    time: number;
    direction: 'UP' | 'DOWN';
    outcome: 'WIN' | 'LOSS';
    confidence: number;
  }[];
}

// ── Helpers ──────────────────────────────────────────────────────────
const fmtPrice = (n: number) => n?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? '--';
const fmtTimer = (secs: number) => `${Math.floor(secs / 60)}:${(secs % 60).toString().padStart(2, '0')}`;
const pnlColor = (n: number) => n > 0 ? 'text-green-400' : n < 0 ? 'text-red-400' : 'text-gray-400';

// ── Demo Data Generator ──────────────────────────────────────────────
function generateDemoState(): BotState {
  const now = Math.floor(Date.now() / 1000);
  const candle5minStart = Math.floor(now / 300) * 300;
  const secsLeft = (candle5minStart + 300) - now;
  
  const open = 95000 + Math.random() * 1000;
  const close = open + (Math.random() - 0.5) * 150;
  const high = Math.max(open, close) + Math.random() * 50;
  const low = Math.min(open, close) - Math.random() * 50;
  const body = Math.abs(close - open);
  const range = high - low;
  const body_pct = range > 0 ? (body / range) * 100 : 0;
  const volatility = (range / open) * 100;
  
  const isSnipeWindow = (secsLeft >= 10 && secsLeft <= 20) || (secsLeft >= 60 && secsLeft <= 120);
  const meetsThreshold = body_pct > 40 && body > 50;
  const shouldSnipe = isSnipeWindow && meetsThreshold && Math.random() > 0.3;
  
  return {
    running: true,
    btc_price: close,
    secs_left: secsLeft,
    current_candle: {
      open,
      high,
      low,
      close,
      body_pct,
      body_usd: body,
      volatility,
      direction: close >= open ? 'GREEN' : 'RED',
    },
    current_market: {
      timestamp: candle5minStart + 300,
      up_price: 0.50 + Math.random() * 0.25,
      down_price: 0.50 - Math.random() * 0.25,
      accepting_orders: true,
      market_slug: `btc-updown-5m-${candle5minStart + 300}`,
    },
    last_signal: shouldSnipe ? {
      action: 'SNIPE',
      direction: close >= open ? 'UP' : 'DOWN',
      reason: secsLeft <= 20 ? `LAST-SECOND: Strong ${close >= open ? 'UP' : 'DOWN'} body ${body_pct.toFixed(1)}% ($${body.toFixed(0)})` : `LATE: Clean continuation (body $${body.toFixed(0)}, vol ${volatility.toFixed(2)}%)`,
      confidence: 65 + Math.random() * 20,
      type: secsLeft <= 20 ? 'LAST_SECOND' : 'LATE',
      metrics: { body_pct, body_usd: body, volatility },
    } : {
      action: 'WAIT',
      reason: `No snipe window (secs_left=${secsLeft}, body_pct=${body_pct.toFixed(1)}%)`,
    },
    stats: {
      total: 24,
      wins: 17,
      losses: 7,
      win_rate: 70.8,
      pnl: 34.20,
      avg_pnl: 1.43,
      last_second_stats: { total: 10, wins: 8, win_rate: 80.0 },
      late_stats: { total: 14, wins: 9, win_rate: 64.3 },
    },
    recent_trades: [],
    candles: [],
    trade_markers: [],
  };
}

// ── Page ─────────────────────────────────────────────────────────────
export default function EnhancedSniperUI() {
  const [state, setState] = useState<BotState | null>(null);
  const [connected, setConnected] = useState(false);
  const [demoMode] = useState(true);
  
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartApiRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const chartInitialized = useRef(false);

  const initChart = useCallback(() => {
    if (chartInitialized.current || !chartContainerRef.current) return;
    
    const chart = createChart(chartContainerRef.current, {
      layout: { background: { color: '#0a0a14' }, textColor: '#9ca3af' },
      grid: { vertLines: { color: '#1a1a2e' }, horzLines: { color: '#1a1a2e' } },
      crosshair: { mode: 0 as const },
      rightPriceScale: { borderColor: '#2a2a3e' },
      timeScale: { borderColor: '#2a2a3e', timeVisible: true, secondsVisible: false },
      autoSize: true,
    });
    
    chartApiRef.current = chart;
    
    const series = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderUpColor: '#26a69a',
      borderDownColor: '#ef5350',
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
    });
    
    candleSeriesRef.current = series;
    chartInitialized.current = true;
  }, []);

  const updateChart = useCallback((candles: BotState['candles'], markers: BotState['trade_markers']) => {
    if (!candleSeriesRef.current || !candles.length) return;
    
    const chartData = candles.map(c => ({
      time: c.time as Time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));
    
    candleSeriesRef.current.setData(chartData);
    
    // Add trade markers
    if (markers.length > 0) {
      const seriesMarkers: SeriesMarker<Time>[] = markers.map(m => ({
        time: m.time as Time,
        position: m.direction === 'UP' ? 'belowBar' : 'aboveBar',
        color: m.outcome === 'WIN' ? '#00ff88' : '#ff4444',
        shape: 'circle',
        text: `${m.outcome === 'WIN' ? '✓' : '✗'} ${m.direction} ${m.confidence.toFixed(0)}%`,
      }));
      
      candleSeriesRef.current.setMarkers(seriesMarkers);
    }
  }, []);

  useEffect(() => {
    if (!demoMode) return;
    
    initChart();
    
    const interval = setInterval(() => {
      const newState = generateDemoState();
      setState(newState);
      updateChart(newState.candles, newState.trade_markers);
    }, 1000);
    
    setConnected(true);
    
    return () => clearInterval(interval);
  }, [demoMode, initChart, updateChart]);

  const s = state;
  const candle = s?.current_candle;
  const market = s?.current_market;
  const signal = s?.last_signal;
  const stats = s?.stats;
  
  const secsLeft = s?.secs_left ?? 300;
  const timerColor = secsLeft <= 30 ? 'text-red-400' : secsLeft <= 60 ? 'text-yellow-400' : 'text-white';

  return (
    <div className="h-screen overflow-hidden bg-[#0a0a14] text-gray-200 font-mono flex flex-col">
      {/* ═══ HEADER ═══ */}
      <div className="flex-none border-b border-[#1a1a2e] px-4 py-3 flex items-center gap-6">
        <div className="text-2xl font-black text-white flex items-center gap-2">
          🎯 <span className="text-yellow-400">SNIPER</span>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="text-sm text-gray-500">BTC</div>
          <div className="text-2xl font-bold text-white">
            ${candle ? fmtPrice(candle.close) : '--'}
          </div>
        </div>

        {/* Countdown - LARGE */}
        <div className="flex items-center gap-2">
          <div className="text-xs text-gray-500 uppercase">Next Close</div>
          <div className={`text-4xl font-black ${timerColor} tabular-nums tracking-wider`}>
            {s ? fmtTimer(secsLeft) : '--:--'}
          </div>
        </div>

        {/* Live signal badge - PROMINENT */}
        {signal?.action === 'SNIPE' && (
          <div className={`px-4 py-2 rounded-lg font-bold text-base border-2 animate-pulse ${
            signal.direction === 'UP'
              ? 'bg-green-500/20 border-green-500 text-green-400'
              : 'bg-red-500/20 border-red-500 text-red-400'
          }`}>
            <div className="flex items-center gap-2">
              <span className="text-2xl">{signal.direction === 'UP' ? '▲' : '▼'}</span>
              <div>
                <div className="text-sm">{signal.type}</div>
                <div className="text-xs opacity-80">{signal.confidence?.toFixed(0)}% conf</div>
              </div>
            </div>
          </div>
        )}

        <div className="ml-auto flex items-center gap-4">
          {/* Stats badge */}
          {stats && (
            <div className="flex items-center gap-3 px-4 py-2 rounded bg-[#111] border border-[#1a1a2e]">
              <div className="text-center">
                <div className="text-[10px] text-gray-500 uppercase">Record</div>
                <div className="text-base font-bold">
                  <span className="text-green-400">{stats.wins}</span>
                  <span className="text-gray-600">-</span>
                  <span className="text-red-400">{stats.losses}</span>
                </div>
              </div>
              <div className="w-px h-8 bg-[#1a1a2e]" />
              <div className="text-center">
                <div className="text-[10px] text-gray-500 uppercase">Win Rate</div>
                <div className={`text-base font-bold ${stats.win_rate >= 70 ? 'text-green-400' : stats.win_rate >= 60 ? 'text-yellow-400' : 'text-red-400'}`}>
                  {stats.win_rate.toFixed(1)}%
                </div>
              </div>
              <div className="w-px h-8 bg-[#1a1a2e]" />
              <div className="text-center">
                <div className="text-[10px] text-gray-500 uppercase">P&L</div>
                <div className={`text-base font-bold ${pnlColor(stats.pnl)}`}>
                  ${stats.pnl >= 0 ? '+' : ''}{stats.pnl.toFixed(2)}
                </div>
              </div>
            </div>
          )}

          {/* Connection */}
          <div className="flex items-center gap-2">
            <span className={`w-3 h-3 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-xs text-gray-500 uppercase">{demoMode ? 'DEMO' : connected ? 'LIVE' : 'OFFLINE'}</span>
          </div>
        </div>
      </div>

      {/* ═══ BODY ═══ */}
      <div className="flex-1 flex overflow-hidden">
        {/* ── LEFT SIDEBAR ── */}
        <div className="flex-none w-[340px] flex flex-col border-r border-[#1a1a2e] overflow-y-auto">
          {/* Current Candle */}
          <div className="p-4 border-b border-[#1a1a2e]">
            <div className="text-xs text-gray-500 font-bold mb-3 uppercase tracking-wider">Current Candle</div>
            {candle ? (
              <div className="space-y-3">
                {/* Visual candle representation */}
                <div className="flex items-center justify-center py-4">
                  <div className="flex flex-col items-center" style={{ height: 120 }}>
                    {/* Upper wick */}
                    <div 
                      className="w-[2px] rounded-full"
                      style={{
                        flex: (candle.high - Math.max(candle.open, candle.close)) / (candle.high - candle.low) * 100,
                        backgroundColor: candle.direction === 'GREEN' ? '#26a69a' : '#ef5350',
                        minHeight: 2,
                      }}
                    />
                    {/* Body */}
                    <div 
                      className="w-[40px] rounded-sm"
                      style={{
                        flex: Math.abs(candle.close - candle.open) / (candle.high - candle.low) * 100,
                        backgroundColor: candle.direction === 'GREEN' ? '#26a69a' : '#ef5350',
                        minHeight: 6,
                        boxShadow: `0 0 20px ${candle.direction === 'GREEN' ? 'rgba(38,166,154,0.4)' : 'rgba(239,83,80,0.4)'}`,
                      }}
                    />
                    {/* Lower wick */}
                    <div 
                      className="w-[2px] rounded-full"
                      style={{
                        flex: (Math.min(candle.open, candle.close) - candle.low) / (candle.high - candle.low) * 100,
                        backgroundColor: candle.direction === 'GREEN' ? '#26a69a' : '#ef5350',
                        minHeight: 2,
                      }}
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-500">Direction</span>
                    <span className={`text-base font-bold ${candle.direction === 'GREEN' ? 'text-green-400' : 'text-red-400'}`}>
                      {candle.direction === 'GREEN' ? '🟢' : '🔴'} {candle.direction}
                    </span>
                  </div>
                  
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-500">Body</span>
                    <div className="text-right">
                      <div className="text-sm font-bold text-white">${candle.body_usd.toFixed(0)}</div>
                      <div className={`text-xs ${candle.body_pct > 40 ? 'text-green-400' : 'text-gray-500'}`}>
                        {candle.body_pct.toFixed(1)}% of range
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-500">Volatility</span>
                    <span className={`text-sm font-bold ${
                      candle.volatility < 0.15 ? 'text-green-400' : 
                      candle.volatility < 0.25 ? 'text-yellow-400' : 'text-red-400'
                    }`}>
                      {candle.volatility.toFixed(3)}%
                    </span>
                  </div>
                  
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-500">Range</span>
                    <span className="text-sm text-gray-300">${(candle.high - candle.low).toFixed(0)}</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-xs text-gray-600">No data</div>
            )}
          </div>

          {/* Polymarket Shares */}
          <div className="p-4 border-b border-[#1a1a2e]">
            <div className="text-xs text-gray-500 font-bold mb-3 uppercase tracking-wider">Polymarket Shares</div>
            {market ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 rounded bg-green-500/10 border border-green-500/30">
                  <div>
                    <div className="text-xs text-green-400 mb-1">UP</div>
                    <div className="text-2xl font-black text-green-400">${market.up_price.toFixed(3)}</div>
                  </div>
                  <div className="text-4xl">▲</div>
                </div>
                
                <div className="flex items-center justify-between p-3 rounded bg-red-500/10 border border-red-500/30">
                  <div>
                    <div className="text-xs text-red-400 mb-1">DOWN</div>
                    <div className="text-2xl font-black text-red-400">${market.down_price.toFixed(3)}</div>
                  </div>
                  <div className="text-4xl">▼</div>
                </div>
                
                <div className="pt-2 border-t border-[#1a1a2e]">
                  <span className={`text-xs px-3 py-1 rounded ${
                    market.accepting_orders 
                      ? 'bg-green-500/20 text-green-400' 
                      : 'bg-red-500/20 text-red-400'
                  }`}>
                    {market.accepting_orders ? '✓ Market Open' : '✗ Market Closed'}
                  </span>
                </div>
              </div>
            ) : (
              <div className="text-xs text-gray-600">No market</div>
            )}
          </div>

          {/* Signal Status */}
          <div className="p-4 border-b border-[#1a1a2e]">
            <div className="text-xs text-gray-500 font-bold mb-3 uppercase tracking-wider">Signal Status</div>
            {signal ? (
              <div className={`p-4 rounded-lg border ${
                signal.action === 'SNIPE'
                  ? 'bg-yellow-500/10 border-yellow-500/40'
                  : 'bg-[#111] border-[#1a1a2e]'
              }`}>
                <div className={`text-xl font-black mb-2 ${
                  signal.action === 'SNIPE'
                    ? signal.direction === 'UP'
                      ? 'text-green-400'
                      : 'text-red-400'
                    : 'text-gray-500'
                }`}>
                  {signal.action === 'SNIPE' ? `🎯 SNIPE ${signal.direction}` : '⏸ WAITING'}
                </div>
                
                <div className="text-xs text-gray-400 mb-2">{signal.reason}</div>
                
                {signal.confidence && (
                  <div className="flex items-center justify-between pt-2 border-t border-[#1a1a2e]">
                    <span className="text-xs text-gray-500">Confidence</span>
                    <span className="text-lg font-bold text-white">{signal.confidence.toFixed(1)}%</span>
                  </div>
                )}
                
                {signal.metrics && (
                  <div className="mt-2 pt-2 border-t border-[#1a1a2e] space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-gray-500">Body</span>
                      <span className="text-gray-300">{signal.metrics.body_pct.toFixed(1)}% (${signal.metrics.body_usd.toFixed(0)})</span>
                    </div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-gray-500">Vol</span>
                      <span className="text-gray-300">{signal.metrics.volatility.toFixed(3)}%</span>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-xs text-gray-600">No signal</div>
            )}
          </div>

          {/* Strategy Performance */}
          <div className="p-4">
            <div className="text-xs text-gray-500 font-bold mb-3 uppercase tracking-wider">Strategy Performance</div>
            {stats && (
              <div className="space-y-3">
                <div className="p-3 rounded bg-[#111] border border-[#1a1a2e]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-gray-500">LAST-SECOND (10-20s)</span>
                    <span className={`text-base font-bold ${
                      stats.last_second_stats.win_rate >= 75 ? 'text-green-400' : 'text-yellow-400'
                    }`}>
                      {stats.last_second_stats.win_rate.toFixed(1)}%
                    </span>
                  </div>
                  <div className="text-[10px] text-gray-600">
                    {stats.last_second_stats.wins}W / {stats.last_second_stats.total - stats.last_second_stats.wins}L
                  </div>
                </div>
                
                <div className="p-3 rounded bg-[#111] border border-[#1a1a2e]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-gray-500">LATE (60-120s)</span>
                    <span className={`text-base font-bold ${
                      stats.late_stats.win_rate >= 65 ? 'text-green-400' : 'text-yellow-400'
                    }`}>
                      {stats.late_stats.win_rate.toFixed(1)}%
                    </span>
                  </div>
                  <div className="text-[10px] text-gray-600">
                    {stats.late_stats.wins}W / {stats.late_stats.total - stats.late_stats.wins}L
                  </div>
                </div>
                
                <div className="p-3 rounded bg-[#111] border border-[#1a1a2e]">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">Avg P&L / Trade</span>
                    <span className={`text-base font-bold ${pnlColor(stats.avg_pnl)}`}>
                      ${stats.avg_pnl >= 0 ? '+' : ''}{stats.avg_pnl.toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── CENTER + RIGHT ── */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Chart */}
          <div className="flex-1 relative min-h-0 border-b border-[#1a1a2e]">
            <div className="absolute top-3 left-4 z-10 flex items-center gap-4">
              <span className="text-sm font-bold text-gray-500">BTC/USDT 5m</span>
              <span className="text-xs text-green-400">● Win</span>
              <span className="text-xs text-red-400">● Loss</span>
            </div>
            <div ref={chartContainerRef} className="w-full h-full" />
          </div>

          {/* Recent Trades */}
          <div className="flex-none h-[280px] overflow-y-auto p-4">
            <div className="text-xs text-gray-500 font-bold mb-3 uppercase tracking-wider">
              Recent Trades {s?.recent_trades?.length ? `(${s.recent_trades.length})` : ''}
            </div>
            
            {s?.recent_trades && s.recent_trades.length > 0 ? (
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-gray-600 border-b border-[#1a1a2e]">
                    <th className="text-left py-2 pr-3 font-bold">TIME</th>
                    <th className="text-left py-2 pr-3 font-bold">TYPE</th>
                    <th className="text-left py-2 pr-3 font-bold">DIR</th>
                    <th className="text-right py-2 pr-3 font-bold">CONF%</th>
                    <th className="text-right py-2 pr-3 font-bold">ENTRY</th>
                    <th className="text-right py-2 pr-3 font-bold">EXIT</th>
                    <th className="text-right py-2 pr-3 font-bold">P&L</th>
                    <th className="text-left py-2 font-bold">STATUS</th>
                  </tr>
                </thead>
                <tbody>
                  {[...s.recent_trades].reverse().slice(0, 20).map((t) => (
                    <tr key={t.trade_id} className="border-b border-[#0f0f1a] hover:bg-[#111]">
                      <td className="py-2 pr-3 text-gray-400">
                        {new Date(t.timestamp).toLocaleTimeString('en-US', {
                          hour12: false,
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit',
                        })}
                      </td>
                      <td className="py-2 pr-3">
                        <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                          t.type === 'LAST_SECOND'
                            ? 'bg-red-500/20 text-red-400'
                            : 'bg-blue-500/20 text-blue-400'
                        }`}>
                          {t.type === 'LAST_SECOND' ? 'LAST' : 'LATE'}
                        </span>
                      </td>
                      <td className={`py-2 pr-3 font-bold ${
                        t.direction === 'UP' ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {t.direction === 'UP' ? '▲' : '▼'} {t.direction}
                      </td>
                      <td className="py-2 pr-3 text-right text-gray-300">{t.confidence.toFixed(0)}%</td>
                      <td className="py-2 pr-3 text-right text-gray-400">${t.entry_price.toFixed(3)}</td>
                      <td className="py-2 pr-3 text-right text-gray-400">
                        {t.exit_price ? `$${t.exit_price.toFixed(3)}` : '--'}
                      </td>
                      <td className={`py-2 pr-3 text-right font-bold ${
                        t.pnl != null ? pnlColor(t.pnl) : 'text-gray-600'
                      }`}>
                        {t.pnl != null ? `$${t.pnl >= 0 ? '+' : ''}${t.pnl.toFixed(2)}` : '--'}
                      </td>
                      <td className={`py-2 font-bold ${
                        t.status === 'closed'
                          ? t.outcome === 'WIN'
                            ? 'text-green-400'
                            : 'text-red-400'
                          : 'text-yellow-400'
                      }`}>
                        {t.status === 'closed' ? t.outcome : t.status.toUpperCase()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="text-xs text-gray-600">No trades yet — bot will start sniping when conditions are met!</div>
            )}
          </div>
        </div>
      </div>

      {/* Loading overlay */}
      {!s && (
        <div className="absolute inset-0 bg-[#0a0a14]/95 flex items-center justify-center z-50">
          <div className="text-center">
            <div className="text-3xl font-black text-white mb-3">
              🎯 <span className="text-yellow-400">SNIPER</span>
            </div>
            <div className="text-gray-500 text-sm mb-4">
              {connected ? 'Loading data...' : 'Connecting to bot...'}
            </div>
            <div className={`w-5 h-5 rounded-full mx-auto ${
              connected ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'
            }`} />
          </div>
        </div>
      )}
    </div>
  );
}
