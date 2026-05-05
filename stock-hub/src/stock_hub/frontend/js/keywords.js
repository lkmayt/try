// keywords.js

document.addEventListener('DOMContentLoaded', () => {
  const keywordInput = document.getElementById('keyword-input');
  const addKeywordBtn = document.getElementById('keyword-add-btn');
  const keywordTags = document.getElementById('keyword-tags');

  // Request Notification permission on first visit
  if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
  }

  // Fetch and render keywords
  async function loadKeywords() {
    try {
      const data = await api.get('/keywords');
      renderKeywords(data.keywords || []);
    } catch (error) {
      console.error('Failed to load keywords:', error);
    }
  }

  function renderKeywords(keywords) {
    if (!keywordTags) return;
    keywordTags.innerHTML = '';
    keywords.forEach(kw => {
      const tag = document.createElement('span');
      tag.className = 'keyword-tag';
      tag.innerHTML = `${kw.keyword} <button class="keyword-delete" data-id="${kw.id}">×</button>`;
      
      const deleteBtn = tag.querySelector('.keyword-delete');
      deleteBtn.addEventListener('click', () => deleteKeyword(kw.id, tag));
      
      keywordTags.appendChild(tag);
    });
  }

  async function addKeyword() {
    if (!keywordInput) return;
    const value = keywordInput.value.trim();
    if (!value) return;

    try {
      await api.post('/keywords', { keyword: value });
      keywordInput.value = '';
      await loadKeywords();
    } catch (error) {
      console.error('Failed to add keyword:', error);
      alert('添加关键词失败，可能已存在');
    }
  }

  async function deleteKeyword(id, tagElement) {
    try {
      const success = await api.del(`/keywords/${id}`);
      if (success) {
        tagElement.remove();
      }
    } catch (error) {
      console.error('Failed to delete keyword:', error);
    }
  }

  if (addKeywordBtn) {
    addKeywordBtn.addEventListener('click', addKeyword);
  }

  if (keywordInput) {
    keywordInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        addKeyword();
      }
    });
  }

  // Initial load
  loadKeywords();

  // WebSocket Alerts
  function connectAlertsWs() {
    const ws = new WebSocket('ws://localhost:8000/ws/alerts');

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'keyword_alert') {
          handleKeywordAlert(data);
        }
      } catch (e) {
        console.error('Failed to parse WS message:', e);
      }
    };

    ws.onclose = () => {
      console.log('Alerts WS closed, reconnecting in 5s...');
      setTimeout(connectAlertsWs, 5000);
    };

    ws.onerror = (err) => {
      console.error('Alerts WS error:', err);
      ws.close();
    };
  }

  function playAlertSound() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      osc.type = 'sine';
      osc.frequency.value = 880;
      osc.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.15);
    } catch (e) {
      console.error('Audio play failed:', e);
    }
  }

  function handleKeywordAlert(alertData) {
    // 1. Browser Notification
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification(`关键词命中: ${alertData.keyword}`, {
        body: alertData.post.title
      });
    }

    // 2. Visual highlight
    const rows = document.querySelectorAll('#posts-tbody tr:not(.detail-row)');
    rows.forEach(row => {
      const titleCell = row.querySelector('.col-title');
      if (titleCell && titleCell.textContent.includes(alertData.post.title)) {
        row.classList.add('highlight-flash');
        // Remove class after animation completes (3s)
        setTimeout(() => {
          row.classList.remove('highlight-flash');
        }, 3000);
      }
    });

    // 3. Sound
    playAlertSound();
  }

  connectAlertsWs();
});
