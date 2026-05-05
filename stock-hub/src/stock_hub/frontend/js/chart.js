let chart = null;
let candleSeries = null;
let volumeSeries = null;
let ma5Series = null;
let ma10Series = null;
let ma20Series = null;
let currentStockCode = null;

function initChart(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;
  
  // Clear any existing chart (e.g., from app.js placeholder)
  container.innerHTML = '';

  chart = LightweightCharts.createChart(container, {
    layout: { background: { color: '#0a0e27' }, textColor: '#e0e6ff' },
    grid: { vertLines: { color: '#1e2548' }, horzLines: { color: '#1e2548' } },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    timeScale: { borderColor: '#1e2548' },
  });

  candleSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {
    upColor: '#ef5350',      // red = up (涨)
    downColor: '#26a69a',    // green = down (跌)
    borderVisible: false,
    wickUpColor: '#ef5350',
    wickDownColor: '#26a69a',
  });

  volumeSeries = chart.addSeries(LightweightCharts.HistogramSeries, {
    priceFormat: { type: 'volume' },
    priceScaleId: '',
  });
  volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.75, bottom: 0 } });

  ma5Series = chart.addSeries(LightweightCharts.LineSeries, { color: '#ff9800', lineWidth: 1, crosshairMarkerVisible: false });
  ma10Series = chart.addSeries(LightweightCharts.LineSeries, { color: '#2196f3', lineWidth: 1, crosshairMarkerVisible: false });
  ma20Series = chart.addSeries(LightweightCharts.LineSeries, { color: '#e040fb', lineWidth: 1, crosshairMarkerVisible: false });

  window.addEventListener('resize', () => {
    chart.applyOptions({ width: container.clientWidth });
  });
}

function calculateMA(data, period) {
  return data.map((d, i) => {
    if (i < period - 1) return { time: d.time };
    const sum = data.slice(i - period + 1, i + 1).reduce((s, c) => s + c.close, 0);
    return { time: d.time, value: sum / period };
  }).filter(d => d.value !== undefined);
}

async function loadStock(code) {
  try {
    const data = await api.get(`/stocks/${code}/kline?frequency=daily&count=200`);
    if (data && data.candles && data.candles.length > 0) {
      const candles = data.candles;
      
      candleSeries.setData(candles);
      
      const volumeData = candles.map(d => ({
        time: d.time,
        value: d.volume,
        color: d.close > d.open ? '#ef5350' : '#26a69a'
      }));
      volumeSeries.setData(volumeData);
      
      ma5Series.setData(calculateMA(candles, 5));
      ma10Series.setData(calculateMA(candles, 10));
      ma20Series.setData(calculateMA(candles, 20));
      
      chart.timeScale().fitContent();
    }
    
    // Load related posts
    const stockData = await api.get(`/stocks/${code}`);
    if (stockData && stockData.posts) {
      renderRelatedPosts(stockData.posts);
    }
  } catch (error) {
    console.error('Failed to load stock data:', error);
  }
}

function renderRelatedPosts(posts) {
  const tbody = document.getElementById('related-posts-tbody');
  if (!tbody) return;
  
  tbody.innerHTML = '';
  if (posts.length === 0) {
    tbody.innerHTML = '<tr><td colspan="3" style="text-align: center;">暂无相关资讯</td></tr>';
    return;
  }
  
  posts.forEach(post => {
    const tr = document.createElement('tr');
    
    const tdTime = document.createElement('td');
    tdTime.className = 'col-time';
    tdTime.textContent = post.time || post.publish_time || '';
    
    const tdSource = document.createElement('td');
    tdSource.className = 'col-source';
    const sourceInfo = formatSource(post.source);
    tdSource.innerHTML = `<span class="source-tag ${sourceInfo.class}">${sourceInfo.name}</span>`;
    
    const tdTitle = document.createElement('td');
    tdTitle.className = 'col-title';
    tdTitle.textContent = post.title;
    
    tr.appendChild(tdTime);
    tr.appendChild(tdSource);
    tr.appendChild(tdTitle);
    tbody.appendChild(tr);
  });
}

let reconnectTimeout = null;

function connectQuoteWs(code) {
  const wsPath = `/ws/quotes/${code}`;
  
  const ws = wsManager.connect(wsPath, (data) => {
    if (data.code !== code) return;
    
    // Update price info panel
    updateStockInfoPanel(data);
    
    // Update candle if we have a current candle
    if (data.candle) {
      candleSeries.update(data.candle);
      
      // Update volume
      volumeSeries.update({
        time: data.candle.time,
        value: data.candle.volume,
        color: data.candle.close > data.candle.open ? '#ef5350' : '#26a69a'
      });
    }
  });
  
  ws.addEventListener('close', () => {
    clearTimeout(reconnectTimeout);
    reconnectTimeout = setTimeout(() => {
      connectQuoteWs(code);
    }, 5000);
  });
}

function updateStockInfoPanel(data) {
  const nameEl = document.getElementById('stock-name');
  const priceEl = document.getElementById('stock-price');
  const changeEl = document.getElementById('stock-change');
  const volumeEl = document.getElementById('stock-volume');
  const amountEl = document.getElementById('stock-amount');
  const highEl = document.getElementById('stock-high');
  const lowEl = document.getElementById('stock-low');
  
  if (nameEl && data.name) nameEl.textContent = `${data.name} (${data.code})`;
  
  if (priceEl && data.price !== undefined) {
    priceEl.textContent = data.price.toFixed(2);
    priceEl.className = `info-value ${data.change >= 0 ? 'up' : 'down'}`;
    priceEl.style.color = data.change >= 0 ? '#ef5350' : '#26a69a';
  }
  
  if (changeEl && data.change !== undefined && data.change_pct !== undefined) {
    const sign = data.change > 0 ? '+' : '';
    changeEl.textContent = `${sign}${data.change.toFixed(2)} (${sign}${data.change_pct.toFixed(2)}%)`;
    changeEl.className = `info-value ${data.change >= 0 ? 'up' : 'down'}`;
    changeEl.style.color = data.change >= 0 ? '#ef5350' : '#26a69a';
  }
  
  if (volumeEl && data.volume !== undefined) {
    volumeEl.textContent = (data.volume / 10000).toFixed(2) + '万手';
  }
  
  if (amountEl && data.amount !== undefined) {
    amountEl.textContent = (data.amount / 100000000).toFixed(2) + '亿';
  }
  
  if (highEl && data.high !== undefined) {
    highEl.textContent = data.high.toFixed(2);
  }
  
  if (lowEl && data.low !== undefined) {
    lowEl.textContent = data.low.toFixed(2);
  }
}

function switchStock(code) {
  if (currentStockCode === code) return;
  
  // Disconnect old WebSocket
  if (currentStockCode) {
    wsManager.disconnect(`/ws/quotes/${currentStockCode}`);
  }
  
  clearTimeout(reconnectTimeout);
  
  currentStockCode = code;
  
  // Update URL hash
  if (window.location.hash !== `#/stock/${code}`) {
    window.location.hash = `#/stock/${code}`;
  }
  
  // Load new stock data
  loadStock(code);
  connectQuoteWs(code);
}
