// Smart stock search autocomplete using Sina suggest API (JSONP to avoid CORS)
let suggestTimer = null;
let suggestDropdown = null;
let suggestCallbackId = 0;

function initSmartSearch() {
  const input = document.getElementById('global-search');
  if (!input) return;

  suggestDropdown = document.createElement('div');
  suggestDropdown.className = 'suggest-dropdown';
  suggestDropdown.style.display = 'none';
  input.parentElement.appendChild(suggestDropdown);

  input.addEventListener('input', () => {
    clearTimeout(suggestTimer);
    const q = input.value.trim();
    if (q.length < 1) { suggestDropdown.style.display = 'none'; return; }
    suggestTimer = setTimeout(() => fetchSuggestions(q), 250);
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') suggestDropdown.style.display = 'none';
    if (e.key === 'Enter') {
      suggestDropdown.style.display = 'none';
      const q = input.value.trim();
      if (q) goToStock(q);
    }
  });

  document.getElementById('global-search-btn').addEventListener('click', () => {
    const q = input.value.trim();
    if (q) goToStock(q);
  });

  document.addEventListener('click', (e) => {
    if (!input.contains(e.target) && !suggestDropdown.contains(e.target)) {
      suggestDropdown.style.display = 'none';
    }
  });
}

function fetchSuggestions(keyword) {
  const cbName = '__sina_suggest_cb_' + (++suggestCallbackId);
  window[cbName] = function(data) {
    delete window[cbName];
    showSuggestions(data);
  };

  const script = document.createElement('script');
  script.src = 'https://suggest3.sinajs.cn/suggest/?name=suggestion&type=111&key=' + encodeURIComponent(keyword);
  script.onerror = function() {
    script.remove();
    delete window[cbName];
    suggestDropdown.style.display = 'none';
  };
  script.onload = function() {
    // Sina API sets global `suggestion` var when loaded as script (JSONP pattern)
    var data = window.suggestion;
    if (data) { showSuggestions(data); delete window.suggestion; }
    script.remove();
  };
  document.head.appendChild(script);
  setTimeout(function() { script.remove(); }, 5000);
}

function showSuggestions(raw) {
  if (!raw) { suggestDropdown.style.display = 'none'; return; }

  var items = String(raw).split(';').filter(Boolean);
  if (items.length === 0) { suggestDropdown.style.display = 'none'; return; }

  suggestDropdown.innerHTML = items.map(function(item) {
    var parts = item.split(',');
    // Format: name,111,market_code,code,name,,abbr,...
    if (parts.length < 4) return '';
    var name = parts[0];
    var code = parts[3] || parts[2];
    var abbr = parts[6] ? parts[6].toUpperCase() : '';
    // Strip exchange prefix for display
    var displayCode = code.replace(/^(sh|sz|bj)/i, '');
    return '<div class="suggest-item" data-code="' + displayCode + '" data-name="' + name + '">'
      + '<span class="suggest-name">' + name + '</span>'
      + '<span class="suggest-code">' + displayCode + '</span>'
      + (abbr ? '<span class="suggest-abbr">' + abbr + '</span>' : '')
      + '</div>';
  }).join('');

  suggestDropdown.querySelectorAll('.suggest-item').forEach(function(item) {
    item.addEventListener('click', function() {
      var code = item.dataset.code;
      document.getElementById('global-search').value = code + ' ' + item.dataset.name;
      suggestDropdown.style.display = 'none';
      window.location.hash = '#/stock/' + code;
    });
  });

  suggestDropdown.style.display = 'block';
}

function goToStock(query) {
  var match = query.match(/\d{6}/);
  if (match) window.location.hash = '#/stock/' + match[0];
}

document.addEventListener('DOMContentLoaded', function() {
  if (document.getElementById('global-search')) initSmartSearch();
});
