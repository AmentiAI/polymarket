'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { createChart, type IChartApi, type ISeriesApi, type CandlestickData, type Time } from 'lightweight-charts';

// ── Types ────────────────────────────────────────────────────────────
interface Trade {
  trade_id: string;
  timestamp: string;
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
  current_market: {
    timestamp: number;
    up_price: number;
    down_price: number;
    accepting_orders: boolean;
  } | null;
  current_candle: {
    open: number;
    high: number;
    low: number;
    close: number;
    body_pct: number;
    volatility: number;
  } | null;
  secs_left: number;
  last_signal: {
    action: 'SNIPE' | 'WAIT';
    direction?: 'UP' | 'DOWN';
    reason: string;
    confidence?: number;
    type?: 'LAST_SECOND' | 'LATE';
  } | null;
  stats: {
    total: number;
    wins: number;
    losses: number;
    win_rate: number;
    pnl: number;
    avg_pnl: number;
    last_second_wr: number;
    late_wr: number;
  };
  recent_trades: Trade[];
  candles: {
    time: number;
    open: number;
    high: number;
    low: number;
    close: number;
  }[];
}

// ── Helpers ──────────────────────────────────────────────────────────
const fmtPrice = (n: number) => n?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? '--';
const fmtTimer = (secs: number) => `${Math.floor(secs / 60)}:${(secs % 60).toString().padStart(2, '0')}`;
const pnlColor = (n: number) => n > 0 ? 'text-green-400' : n < 0 ? 'text-red-400' : 'text-gray-400';

// ── Mock Data Generator (for demo) ───────────────────────────────────
function generateMockState(): BotState {
  const now = Math.floor(Date.now() / 1000);
  const candle5minStart = Math.floor(now / 300) * 300;
  const secsLeft = (candle5minStart + 300) - now;
  
  // Random candle
  const open = 95000 + Math.random() * 1000;
  const close = open + (Math.random() - 0.5) * 150;
  const high = Math.max(open, close) + Math.random() * 50;
  const low = Math.min(open, close) - Math.random() * 50;
  const body = Math.abs(close - open);
  const range = high - low;
  const body_pct = range > 0 ? (body / range) * 100 : 0;
  const volatility = (range / open) * 100;
  
  return {
    running: true,
    current_market: {
      timestamp: candle5minStart + 300,
      up_price: 0.52 + Math.random() * 0.2,
      down_price: 0.48 - Math.random() * 0.2,
      accepting_orders: true,
    },
    current_candle: {
      open,
      high,
      low,
      close,
      body_pct,
      volatility,
    },
    secs_left: secsLeft,
    last_signal: {
      action: Math.random() > 0.7 ? 'SNIPE' : 'WAIT',
      direction: Math.random() > 0.5 ? 'UP' : 'DOWN',
      reason: 'LATE: Clean green continuation (body $67, vol 0.11%)',
      confidence: 65 + Math.random() * 20,
      type: Math.random() > 0.5 ? 'LAST_SECOND' : 'LATE',
    },
    stats: {
      total: 24,
      wins: 17,
      losses: 7,
      win_rate: 70.8,
      pnl: 34.20,
      avg_pnl: 1.43,
      last_second_wr: 76.5,
      late_wr: 68.2,
    },
    recent_trades: [],
    candles: [],
  };
}

