'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { createChart, type IChartApi, type ISeriesApi, type SeriesMarker, type CandlestickData, type Time } from 'lightweight-charts';
import { io, type Socket } from 'socket.io-client';

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

interface BacktestResults {
  total_tests: number;
  overall_accuracy: number;
  edge_vs_random: number;
  high_confidence: {
    signals_found: number;
    accuracy: number;
    edge_vs_random: number;
    signals_per_day: number;
  };
  timestamp: string;
  candle_range: string;
}

interface WickSignal {
  direction: 'buy_down' | 'buy_up';
  reason: 'failed_higher_high' | 'failed_lower_low';
  entry_price: number;
  fair_price: number;
  profit_potential: number;
  confidence: number;
  wick_ratio: number;
}

interface BotState {
  running: boolean;
  btc_price: number;
  secs_left: number;
  backtest?: BacktestResults;
  wick_signal?: WickSignal | null;
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
  prediction: {
    direction: 'UP' | 'DOWN' | 'NEUTRAL';
    confidence: number;
    confidence_raw?: number;
    confidence_calibrated?: boolean;
    expected_body_range: [number, number];
    expected_volatility: number;
    expected_close_range: [number, number];
    reasoning: string[];
    validation_metrics?: {
      total_predictions: number;
      overall_accuracy: number;
      recent_accuracy: number;
      has_enough_data: boolean;
    };
    indicators: {
      rsi: number;
      pattern: { pattern: string; signal: string; confidence: number };
      momentum: { direction: string; strength: number };
      volatility: { trend: string; current: number };
      direction_score: number;
    };
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

// ── Config ───────────────────────────────────────────────────────────
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'http://localhost:8080';

// ── Helpers ──────────────────────────────────────────────────────────
const fmtPrice = (n: number) => n?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? '--';
const fmtTimer = (secs: number) => `${Math.floor(secs / 60)}:${(secs % 60).toString().padStart(2, '0')}`;
const pnlColor = (n: number) => n > 0 ? 'text-green-400' : n < 0 ? 'text-red-400' : 'text-gray-400';

// ── Page ─────────────────────────────────────────────────────────────
export default function LiveSniperUI() {
  const [state, setState] = useState<BotState | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<number>(0);
  const [now, setNow] = useState<number>(Date.now());
  const [balance, setBalance] = useState<{ usdc: number; polygon: number } | null>(null);
  
  const socketRef = useRef<Socket | null>(null);
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartApiRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const chartInitialized = useRef(false);

  // Initialize chart
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

  // Update chart
  const updateChart = useCallback((candles: BotState['candles'], markers: BotState['trade_markers'], prediction: BotState['prediction'] | null, currentCandle: BotState['current_candle'] | null) => {
    console.log('📊 updateChart called:', { 
      hasSeries: !!candleSeriesRef.current, 
      candleCount: candles?.length || 0,
      markerCount: markers?.length || 0 
    });
    
    if (!candleSeriesRef.current) {
      console.warn('⚠️ Chart series not initialized yet');
      return;
    }
    
    if (candles && candles.length > 0) {
      console.log('✅ Setting chart data with', candles.length, 'candles');
      const chartData = candles.map(c => ({
        time: c.time as Time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }));
      
      // Add current forming candle (live updates!)
      if (currentCandle && currentCandle.open > 0 && currentCandle.close > 0) {
        const lastHistorical = candles[candles.length - 1];
        const currentTime = lastHistorical.time + 300; // 5 minutes ahead
        
        // Validate data before adding
        if (currentCandle.high >= currentCandle.low && 
            currentCandle.high >= Math.max(currentCandle.open, currentCandle.close) &&
            currentCandle.low <= Math.min(currentCandle.open, currentCandle.close)) {
          
          chartData.push({
            time: currentTime as Time,
            open: currentCandle.open,
            high: currentCandle.high,
            low: currentCandle.low,
            close: currentCandle.close,
          });
        }
      }
      
      candleSeriesRef.current.setData(chartData);
    }
    
    // Add trade markers (signals from historical analysis)
    const seriesMarkers: SeriesMarker<Time>[] = [];
    
    if (markers && markers.length > 0) {
      markers.forEach(m => {
        // Color based on type and direction
        let color = '#00ff88'; // Default green for signals
        let shape: 'circle' | 'arrowUp' | 'arrowDown' = 'circle';
        
        if (m.outcome === 'SIGNAL') {
          // Historical signal markers
          if (m.direction === 'UP') {
            color = m.type === 'LAST_SECOND' ? '#ff6b00' : '#00d4ff'; // Orange for LAST, Cyan for LATE
            shape = 'arrowUp';
          } else {
            color = m.type === 'LAST_SECOND' ? '#ff0066' : '#9900ff'; // Pink for LAST, Purple for LATE
            shape = 'arrowDown';
          }
        } else {
          // Actual trade outcomes
          color = m.outcome === 'WIN' ? '#00ff88' : '#ff4444';
          shape = 'circle';
        }
        
        seriesMarkers.push({
          time: m.time as Time,
          position: m.direction === 'UP' ? 'belowBar' : 'aboveBar',
          color: color,
          shape: shape,
          text: `${m.type?.slice(0, 4) || ''} ${m.direction} ${m.confidence.toFixed(0)}%`,
        });
      });
    }
    
    // Don't add prediction marker on chart - only show in sidebar and header badge
    
    if (seriesMarkers.length > 0) {
      candleSeriesRef.current.setMarkers(seriesMarkers);
    }
  }, []);

  // Force re-render every second to update "Xs ago" indicator
  useEffect(() => {
    const interval = setInterval(() => {
      setNow(Date.now());
    }, 1000);
    
    return () => clearInterval(interval);
  }, []);

  // Initialize chart on mount
  useEffect(() => {
    console.log('🎨 Component mounted, initializing chart...');
    // Small delay to ensure DOM is ready
    const timer = setTimeout(() => {
      initChart();
    }, 100);
    return () => clearTimeout(timer);
  }, [initChart]);

  // WebSocket connection
  useEffect(() => {
    console.log('🔌 Connecting to WebSocket:', WS_URL);
    const socket = io(WS_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 10,
    });
    
    socketRef.current = socket;
    
    socket.on('connect', () => {
      console.log('✅ WebSocket connected');
      setConnected(true);
      setError(null);
      // Force broadcast request
      socket.emit('request_state');
    });
    
    socket.on('disconnect', () => {
      console.log('❌ WebSocket disconnected');
      setConnected(false);
    });
    
    socket.on('connect_error', (err) => {
      console.error('⚠ WebSocket error:', err);
      setConnected(false);
      setError(`Connection failed: ${err.message}`);
    });
    
    socket.on('bot_state', (data: BotState) => {
      console.log('🔄 Received bot_state:', {
        candles: data.candles?.length || 0,
        markers: data.trade_markers?.length || 0,
        btc_price: data.btc_price,
        hasBacktest: !!data.backtest
      });
      setState(data);
      setLastUpdate(Date.now());
      updateChart(data.candles, data.trade_markers, data.prediction, data.current_candle);
    });
    
    return () => {
      socket.disconnect();
    };
  }, [initChart, updateChart]);

  // Bot control
  const startBot = async () => {
    try {
      const res = await fetch(`${WS_URL}/api/bot/start`, { method: 'POST' });
      const data = await res.json();
      
      if (!data.success) {
        setError(data.error || 'Failed to start bot');
      }
    } catch (err) {
      console.error('Failed to start bot:', err);
      setError('Failed to start bot - check server is running');
    }
  };
  
  const stopBot = async () => {
    try {
      const res = await fetch(`${WS_URL}/api/bot/stop`, { method: 'POST' });
      const data = await res.json();
      
      if (!data.success) {
        setError(data.error || 'Failed to stop bot');
      }
    } catch (err) {
      console.error('Failed to stop bot:', err);
      setError('Failed to stop bot');
    }
  };

  const s = state;
  const candle = s?.current_candle;
  const market = s?.current_market;
  const signal = s?.last_signal;
  const stats = s?.stats;
  const prediction = s?.prediction;
  
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

          {/* Wallet Balance */}
          <div className="flex items-center gap-3 px-4 py-2 rounded bg-[#111] border border-[#1a1a2e]">
            <div className="text-xs text-gray-500 uppercase">Balance</div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1">
                <span className="text-sm font-bold text-white">$0.00</span>
                <span className="text-xs text-gray-600">USDC</span>
              </div>
              <div className="w-px h-4 bg-[#1a1a2e]" />
              <div className="flex items-center gap-1">
                <span className="text-sm font-bold text-purple-400">0.00</span>
                <span className="text-xs text-gray-600">MATIC</span>
              </div>
            </div>
          </div>

          {/* Bot controls */}
          <div className="flex items-center gap-2">
            {s?.running ? (
              <button
                onClick={stopBot}
                className="px-4 py-2 rounded bg-red-600 hover:bg-red-700 text-white text-sm font-bold transition-colors"
              >
                STOP BOT
              </button>
            ) : (
              <button
                onClick={startBot}
                className="px-4 py-2 rounded bg-green-600 hover:bg-green-700 text-white text-sm font-bold transition-colors"
              >
                START BOT
              </button>
            )}
          </div>

          {/* Connection & Update Indicator */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className={`w-3 h-3 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
              <span className="text-xs text-gray-500 uppercase">{connected ? 'LIVE' : 'OFFLINE'}</span>
            </div>
            {connected && lastUpdate > 0 && (
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${
                  (now - lastUpdate) < 1500 ? 'bg-green-400' : 
                  (now - lastUpdate) < 3000 ? 'bg-yellow-400' : 'bg-red-400'
                } animate-pulse`} />
                <span className={`text-xs ${
                  (now - lastUpdate) < 1500 ? 'text-green-500' : 
                  (now - lastUpdate) < 3000 ? 'text-yellow-500' : 'text-red-500'
                }`}>
                  {((now - lastUpdate) / 1000).toFixed(1)}s
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex-none bg-red-500/20 border-b border-red-500/40 px-4 py-2 flex items-center gap-2">
          <span className="text-red-400">⚠</span>
          <span className="text-red-300 text-sm">{error}</span>
          <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-300">✕</button>
        </div>
      )}

