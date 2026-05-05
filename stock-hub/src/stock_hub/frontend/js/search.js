// Search with debounce and keyword highlighting
let searchTimer = null;

async function doSearch(query) {
  currentSearchQuery = query;
  const source = getActiveSource();
  const sourceParam = source && source !== 'all' ? `&source=${source}` : '';
  const data = await api.get(`/search?q=${encodeURIComponent(query)}&limit=30${sourceParam}`);
  renderPosts(data.results || []);
}

function initSearch() {
  const input = document.querySelector('#content-search');
  if (!input) return;

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      clearTimeout(searchTimer);
      const q = input.value.trim();
      if (q) {
        doSearch(q);
      } else {
        currentSearchQuery = '';
        loadRecentPosts(getActiveSource());
      }
    }
  });

  input.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      const q = input.value.trim();
      if (q) {
        doSearch(q);
      } else {
        currentSearchQuery = '';
        loadRecentPosts(getActiveSource());
      }
    }, 300);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  initSearch();
  currentSearchQuery = '';
  loadRecentPosts('all');
  startAutoRefresh('all');
});
