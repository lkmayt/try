// DOM Utilities
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => document.querySelectorAll(selector);

function createElement(tag, className, textContent) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (textContent) el.textContent = textContent;
  return el;
}

function formatTime(date) {
  const pad = (n) => n.toString().padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function formatSource(source) {
  const sourceMap = {
    'cninfo': { name: '巨潮', class: 'source-cninfo' },
    'sse': { name: '上证互动', class: 'source-sse' },
    'szse': { name: '深证互动', class: 'source-szse' },
    'jiuyan': { name: '韭研公社', class: 'source-jiuyan' },
    'zsxq': { name: '知识星球', class: 'source-zsxq' }
  };
  return sourceMap[source] || { name: source, class: '' };
}

// API Wrapper
const api = {
  async get(path) {
    const response = await fetch(`/api${path}`);
    return response.json();
  },
  async post(path, body) {
    const response = await fetch(`/api${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    return response.json();
  },
  async del(path) {
    const response = await fetch(`/api${path}`, {
      method: 'DELETE'
    });
    return response.ok;
  }
};

// WebSocket Manager
class WsManager {
  constructor() {
    this.connections = {};
  }

  connect(path, onMessage) {
    if (this.connections[path]) {
      return this.connections[path];
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host || 'localhost:8000';
    const wsUrl = `${protocol}//${host}${path}`;
    
    const ws = new WebSocket(wsUrl);
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (onMessage) onMessage(data);
      } catch (e) {
        console.error('WebSocket message parsing error:', e);
      }
    };

    ws.onclose = () => {
      console.log(`WebSocket closed: ${path}`);
      delete this.connections[path];
    };

    ws.onerror = (error) => {
      console.error(`WebSocket error on ${path}:`, error);
    };

    this.connections[path] = ws;
    return ws;
  }

  disconnect(path) {
    if (this.connections[path]) {
      this.connections[path].close();
      delete this.connections[path];
    }
  }
}

const wsManager = new WsManager();

// Routing
function navigateTo(hash) {
  window.location.hash = hash;
}

function handleRoute() {
  const hash = window.location.hash;
  if (hash.startsWith('#/stock/')) {
    const code = hash.replace('#/stock/', '');
    if (!window.location.pathname.includes('stock.html')) {
      window.location.href = `stock.html#/stock/${code}`;
    }
  } else if (hash === '#/' || hash === '') {
    if (!window.location.pathname.includes('index.html') && window.location.pathname !== '/') {
      window.location.href = 'index.html';
    }
  }
}

// Clock Updater
function updateClock() {
  const clockEl = $('#current-time');
  if (clockEl) {
    clockEl.textContent = formatTime(new Date());
  }
}

// Initialization
document.addEventListener('DOMContentLoaded', () => {
  // Start clock
  updateClock();
  setInterval(updateClock, 1000);

  // Handle routing
  window.addEventListener('hashchange', handleRoute);
  
  // Global search input handler
  const searchInput = $('#global-search');
  const searchBtn = $('#global-search-btn');
  
  if (searchInput) {
    searchInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter' && searchInput.value.trim()) {
        const val = searchInput.value.trim();
        const codeMatch = val.match(/\d{6}/);
        if (codeMatch) navigateTo(`#/stock/${codeMatch[0]}`);
      }
    });
  }
  
  if (searchBtn && searchInput) {
    searchBtn.addEventListener('click', () => {
      const val = searchInput.value.trim();
      if (val) {
        const codeMatch = val.match(/\d{6}/);
        if (codeMatch) navigateTo(`#/stock/${codeMatch[0]}`);
      }
    });
  }

  // Page specific initialization
  if (window.location.pathname.includes('stock.html')) {
    initStockPage();
  } else {
    initIndexPage();
  }
});

function initIndexPage() {
  // Tab switching logic
  const tabs = $$('.tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
    });
  });
}

function initStockPage() {
  const hash = window.location.hash;
  if (hash.startsWith('#/stock/')) {
    const code = hash.replace('#/stock/', '');
    const stockCodeInput = $('#stock-code-input');
    if (stockCodeInput) {
      stockCodeInput.value = code;
    }
    
    // Update placeholders
    const nameEl = $('#stock-name');
    if (nameEl) nameEl.textContent = `${code} (加载中...)`;
  }
}