      {/* ═══ BODY ═══ */}
      <div className="flex-1 flex overflow-hidden">
        {/* ── LEFT SIDEBAR ── */}
        <div className="flex-none w-[320px] flex flex-col border-r border-[#1a1a2e] overflow-y-auto">
          {/* Current Candle & Prediction */}
          <div className="p-4 border-b border-[#1a1a2e]">
            <div className="text-xs text-gray-500 font-bold mb-3 uppercase tracking-wider">Current & Predicted</div>
            <div className="flex items-start gap-4">
              {/* Current Candle */}
              {candle ? (
                <div className="flex-1 space-y-2">
                  <div className="text-[10px] text-gray-400 uppercase text-center">Current</div>
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
                  <div className="text-center">
                    <div className={`text-base font-bold ${candle.direction === 'GREEN' ? 'text-green-400' : 'text-red-400'}`}>
                      {candle.direction === 'GREEN' ? '🟢' : '🔴'} {candle.direction}
                    </div>
                    <div className="text-xs text-gray-500">${candle.body_usd.toFixed(0)} body</div>
                  </div>
                </div>
              ) : (
                <div className="flex-1 text-xs text-gray-600 text-center">No data</div>
              )}

              {/* Divider */}
              <div className="w-px h-full bg-[#1a1a2e] my-2" />

