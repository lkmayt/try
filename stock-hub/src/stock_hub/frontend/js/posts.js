// Posts rendering with keyword highlighting and auto-refresh
let currentOffset = 0;
let currentSearchQuery = '';
let refreshTimer = null;

function highlightText(text, query) {
  if (!query || !text) return text || '';
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const regex = new RegExp(`(${escaped})`, 'gi');
  return text.replace(regex, '<mark class="search-highlight">$1</mark>');
}

function renderPosts(posts) {
  const tbody = document.querySelector('#posts-table tbody');
  const emptyRow = document.querySelector('#posts-empty');
  if (!tbody) return;

  tbody.innerHTML = '';

  if (emptyRow) emptyRow.style.display = posts.length ? 'none' : '';

  if (posts.length === 0) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 4;
    cell.style.cssText = 'text-align:center;padding:40px;color:var(--text-secondary)';
    cell.textContent = currentSearchQuery 
      ? `未找到包含"${currentSearchQuery}"的帖子` 
      : '暂无数据，请点击"开始"启动数据抓取';
    row.appendChild(cell);
    tbody.appendChild(row);
    return;
  }

  posts.forEach((post) => {
    const row = document.createElement('tr');
    row.className = 'post-row';

    // Time cell — format properly
    const timeCell = document.createElement('td');
    timeCell.className = 'post-time';
    const ts = post.published_at || '';
    timeCell.textContent = ts.length >= 10 ? ts.slice(0, 16).replace('T', ' ') : ts;

    // Source cell with colored badge
    const sourceCell = document.createElement('td');
    const sourceInfo = formatSource(post.source);
    const tag = document.createElement('span');
    tag.className = `source-tag ${sourceInfo.class}`;
    tag.textContent = sourceInfo.name;
    sourceCell.appendChild(tag);

    // Title cell — highlight keywords
    const titleCell = document.createElement('td');
    titleCell.className = 'post-title';
    titleCell.innerHTML = highlightText(post.title || '(无标题)', currentSearchQuery);

    // Keywords cell
    const kwCell = document.createElement('td');
    kwCell.className = 'post-keywords';
    kwCell.textContent = '';

    row.append(timeCell, sourceCell, titleCell, kwCell);

    // Expandable detail on click
    row.addEventListener('click', () => {
      const detail = row.nextElementSibling;
      if (detail && detail.classList.contains('detail-panel')) {
        detail.remove();
        return;
      }

      const detailRow = document.createElement('tr');
      detailRow.className = 'detail-panel';
      const detailCell = document.createElement('td');
      detailCell.colSpan = 4;

      let content = (post.content || '').substring(0, 800);
      content = highlightText(content, currentSearchQuery);
      content = content.replace(/(\d{6})/g, '<a href="#/stock/$1" class="stock-link">$1</a>');
      const title = highlightText(post.title || '(无标题)', currentSearchQuery);

      detailCell.innerHTML = '<strong style="font-size:15px">' + title + '</strong><br><br>' + content;

      if (post.url) {
        detailCell.innerHTML += '<br><br><a href="' + post.url + '" target="_blank" class="stock-link">查看原文 →</a>';
      }

      detailRow.appendChild(detailCell);
      row.after(detailRow);
    });

    tbody.appendChild(row);
  });
}

async function loadRecentPosts(source) {
  const sourceParam = source && source !== 'all' ? `&source=${source}` : '';
  const data = await api.get(`/posts/recent?limit=50${sourceParam}`);
  currentOffset = 0;
  renderPosts(data.posts || []);
}

// Auto-refresh posts every 30 seconds
function startAutoRefresh(source) {
  stopAutoRefresh();
  refreshTimer = setInterval(() => {
    loadRecentPosts(source);
  }, 30000);
}

function stopAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
}
