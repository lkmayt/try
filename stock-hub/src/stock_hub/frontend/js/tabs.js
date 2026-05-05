let activeSource = 'all';

function getActiveSource() { return activeSource; }

function initTabs() {
  const tabs = document.querySelectorAll('#tabs .tab');
  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      tabs.forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');
      activeSource = tab.dataset.source || 'all';
      const searchInput = document.querySelector('#content-search');
      if (searchInput && searchInput.value.trim()) {
        doSearch(searchInput.value.trim());
      } else {
        loadRecentPosts(activeSource);
      }
    });
  });
}

document.addEventListener('DOMContentLoaded', initTabs);