              {/* Predicted Candle */}
              {prediction && s ? (
                <div className="flex-1 space-y-2">
                  <div className="text-[10px] text-purple-400 uppercase text-center">👻 Predicted</div>
                  {(() => {
                    // Simple visual: show a candle in the predicted direction
                    // GREEN candle for UP prediction, RED candle for DOWN prediction
                    const isUp = prediction.direction === 'UP';
                    const isDown = prediction.direction === 'DOWN';
                    
                    // Use average expected body size for visual
                    const [minBody, maxBody] = prediction.expected_body_range;
                    const avgBodyUSD = (minBody + maxBody) / 2;
                    
                    // Current live BTC price (updates every second!)
                    const currentPrice = s.btc_price;
                    
                    // Estimated move based on expected body
                    const estimatedMove = avgBodyUSD / 2; // rough estimate
                    
                    // Build candle structure
                    let predictedOpen = currentPrice;
                    let predictedClose = isUp ? currentPrice + estimatedMove : 
                                       isDown ? currentPrice - estimatedMove : currentPrice;
                    
                    // Add small wicks
                    let predictedHigh = Math.max(predictedOpen, predictedClose) + estimatedMove * 0.2;
                    let predictedLow = Math.min(predictedOpen, predictedClose) - estimatedMove * 0.2;
                    
                    const range = predictedHigh - predictedLow;
                    
                    if (range <= 0 || isNaN(range)) {
                      return <div className="text-xs text-gray-600 text-center py-16">Loading...</div>;
                    }
                    
                    // Calculate proportions for flex layout
                    const upperWick = predictedHigh - Math.max(predictedOpen, predictedClose);
                    const body = Math.abs(predictedClose - predictedOpen);
                    const lowerWick = Math.min(predictedOpen, predictedClose) - predictedLow;
                    
                    const upperPct = (upperWick / range * 100);
                    const bodyPct = (body / range * 100);
                    const lowerPct = (lowerWick / range * 100);
                    
                    // Colors: GREEN for UP, RED for DOWN
                    const color = isUp ? '#26a69a' : isDown ? '#ef5350' : '#6b7280';
                    
                    return (
                      <>
                        {/* Visual candle */}
                        <div className="flex items-center justify-center py-4">
                          <div className="flex flex-col items-center" style={{ height: 120 }}>
                            {/* Upper wick */}
                            <div 
                              className="w-[2px] rounded-full"
                              style={{
                                flex: upperPct,
                                backgroundColor: color,
                                minHeight: 2,
                                opacity: 0.8,
                              }}
                            />
                            {/* Body */}
                            <div 
                              className="w-[40px] rounded-sm"
                              style={{
                                flex: Math.max(bodyPct, 15), // min 15% for visibility
                                backgroundColor: color,
                                minHeight: 8,
                                boxShadow: `0 0 20px ${isUp ? 'rgba(38,166,154,0.5)' : isDown ? 'rgba(239,83,80,0.5)' : 'rgba(107,114,128,0.3)'}`,
                              }}
                            />
                            {/* Lower wick */}
                            <div 
                              className="w-[2px] rounded-full"
                              style={{
                                flex: lowerPct,
                                backgroundColor: color,
                                minHeight: 2,
                                opacity: 0.8,
                              }}
                            />
                          </div>
                        </div>
                        <div className="text-center">
                          <div className={`text-base font-bold ${
                            isUp ? 'text-green-400' :
                            isDown ? 'text-red-400' : 'text-gray-400'
                          }`}>
                            {isUp ? '▲ UP' : isDown ? '▼ DOWN' : '━ NEUTRAL'}
                          </div>
                          <div className="text-xs text-gray-500">${avgBodyUSD.toFixed(0)} est. body</div>
                        </div>
                      </>
                    );
                  })()}
                </div>
              ) : (
                <div className="flex-1 text-xs text-gray-600 text-center">No prediction</div>
              )}
            </div>

