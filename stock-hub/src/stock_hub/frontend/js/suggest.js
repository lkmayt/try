// Stock search autocomplete via backend proxy (bypasses CORS)
var _suggestTimer = null;
var _suggestDropdown = null;

function initSmartSearch() {
  var input = document.getElementById('global-search');
  if (!input) return;

  _suggestDropdown = document.createElement('div');
  _suggestDropdown.className = 'suggest-dropdown';
  _suggestDropdown.style.display = 'none';
  input.parentElement.appendChild(_suggestDropdown);

  input.addEventListener('input', function() {
    clearTimeout(_suggestTimer);
    var q = input.value.trim();
    if (q.length < 1) { _suggestDropdown.style.display = 'none'; return; }
    _suggestTimer = setTimeout(function() { fetchSuggestions(q); }, 200);
  });

  input.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') _suggestDropdown.style.display = 'none';
  });

  input.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
      var firstItem = _suggestDropdown.querySelector('.suggest-item');
      if (firstItem && _suggestDropdown.style.display !== 'none') {
        firstItem.click();
        e.preventDefault();
      } else {
        _suggestDropdown.style.display = 'none';
        goToStock(input.value.trim());
      }
    }
  });

  var btn = document.getElementById('global-search-btn');
  if (btn) btn.addEventListener('click', function() { goToStock(input.value.trim()); });

  document.addEventListener('click', function(e) {
    if (!input.contains(e.target) && !_suggestDropdown.contains(e.target)) {
      _suggestDropdown.style.display = 'none';
    }
  });
}

function fetchSuggestions(keyword) {
  fetch('/api/suggest?q=' + encodeURIComponent(keyword))
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(data) {
      var items = data && data.suggestions ? data.suggestions : [];
      if (items.length === 0) { _suggestDropdown.style.display = 'none'; return; }
      renderDropdown(items);
    })
    .catch(function() { _suggestDropdown.style.display = 'none'; });
}

function renderDropdown(items) {
  _suggestDropdown.innerHTML = items.slice(0, 8).map(function(item) {
    var code = item.code || '';
    var name = item.name || '';
    var pinyin = (item.pinyin || '').toUpperCase();
    return '<div class="suggest-item" data-code="' + code + '">' +
      '<span class="suggest-name">' + name + '</span>' +
      '<span class="suggest-code">' + code + '</span>' +
      (pinyin ? '<span class="suggest-abbr">' + pinyin + '</span>' : '') +
      '</div>';
  }).join('');

  _suggestDropdown.querySelectorAll('.suggest-item').forEach(function(item) {
    item.addEventListener('click', function() {
      var code = item.dataset.code;
      document.getElementById('global-search').value = code + ' ' + item.querySelector('.suggest-name').textContent;
      _suggestDropdown.style.display = 'none';
      window.location.hash = '#/stock/' + code;
    });
  });

  _suggestDropdown.style.display = 'block';
}

function goToStock(query) {
  var match = query.match(/\d{6}/);
  if (match) window.location.hash = '#/stock/' + match[0];
}

document.addEventListener('DOMContentLoaded', function() {
  if (document.getElementById('global-search')) initSmartSearch();
});
