document.addEventListener('DOMContentLoaded', () => {
  const statusBar = document.querySelector('.status-bar');
  const indicatorsContainer = document.querySelector('.status-indicators');
  const toggleBtn = document.getElementById('scheduler-toggle');
  
  let isSchedulerRunning = false;
  let healthData = null;
  let pollInterval = null;

  const sourceNames = {
    'cninfo': '巨潮',
    'sse': '上证互动',
    'szse': '深证互动',
    'jiuyan': '韭研公社',
    'zsxq': '知识星球'
  };

  // Create expanded panel
  const expandedPanel = document.createElement('div');
  expandedPanel.className = 'status-expanded-panel';
  expandedPanel.style.display = 'none';
  expandedPanel.innerHTML = `
    <table class="status-table">
      <thead>
        <tr>
          <th>名称</th>
          <th>状态</th>
          <th>最后抓取</th>
          <th>帖子数</th>
          <th>错误信息</th>
        </tr>
      </thead>
      <tbody id="status-tbody"></tbody>
    </table>
  `;
  document.body.appendChild(expandedPanel);

  // Create config modal
  const configModal = document.createElement('div');
  configModal.className = 'config-modal-overlay';
  configModal.style.display = 'none';
  configModal.innerHTML = `
    <div class="config-modal">
      <div class="config-modal-header">
        <h3>设置</h3>
        <span class="close-modal">&times;</span>
      </div>
      <div class="config-modal-body">
        <div class="form-group">
          <label>知识星球 Cookie</label>
          <textarea id="zsxq-cookie" rows="4" placeholder="输入 Cookie..."></textarea>
        </div>
        <div class="form-group">
          <label>抓取间隔 (秒): <span id="interval-val">60</span></label>
          <input type="range" id="scrape-interval" min="30" max="300" value="60">
        </div>
        <button id="save-config-btn" class="btn" style="background-color: var(--success); width: 100%; margin-top: 10px;">保存</button>
      </div>
    </div>
  `;
  document.body.appendChild(configModal);

  // Add settings button to status bar
  const settingsBtn = document.createElement('div');
  settingsBtn.className = 'settings-btn';
  settingsBtn.innerHTML = '⚙️ 设置';
  settingsBtn.style.cursor = 'pointer';
  settingsBtn.style.marginLeft = '15px';
  settingsBtn.style.display = 'inline-flex';
  settingsBtn.style.alignItems = 'center';
  
  // Insert settings button after indicators
  indicatorsContainer.parentNode.insertBefore(settingsBtn, indicatorsContainer.nextSibling);

  // Styles for new elements
  const style = document.createElement('style');
  style.textContent = `
    .status-indicator { display: inline-flex; align-items: center; margin-right: 15px; cursor: pointer; }
    .status-dot { width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
    .status-active { background-color: #26a69a; }
    .status-idle { background-color: #ffa726; }
    .status-error { background-color: #ef5350; }
    
    .status-expanded-panel {
      position: fixed;
      bottom: 40px;
      left: 10px;
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: 4px;
      padding: 10px;
      z-index: 1000;
      box-shadow: 0 -2px 10px rgba(0,0,0,0.5);
      max-width: 600px;
    }
    .status-table { width: 100%; border-collapse: collapse; font-size: 12px; }
    .status-table th, .status-table td { padding: 6px 10px; text-align: left; border-bottom: 1px solid var(--border-color); }
    .status-table th { color: var(--text-secondary); }
    
    .config-modal-overlay {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.7);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 2000;
    }
    .config-modal {
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      width: 400px;
      padding: 20px;
    }
    .config-modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
    .config-modal-header h3 { margin: 0; }
    .close-modal { cursor: pointer; font-size: 20px; color: var(--text-secondary); }
    .close-modal:hover { color: var(--text-primary); }
    .form-group { margin-bottom: 15px; }
    .form-group label { display: block; margin-bottom: 5px; color: var(--text-secondary); font-size: 12px; }
    .form-group textarea { width: 100%; background: var(--bg-primary); border: 1px solid var(--border-color); color: var(--text-primary); padding: 8px; border-radius: 4px; resize: vertical; }
    .form-group input[type="range"] { width: 100%; }
  `;
  document.head.appendChild(style);

  // Toggle expanded panel
  indicatorsContainer.addEventListener('click', () => {
    expandedPanel.style.display = expandedPanel.style.display === 'none' ? 'block' : 'none';
  });

  // Config modal logic
  settingsBtn.addEventListener('click', () => {
    configModal.style.display = 'flex';
  });
  
  configModal.querySelector('.close-modal').addEventListener('click', () => {
    configModal.style.display = 'none';
  });
  
  configModal.addEventListener('click', (e) => {
    if (e.target === configModal) configModal.style.display = 'none';
  });

  const intervalInput = document.getElementById('scrape-interval');
  const intervalVal = document.getElementById('interval-val');
  intervalInput.addEventListener('input', (e) => {
    intervalVal.textContent = e.target.value;
  });

  document.getElementById('save-config-btn').addEventListener('click', async () => {
    const cookie = document.getElementById('zsxq-cookie').value;
    const interval = intervalInput.value;
    try {
      await api.post('/config/zsxq', { cookie, interval: parseInt(interval) });
      configModal.style.display = 'none';
      // Optional: show success toast
    } catch (err) {
      console.error('Failed to save config', err);
    }
  });

  // Scheduler toggle logic
  if (toggleBtn) {
    toggleBtn.addEventListener('click', async () => {
      try {
        if (isSchedulerRunning) {
          await api.post('/scheduler/stop');
          isSchedulerRunning = false;
          toggleBtn.textContent = '开始';
          toggleBtn.style.backgroundColor = 'var(--bg-secondary)';
          // Set all indicators to yellow
          renderIndicators(healthData, true);
        } else {
          await api.post('/scheduler/start');
          isSchedulerRunning = true;
          toggleBtn.textContent = '停止';
          toggleBtn.style.backgroundColor = 'var(--success)';
          // Update indicators from health data
          renderIndicators(healthData, false);
        }
      } catch (err) {
        console.error('Failed to toggle scheduler', err);
      }
    });
  }

  function renderIndicators(data, forceIdle = false) {
    if (!data || !data.sources) return;
    
    indicatorsContainer.innerHTML = '';
    const tbody = document.getElementById('status-tbody');
    tbody.innerHTML = '';

    Object.keys(sourceNames).forEach(sourceKey => {
      const sourceInfo = data.sources[sourceKey] || {};
      const name = sourceNames[sourceKey];
      
      let statusColor = 'status-idle';
      let statusText = '未知';
      
      if (forceIdle) {
        statusColor = 'status-idle';
        statusText = '已停止';
      } else {
        if (sourceInfo.status === 'ok' || sourceInfo.status === 'active') {
          statusColor = 'status-active';
          statusText = '正常';
        } else if (sourceInfo.status === 'error') {
          statusColor = 'status-error';
          statusText = '错误';
        } else {
          statusColor = 'status-idle';
          statusText = sourceInfo.status || '空闲';
        }
      }

      // Add to status bar
      const indicator = document.createElement('span');
      indicator.className = 'status-indicator';
      indicator.innerHTML = `<span class="status-dot ${statusColor}"></span> ${name}`;
      indicatorsContainer.appendChild(indicator);

      // Add to expanded panel
      const tr = document.createElement('tr');
      const lastScrape = sourceInfo.last_scrape ? new Date(sourceInfo.last_scrape).toLocaleString() : '-';
      const count = sourceInfo.count !== undefined ? sourceInfo.count : '-';
      const errorMsg = sourceInfo.error || '-';
      
      tr.innerHTML = `
        <td>${name}</td>
        <td><span class="status-dot ${statusColor}" style="display:inline-block"></span> ${statusText}</td>
        <td>${lastScrape}</td>
        <td>${count}</td>
        <td style="color: ${sourceInfo.error ? 'var(--error)' : 'inherit'}">${errorMsg}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  async function fetchHealth() {
    try {
      const data = await api.get('/health');
      healthData = data;
      renderIndicators(data, !isSchedulerRunning);
    } catch (err) {
      console.error('Failed to fetch health', err);
    }
  }

  // Initialize
  fetchHealth();
  pollInterval = setInterval(fetchHealth, 10000);
});