            {/* 🔥 WICK ARBITRAGE SIGNAL */}
            {s?.wick_signal && (
              <div className="mt-4 p-4 rounded-lg border-2 border-orange-500 bg-gradient-to-br from-orange-500/10 via-transparent to-purple-500/10 animate-pulse">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-2xl">🔥</span>
                    <div>
                      <div className="text-sm font-bold text-orange-400 uppercase tracking-wide">WICK ARBITRAGE</div>
                      <div className="text-xs text-gray-400">
                        {s.wick_signal.reason === 'failed_higher_high' ? 'Failed Higher High' : 'Failed Lower Low'}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-gray-400">Profit Potential</div>
                    <div className="text-2xl font-bold text-green-400">+{s.wick_signal.profit_potential.toFixed(0)}%</div>
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-3 mt-3">
                  <div className="bg-[#0f0f1e] p-3 rounded-lg">
                    <div className="text-xs text-gray-400 mb-1">Buy {s.wick_signal.direction === 'buy_down' ? 'DOWN' : 'UP'} @</div>
                    <div className="text-xl font-bold text-white">${s.wick_signal.entry_price.toFixed(2)}</div>
                    <div className="text-xs text-orange-400 mt-1">Current Price</div>
                  </div>
                  
                  <div className="bg-[#0f0f1e] p-3 rounded-lg">
                    <div className="text-xs text-gray-400 mb-1">Fair Value</div>
                    <div className="text-xl font-bold text-green-400">${s.wick_signal.fair_price.toFixed(2)}</div>
                    <div className="text-xs text-gray-400 mt-1">Wick: {s.wick_signal.wick_ratio.toFixed(1)}x body</div>
                  </div>
                </div>
                
                <div className="mt-3 flex items-center justify-between p-3 bg-[#0f0f1e] rounded-lg">
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${s.wick_signal.confidence > 0.75 ? 'bg-green-400' : 'bg-yellow-400'} animate-ping`}></div>
                    <span className="text-xs text-gray-400">Confidence</span>
                  </div>
                  <div className="text-lg font-bold text-white">{(s.wick_signal.confidence * 100).toFixed(0)}%</div>
                </div>
                
                <div className="mt-3 text-center">
                  <div className="text-xs text-gray-400 leading-relaxed">
                    💡 Polymarket prices haven't adjusted to the wick yet. 
                    Buy cheap shares now, sell in 30-120sec when prices converge.
                  </div>
                </div>
              </div>
            )}

            {/* Current Candle Stats */}
            {candle && (
              <div className="mt-4 pt-4 border-t border-[#1a1a2e]">
                <div className="text-[10px] text-gray-500 mb-2 uppercase">Current Stats</div>

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

          {/* Next Candle Prediction */}
          {prediction && (
            <div className="p-4 border-b border-[#1a1a2e]">
              <div className="text-xs text-gray-500 font-bold mb-3 uppercase tracking-wider">Next Candle Prediction</div>
              
              <div className="space-y-3">
                {/* Direction */}
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500">Direction</span>
                  <div className="flex items-center gap-2">
                    <span className={`text-lg font-bold ${
                      prediction.direction === 'UP' ? 'text-green-400' :
                      prediction.direction === 'DOWN' ? 'text-red-400' : 'text-gray-400'
                    }`}>
                      {prediction.direction === 'UP' ? '▲ UP' : prediction.direction === 'DOWN' ? '▼ DOWN' : '━ NEUTRAL'}
                    </span>
                    <span className={`text-sm ${
                      prediction.confidence >= 70 ? 'text-green-400' :
                      prediction.confidence >= 50 ? 'text-yellow-400' : 'text-gray-500'
                    }`}>
                      {prediction.confidence.toFixed(0)}%
                    </span>
                  </div>
                </div>

                {/* Expected Body Range */}
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500">Expected Body</span>
                  <span className="text-sm text-white">
                    ${prediction.expected_body_range[0].toFixed(0)} - ${prediction.expected_body_range[1].toFixed(0)}
                  </span>
                </div>

                {/* Expected Close Range */}
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500">Expected Close</span>
                  <span className="text-sm text-white">
                    ${prediction.expected_close_range[0].toFixed(0)} - ${prediction.expected_close_range[1].toFixed(0)}
                  </span>
                </div>

                {/* Key Indicators */}
                <div className="pt-2 border-t border-[#1a1a2e]">
                  <div className="space-y-1.5 text-[10px]">
                    {prediction.indicators?.rsi !== undefined && (
                      <div className="flex items-center justify-between">
                        <span className="text-gray-600">RSI</span>
                        <span className={`${
                          prediction.indicators.rsi > 70 ? 'text-red-400' :
                          prediction.indicators.rsi < 30 ? 'text-green-400' : 'text-gray-400'
                        }`}>
                          {prediction.indicators.rsi.toFixed(1)}
                        </span>
                      </div>
                    )}
                    
                    {prediction.indicators?.pattern?.pattern && prediction.indicators.pattern.pattern !== 'NONE' && (
                      <div className="flex items-center justify-between">
                        <span className="text-gray-600">Pattern</span>
                        <span className={`${
                          prediction.indicators.pattern.signal === 'BULLISH' ? 'text-green-400' :
                          prediction.indicators.pattern.signal === 'BEARISH' ? 'text-red-400' : 'text-gray-400'
                        }`}>
                          {prediction.indicators.pattern.pattern.replace(/_/g, ' ')}
                        </span>
                      </div>
                    )}

                    {prediction.indicators?.momentum?.direction && (
                      <div className="flex items-center justify-between">
                        <span className="text-gray-600">Momentum</span>
                        <span className={`${
                          prediction.indicators.momentum.direction === 'BULLISH' ? 'text-green-400' :
                          prediction.indicators.momentum.direction === 'BEARISH' ? 'text-red-400' : 'text-gray-400'
                        }`}>
                          {prediction.indicators.momentum.direction} {prediction.indicators.momentum.strength?.toFixed(0) || 0}%
                        </span>
                      </div>
                    )}

                    {prediction.indicators?.volatility?.trend && (
                      <div className="flex items-center justify-between">
                        <span className="text-gray-600">Volatility</span>
                        <span className={`${
                          prediction.indicators.volatility.trend === 'INCREASING' ? 'text-yellow-400' :
                          prediction.indicators.volatility.trend === 'DECREASING' ? 'text-blue-400' : 'text-gray-400'
                        }`}>
                          {prediction.indicators.volatility.trend}
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Reasoning */}
                <div className="pt-2 border-t border-[#1a1a2e]">
                  <div className="text-[9px] text-gray-600 space-y-0.5">
                    {prediction.reasoning.slice(0, 3).map((reason, i) => (
                      <div key={i}>• {reason}</div>
                    ))}
                  </div>
                </div>

                {/* Validation Metrics - Real Accuracy */}
                {prediction.validation_metrics?.has_enough_data && (
                  <div className="pt-2 border-t border-[#1a1a2e]">
                    <div className="text-[9px] text-purple-400 font-bold mb-1 uppercase">Actual Track Record</div>
                    <div className="space-y-1 text-[9px]">
                      <div className="flex items-center justify-between">
                        <span className="text-gray-600">Overall Accuracy</span>
                        <span className={`font-bold ${
                          prediction.validation_metrics.overall_accuracy >= 70 ? 'text-green-400' :
                          prediction.validation_metrics.overall_accuracy >= 55 ? 'text-yellow-400' : 'text-red-400'
                        }`}>
                          {prediction.validation_metrics.overall_accuracy.toFixed(1)}%
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-600">Recent (100)</span>
                        <span className={`font-bold ${
                          prediction.validation_metrics.recent_accuracy >= 70 ? 'text-green-400' :
                          prediction.validation_metrics.recent_accuracy >= 55 ? 'text-yellow-400' : 'text-red-400'
                        }`}>
                          {prediction.validation_metrics.recent_accuracy.toFixed(1)}%
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-600">Total Predictions</span>
                        <span className="text-gray-400">
                          {prediction.validation_metrics.total_predictions}
                        </span>
                      </div>
                      {prediction.confidence_calibrated && prediction.confidence_raw && (
                        <div className="flex items-center justify-between pt-1 border-t border-[#1a1a2e]/50">
                          <span className="text-gray-600">Confidence</span>
                          <span className="text-blue-400">
                            {prediction.confidence.toFixed(0)}% (from {prediction.confidence_raw.toFixed(0)}%)
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Collecting data message */}
                {!prediction.validation_metrics?.has_enough_data && (
                  <div className="pt-2 border-t border-[#1a1a2e]">
                    <div className="text-[9px] text-gray-600 italic">
                      ⏳ Collecting prediction data... ({prediction.validation_metrics?.total_predictions || 0}/10 needed)
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

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

        {/* ── CENTER (Chart + Trades) ── */}
        <div className="flex-1 flex flex-col min-w-0 min-h-0">
          {/* How to Bet Instructions */}
          {!s?.running && (
            <div className="flex-none bg-gradient-to-r from-purple-500/10 to-blue-500/10 border-b border-purple-500/30 px-6 py-4">
              <div className="flex items-start gap-4">
                <div className="flex-none text-4xl">🎯</div>
                <div className="flex-1">
                  <div className="text-lg font-bold text-white mb-1">BET ON 5-MINUTE BTC CANDLES</div>
                  <div className="text-sm text-gray-300 mb-2">
                    The bot automatically trades Polymarket's BTC 5-min UP/DOWN markets using advanced indicators
                  </div>
                  <div className="flex items-center gap-6 text-xs">
                    <div className="flex items-center gap-2">
                      <span className="text-green-400">✓</span>
                      <span className="text-gray-400">7-indicator AI prediction</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-green-400">✓</span>
                      <span className="text-gray-400">Real-time validation & calibration</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-green-400">✓</span>
                      <span className="text-gray-400">Auto-execution on signals</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-yellow-400">⚠</span>
                      <span className="text-gray-400">Fund wallet with USDC first!</span>
                    </div>
                  </div>
                </div>
                <button
                  onClick={startBot}
                  className="flex-none px-6 py-3 rounded-lg bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 text-white font-bold text-lg shadow-lg shadow-green-500/50 transition-all transform hover:scale-105"
                >
                  START BETTING →
                </button>
              </div>
            </div>
          )}

          {/* Chart */}
          <div className="flex-1 relative min-h-0 border-b border-[#1a1a2e]">
            <div className="absolute top-3 left-4 z-10 flex items-center gap-4">
              <span className="text-sm font-bold text-white">BTC/USDT 5m</span>
              {candle && (
                <span className={`text-[10px] px-2 py-1 rounded border ${
                  candle.direction === 'GREEN' 
                    ? 'bg-green-500/20 border-green-500/40 text-green-300' 
                    : 'bg-red-500/20 border-red-500/40 text-red-300'
                }`}>
                  ⏱ Forming: {candle.direction} ${candle.body_usd.toFixed(0)}
                </span>
              )}
              {prediction && (
                <span className="text-[10px] px-2 py-1 rounded bg-purple-500/20 border border-purple-500/40 text-purple-300">
                  👻 Next: {prediction.direction} ({prediction.confidence.toFixed(0)}%)
                </span>
              )}
            </div>
            <div className="absolute top-3 right-4 z-10 flex items-center gap-3 text-[10px]">
              <span className="flex items-center gap-1">
                <span className="text-[#ff6b00]">▲</span> LAST UP
              </span>
              <span className="flex items-center gap-1">
                <span className="text-[#00d4ff]">▲</span> LATE UP
              </span>
              <span className="flex items-center gap-1">
                <span className="text-[#ff0066]">▼</span> LAST DN
              </span>
              <span className="flex items-center gap-1">
                <span className="text-[#9900ff]">▼</span> LATE DN
              </span>
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
                  {s.recent_trades.map((t) => (
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
              <div className="text-xs text-gray-600">
                {s?.running 
                  ? 'Waiting for snipe signals...'
                  : 'Click START BOT to begin trading'
                }
              </div>
            )}
          </div>
        </div>

        {/* ── RIGHT SIDEBAR - Backtest & Validation ── */}
        <div className="flex-none w-[320px] flex flex-col border-l border-[#1a1a2e] overflow-y-auto bg-[#0a0a14]">
          {/* Backtest Results */}
          {s?.backtest && (
            <div className="p-4 border-b border-[#1a1a2e]">
              <div className="text-xs text-purple-400 font-bold mb-3 uppercase tracking-wider flex items-center gap-2">
                🔬 Backtest Results
              </div>
              <div className="space-y-3">
                <div className="p-3 rounded bg-[#111] border border-purple-500/20">
                  <div className="text-[10px] text-gray-500 mb-2 uppercase">Overall Performance</div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">Total Tests</span>
                      <span className="text-sm font-bold text-white">{s.backtest.total_tests.toLocaleString()}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">Accuracy</span>
                      <span className="text-sm font-bold text-red-400">{s.backtest.overall_accuracy.toFixed(1)}%</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">Edge vs Random</span>
                      <span className="text-sm font-bold text-red-400">{s.backtest.edge_vs_random >= 0 ? '+' : ''}{s.backtest.edge_vs_random.toFixed(1)}%</span>
                    </div>
                  </div>
                  <div className="text-[9px] text-gray-600 mt-2">
                    {s.backtest.candle_range}
                  </div>
                </div>

                <div className="p-3 rounded bg-gradient-to-br from-green-500/10 to-emerald-500/10 border border-green-500/30">
                  <div className="text-[10px] text-green-400 mb-2 uppercase font-bold">✅ High Confidence (&gt;70%)</div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">Signals Found</span>
                      <span className="text-sm font-bold text-white">{s.backtest.high_confidence.signals_found}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">Accuracy</span>
                      <span className="text-lg font-black text-green-400">{s.backtest.high_confidence.accuracy.toFixed(1)}%</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">Edge vs Random</span>
                      <span className="text-sm font-bold text-green-400">+{s.backtest.high_confidence.edge_vs_random.toFixed(1)}%</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">Rate</span>
                      <span className="text-xs text-gray-400">~{s.backtest.high_confidence.signals_per_day.toFixed(1)} signals/day</span>
                    </div>
                  </div>
                </div>

                <div className="text-[9px] text-gray-600 leading-relaxed">
                  💡 <span className="text-purple-400">Strategy:</span> Only trade predictions with &gt;70% confidence. These show {s.backtest.high_confidence.accuracy.toFixed(1)}% historical accuracy with a {s.backtest.high_confidence.edge_vs_random.toFixed(1)}% edge over random.
                </div>
              </div>
            </div>
          )}

          {/* Live Validation Metrics */}
          {prediction?.validation_metrics?.has_enough_data && (
            <div className="p-4 border-b border-[#1a1a2e]">
              <div className="text-xs text-blue-400 font-bold mb-3 uppercase tracking-wider flex items-center gap-2">
                📊 Live Accuracy
              </div>
              <div className="space-y-3">
                <div className="p-3 rounded bg-[#111] border border-blue-500/20">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-gray-500">Overall</span>
                    <span className={`text-lg font-bold ${
                      prediction.validation_metrics.overall_accuracy >= 60 ? 'text-green-400' :
                      prediction.validation_metrics.overall_accuracy >= 55 ? 'text-yellow-400' : 'text-red-400'
                    }`}>
                      {prediction.validation_metrics.overall_accuracy.toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-gray-500">Recent (100)</span>
                    <span className={`text-lg font-bold ${
                      prediction.validation_metrics.recent_accuracy >= 60 ? 'text-green-400' :
                      prediction.validation_metrics.recent_accuracy >= 55 ? 'text-yellow-400' : 'text-red-400'
                    }`}>
                      {prediction.validation_metrics.recent_accuracy.toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">Total Predictions</span>
                    <span className="text-sm text-gray-400">
                      {prediction.validation_metrics.total_predictions}
                    </span>
                  </div>
                </div>

                {prediction.confidence_calibrated && prediction.confidence_raw && (
                  <div className="p-2 rounded bg-purple-500/10 border border-purple-500/30">
                    <div className="text-[9px] text-purple-400 mb-1 uppercase font-bold">Auto-Calibration</div>
                    <div className="text-[10px] text-gray-400">
                      Raw: {prediction.confidence_raw.toFixed(0)}% → Calibrated: {prediction.confidence.toFixed(0)}%
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Prediction History (Last 10) */}
          <div className="p-4 border-b border-[#1a1a2e]">
            <div className="text-xs text-gray-500 font-bold mb-3 uppercase tracking-wider">
              Recent Predictions
            </div>
            <div className="space-y-2">
              {/* Placeholder for recent predictions - will be populated from validation log */}
              <div className="text-[10px] text-gray-600">
                Track last 10 predictions vs actual outcomes here
              </div>
              {/* TODO: Add prediction history from state */}
            </div>
          </div>

          {/* Strategy Stats */}
          {stats && (
            <div className="p-4">
              <div className="text-xs text-gray-500 font-bold mb-3 uppercase tracking-wider">
                Strategy Breakdown
              </div>
              <div className="space-y-2">
                <div className="p-3 rounded bg-[#111] border border-[#1a1a2e]">
                  <div className="text-[10px] text-orange-400 mb-2 uppercase font-bold">LAST-SECOND (10-20s)</div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-gray-500">Win Rate</span>
                    <span className={`text-base font-bold ${
                      stats.last_second_stats.win_rate >= 70 ? 'text-green-400' : 'text-yellow-400'
                    }`}>
                      {stats.last_second_stats.win_rate.toFixed(1)}%
                    </span>
                  </div>
                  <div className="text-[10px] text-gray-600">
                    {stats.last_second_stats.wins}W / {stats.last_second_stats.total - stats.last_second_stats.wins}L
                  </div>
                </div>

                <div className="p-3 rounded bg-[#111] border border-[#1a1a2e]">
                  <div className="text-[10px] text-cyan-400 mb-2 uppercase font-bold">LATE (60-120s)</div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-gray-500">Win Rate</span>
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

                <div className="p-3 rounded bg-gradient-to-br from-purple-500/10 to-blue-500/10 border border-purple-500/30">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-400">Avg P&L / Trade</span>
                    <span className={`text-lg font-bold ${pnlColor(stats.avg_pnl)}`}>
                      ${stats.avg_pnl >= 0 ? '+' : ''}{stats.avg_pnl.toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Risk Management Reminder */}
          <div className="p-4 mt-auto border-t border-[#1a1a2e]">
            <div className="p-3 rounded bg-yellow-500/10 border border-yellow-500/30">
              <div className="text-[10px] text-yellow-400 font-bold mb-2 uppercase">⚠️ Risk Management</div>
              <div className="space-y-1 text-[9px] text-gray-400">
                <div>• Start small: $5-10 per trade</div>
                <div>• Max 2-3% of bankroll per trade</div>
                <div>• Only trade &gt;70% confidence</div>
                <div>• Track 50+ trades before scaling</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Loading overlay */}
      {!s && !error && (
        <div className="absolute inset-0 bg-[#0a0a14]/95 flex items-center justify-center z-50">
          <div className="text-center">
            <div className="text-3xl font-black text-white mb-3">
              🎯 <span className="text-yellow-400">SNIPER</span>
            </div>
            <div className="text-gray-500 text-sm mb-4">
              {connected ? 'Waiting for bot data...' : 'Connecting to server...'}
            </div>
            <div className={`w-5 h-5 rounded-full mx-auto ${
              connected ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'
            }`} />
            <div className="text-xs text-gray-600 mt-4">
              Make sure web_server.py is running on port 8080
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