// ── Page ─────────────────────────────────────────────────────────────
export default function SniperUI() {
  const [state, setState] = useState<BotState | null>(null);
  const [connected, setConnected] = useState(false);
  const [demoMode, setDemoMode] = useState(true);
  
  // Chart refs
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartApiRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const chartInitialized = useRef(false);

  // Init chart
  const initChart = useCallback(() => {
    if (chartInitialized.current || !chartContainerRef.current) return;
    
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: '#0a0a14' },
        textColor: '#9ca3af',
      },
      grid: {
        vertLines: { color: '#1a1a2e' },
        horzLines: { color: '#1a1a2e' },
      },
      crosshair: { mode: 0 as const },
      rightPriceScale: { borderColor: '#2a2a3e' },
      timeScale: {
        borderColor: '#2a2a3e',
        timeVisible: true,
        secondsVisible: false,
      },
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

  // Update chart
  const updateChart = useCallback((candles: BotState['candles']) => {
    if (!candleSeriesRef.current || !candles.length) return;
    
    const chartData = candles.map(c => ({
      time: c.time as Time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));
    
    candleSeriesRef.current.setData(chartData);
  }, []);

  // Demo mode: generate fake data
  useEffect(() => {
    if (!demoMode) return;
    
    initChart();
    
    const interval = setInterval(() => {
      setState(generateMockState());
    }, 1000);
    
    setConnected(true);
    
    return () => clearInterval(interval);
  }, [demoMode, initChart]);

  // Real mode: connect to bot backend
  useEffect(() => {
    if (demoMode) return;
    
    initChart();
    
    // TODO: WebSocket connection to Python bot
    // const ws = new WebSocket('ws://localhost:8080/ws');
    // ws.onopen = () => setConnected(true);
    // ws.onclose = () => setConnected(false);
    // ws.onmessage = (ev) => {
    //   const data = JSON.parse(ev.data);
    //   setState(data);
    //   updateChart(data.candles);
    // };
    
    // return () => ws.close();
  }, [demoMode, initChart, updateChart]);

  const s = state;
  const candle = s?.current_candle;
  const market = s?.current_market;
  const signal = s?.last_signal;
  const stats = s?.stats;
  
  // Timer urgency color
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
          <div className="text-xl font-bold text-white">
            ${candle ? fmtPrice(candle.close) : '--'}
          </div>
        </div>

        {/* Countdown */}
        <div className="flex items-center gap-2">
          <div className="text-xs text-gray-500">NEXT CLOSE</div>
          <div className={`text-3xl font-black ${timerColor} tabular-nums`}>
            {s ? fmtTimer(secsLeft) : '--:--'}
          </div>
        </div>

        {/* Live signal */}
        {signal?.action === 'SNIPE' && (
          <div className={`px-4 py-2 rounded-lg font-bold text-sm border-2 ${
            signal.direction === 'UP'
              ? 'bg-green-500/20 border-green-500 text-green-400'
              : 'bg-red-500/20 border-red-500 text-red-400'
          } animate-pulse`}>
            🔥 {signal.type} {signal.direction} {signal.confidence?.toFixed(0)}%
          </div>
        )}

        <div className="ml-auto flex items-center gap-4">
          {/* Stats */}
          {stats && (
            <div className="flex items-center gap-3 px-4 py-2 rounded bg-[#111] border border-[#1a1a2e]">
              <div className="text-center">
                <div className="text-[10px] text-gray-500 uppercase">W/L</div>
                <div className="text-sm font-bold">
                  <span className="text-green-400">{stats.wins}</span>
                  <span className="text-gray-600">/</span>
                  <span className="text-red-400">{stats.losses}</span>
                </div>
              </div>
              <div className="text-center">
                <div className="text-[10px] text-gray-500 uppercase">Win Rate</div>
                <div className={`text-sm font-bold ${stats.win_rate >= 70 ? 'text-green-400' : stats.win_rate >= 60 ? 'text-yellow-400' : 'text-red-400'}`}>
                  {stats.win_rate.toFixed(1)}%
                </div>
              </div>
              <div className="text-center">
                <div className="text-[10px] text-gray-500 uppercase">P&L</div>
                <div className={`text-sm font-bold ${pnlColor(stats.pnl)}`}>
                  ${stats.pnl >= 0 ? '+' : ''}{stats.pnl.toFixed(2)}
                </div>
              </div>
            </div>
          )}

          {/* Connection status */}
          <div className="flex items-center gap-2">
            <span className={`w-3 h-3 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-xs text-gray-500">{connected ? 'LIVE' : 'OFFLINE'}</span>
          </div>

          {/* Demo toggle */}
          <button
            onClick={() => setDemoMode(!demoMode)}
            className={`px-3 py-1 rounded text-xs font-bold ${
              demoMode
                ? 'bg-blue-600 hover:bg-blue-700 text-white'
                : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
            }`}
          >
            {demoMode ? 'DEMO' : 'LIVE'}
          </button>
        </div>
      </div>

      {/* ═══ BODY ═══ */}
      <div className="flex-1 flex overflow-hidden">
        {/* ── LEFT SIDEBAR ── */}
        <div className="flex-none w-[320px] flex flex-col border-r border-[#1a1a2e] overflow-y-auto">
          {/* Current Candle */}
          <div className="p-4 border-b border-[#1a1a2e]">
            <div className="text-xs text-gray-500 font-bold mb-3 uppercase">Current Candle</div>
            {candle ? (
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-xs text-gray-500">Body</span>
                  <span className={`text-sm font-bold ${candle.close >= candle.open ? 'text-green-400' : 'text-red-400'}`}>
                    ${Math.abs(candle.close - candle.open).toFixed(0)} ({candle.body_pct.toFixed(1)}%)
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-gray-500">Volatility</span>
                  <span className={`text-sm font-bold ${candle.volatility < 0.15 ? 'text-green-400' : candle.volatility < 0.25 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {candle.volatility.toFixed(3)}%
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-gray-500">Range</span>
                  <span className="text-sm text-gray-300">${(candle.high - candle.low).toFixed(0)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-gray-500">Direction</span>
                  <span className={`text-sm font-bold ${candle.close >= candle.open ? 'text-green-400' : 'text-red-400'}`}>
                    {candle.close >= candle.open ? '🟢 GREEN' : '🔴 RED'}
                  </span>
                </div>
              </div>
            ) : (
              <div className="text-xs text-gray-600">No data</div>
            )}
          </div>

          {/* Market Info */}
          <div className="p-4 border-b border-[#1a1a2e]">
            <div className="text-xs text-gray-500 font-bold mb-3 uppercase">Polymarket Shares</div>
            {market ? (
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-xs text-gray-500">UP</span>
                  <span className="text-lg font-bold text-green-400">${market.up_price.toFixed(3)}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-gray-500">DOWN</span>
                  <span className="text-lg font-bold text-red-400">${market.down_price.toFixed(3)}</span>
                </div>
                <div className="mt-2 pt-2 border-t border-[#1a1a2e]">
                  <span className={`text-[10px] px-2 py-1 rounded ${market.accepting_orders ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                    {market.accepting_orders ? '✓ ACCEPTING ORDERS' : '✗ MARKET CLOSED'}
                  </span>
                </div>
              </div>
            ) : (
              <div className="text-xs text-gray-600">No market</div>
            )}
          </div>

          {/* Signal Status */}
          <div className="p-4 border-b border-[#1a1a2e]">
            <div className="text-xs text-gray-500 font-bold mb-3 uppercase">Signal Status</div>
            {signal ? (
              <div className="space-y-2">
                <div className={`px-3 py-2 rounded ${
                  signal.action === 'SNIPE'
                    ? 'bg-yellow-500/20 border border-yellow-500/40'
                    : 'bg-gray-800/50 border border-[#1a1a2e]'
                }`}>
                  <div className={`text-lg font-bold mb-1 ${
                    signal.action === 'SNIPE'
                      ? signal.direction === 'UP'
                        ? 'text-green-400'
                        : 'text-red-400'
                      : 'text-gray-500'
                  }`}>
                    {signal.action === 'SNIPE' ? `🎯 SNIPE ${signal.direction}` : '⏸ WAITING'}
                  </div>
                  <div className="text-xs text-gray-400">{signal.reason}</div>
                  {signal.confidence && (
                    <div className="text-sm font-bold text-white mt-1">
                      {signal.confidence.toFixed(1)}% confidence
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-xs text-gray-600">No signal</div>
            )}
          </div>

          {/* Strategy Stats */}
          {stats && (
            <div className="p-4">
              <div className="text-xs text-gray-500 font-bold mb-3 uppercase">Strategy Performance</div>
              <div className="space-y-3">
                <div className="p-2 rounded bg-[#111]">
                  <div className="text-[10px] text-gray-500 mb-1">LAST-SECOND (10-20s)</div>
                  <div className={`text-sm font-bold ${stats.last_second_wr >= 70 ? 'text-green-400' : 'text-yellow-400'}`}>
                    {stats.last_second_wr.toFixed(1)}% win rate
                  </div>
                </div>
                <div className="p-2 rounded bg-[#111]">
                  <div className="text-[10px] text-gray-500 mb-1">LATE (60-120s)</div>
                  <div className={`text-sm font-bold ${stats.late_wr >= 65 ? 'text-green-400' : 'text-yellow-400'}`}>
                    {stats.late_wr.toFixed(1)}% win rate
                  </div>
                </div>
                <div className="p-2 rounded bg-[#111]">
                  <div className="text-[10px] text-gray-500 mb-1">AVG P&L / TRADE</div>
                  <div className={`text-sm font-bold ${pnlColor(stats.avg_pnl)}`}>
                    ${stats.avg_pnl >= 0 ? '+' : ''}{stats.avg_pnl.toFixed(2)}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ── CENTER + RIGHT ── */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Chart */}
          <div className="flex-1 relative min-h-0 border-b border-[#1a1a2e]">
            <div className="absolute top-3 left-4 z-10 text-sm font-bold text-gray-500">
              BTC/USDT 5m
            </div>
            <div ref={chartContainerRef} className="w-full h-full" />
          </div>

          {/* Recent Trades */}
          <div className="flex-none h-[280px] overflow-y-auto p-4">
            <div className="text-xs text-gray-500 font-bold mb-3 uppercase">
              Recent Trades {s?.recent_trades?.length ? `(${s.recent_trades.length})` : ''}
            </div>
            
            {s?.recent_trades && s.recent_trades.length > 0 ? (
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-gray-600 border-b border-[#1a1a2e]">
                    <th className="text-left py-2 pr-3">TIME</th>
                    <th className="text-left py-2 pr-3">TYPE</th>
                    <th className="text-left py-2 pr-3">DIR</th>
                    <th className="text-right py-2 pr-3">CONF%</th>
                    <th className="text-right py-2 pr-3">ENTRY</th>
                    <th className="text-right py-2 pr-3">EXIT</th>
                    <th className="text-right py-2 pr-3">P&L</th>
                    <th className="text-left py-2">STATUS</th>
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
                        <span className={`text-[10px] px-2 py-0.5 rounded ${
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
                      <td className={`py-2 ${
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
              <div className="text-xs text-gray-600">No trades yet — run the bot to start sniping!</div>
            )}
          </div>
        </div>
      </div>

      {/* Loading overlay */}
      {!s && (
        <div className="absolute inset-0 bg-[#0a0a14]/95 flex items-center justify-center z-50">
          <div className="text-center">
            <div className="text-2xl font-bold text-white mb-2">
              🎯 <span className="text-yellow-400">SNIPER</span>
            </div>
            <div className="text-gray-500 text-sm mb-4">
              {connected ? 'Waiting for data...' : 'Connecting to bot...'}
            </div>
            <div className={`w-4 h-4 rounded-full mx-auto ${
              connected ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'
            }`} />
          </div>
        </div>
      )}
    </div>
  );
}
