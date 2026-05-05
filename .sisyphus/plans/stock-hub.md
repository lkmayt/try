# Stock Hub — A股信息聚合工具 1.0

## TL;DR

> **Quick Summary**: 构建本地 Web 应用，后台定时抓取5个渠道（巨潮信息、上证互动、深证互动、韭研公社、知识星球）的帖子入 SQLite，前端提供多源 Tab 切换、中文全文搜索、关键词弹窗告警、个股详情页（TradingView K线 + 实时行情 + 相关帖子）。核心场景：盘中个股异动 → 搜一下 → 一屏看到所有渠道的相关逻辑。
> 
> **Deliverables**:
> - `E:\re0\stock-hub\` 完整 Python 项目
> - FastAPI 后端（REST API + WebSocket）
> - 原生 HTML/JS 前端（TradingView Lightweight Charts）
> - 5个信息源爬虫（巨潮/上证互动/深证互动/韭研公社/知识星球），全部 HTTP API，无需浏览器自动化
> - 行情模块（mootdx + easyquotation 双源）
> - SQLite + FTS5 中文全文搜索
> - 关键词监控 + 浏览器弹窗通知
> - pytest 测试套件（mock 所有外部 API）
> 
> **Estimated Effort**: Large
> **Parallel Execution**: YES - 5 waves
> **Critical Path**: Task 1 → Task 2 → Task 3 → Tasks 4-8 (parallel scrapers) → Task 9 → Tasks 10-11 → Tasks 12-16 (parallel frontend) → Task 17 → F1-F4

---

## Context

### Original Request
用户想构建一个A股信息聚合桌面工具。核心痛点：盘中看到个股异动想了解逻辑时，需要打开韭研公社、知识星球、微信群等多个地方搜索。希望在一个软件里搜索就能直达所有渠道的相关信息。参考了朋友的"红字快讯监控"工具（桌面应用，Tab切换源+关键词提醒+搜索）。

用户同时描述了一个完整的五层数据源架构（行情/研报/新闻/财报/公告），但确认 1.0 只做信息流+搜索+行情+K线，研报/财报/公告层延后到 2.0。

### Interview Summary

**Key Discussions**:
- **产品定位**: "大而全的股票逻辑知识库"——搜一个股票，列出所有渠道的相关帖子
- **UI选型**: Python后端 + Web前端（FastAPI + HTML/JS），浏览器打开 localhost
- **存储**: SQLite + FTS5 全文搜索
- **K线图**: TradingView Lightweight Charts（用户提到 TradingView）
- **数据流**: 后台定时拓取入库（开始/停止按钮），用户搜索查库
- **行情展示**: 个股详情页（输入股票代码 → K线+实时价+相关帖子）
- **关键词监控**: 命中时弹窗通知
- **1.0信息源**: 巨潮信息、知识星球、上证互动、深证互动、韭研公社
- **项目位置**: E:\re0\stock-hub\ 子目录
- **测试**: pytest + mock 外部 API

**Research Findings**:
- **上证互动**: AJAX API `sns.sseinfo.com/ajax/userfeeds.do`，AKShare 已集成 `ak.stock_sns_sseinfo()`
- **深证互动**: AJAX API `irm.cninfo.com.cn`，AKShare 已集成 `ak.stock_irm_cninfo()`
- **巨潮信息**: 非官方 POST API `cninfo.com.cn/new/hisAnnouncement/query`，需 Referer+UA
- **韭研公社**: REST API 已被逆向（RSSHub/LeekHub）——`app.jiuyangongshe.com/jystock-app/api/`，MD5 盐值 token 认证
- **知识星球**: REST API `api.zsxq.com`，Cookie + MD5 签名，开源项目 ZsxqCrawler 可参考
- **全景问答**: 无公开 API，需 Playwright 浏览器自动化，难度最高 → **延后到 2.0**
- **TradingView LC**: Apache 2.0 开源，CDN 引入，`series.update()` 支持 WebSocket 实时更新

### Metis Review

**Identified Gaps** (addressed):
1. **中文 FTS5 分词**: 标准 unicode61 不支持中文分词 → 使用 `simple` tokenizer（C扩展，支持中文+拼音）或 bigram 方案
2. **全景问答复杂度**: 唯一需要 Playwright 的源，显著增加复杂度 → **用户决定延后到 2.0，1.0 不做**
3. **韭研公社 token 盐值**: 固定盐值 `Uu0KfOB8iUP69d3c` 可能变化 → 抽象为配置项
4. **知识星球 Cookie 过期**: 需手动刷新 → UI 中提供 Cookie 配置入口 + 状态显示
5. **SQLite 写竞争**: 多个爬虫并发写入 → WAL 模式 + 单写入者队列
6. **数据保留策略**: 未讨论 → 默认保留90天，可配置
7. **爬虫故障隔离**: 单源故障不影响其他源 → 每源独立 try/except + UI 状态面板
8. **关键词匹配范围**: 只匹配新到帖子（实时流），不回溯历史

---

## Work Objectives

### Core Objective
构建本地 Web 应用（FastAPI + 原生 HTML/JS），后台定时抓取6个信息渠道的帖子入 SQLite，前端提供搜索、Tab 过滤、关键词弹窗告警、个股详情页（K线+行情+帖子），让用户在一个界面内完成"搜股票逻辑"的全部需求。

### Concrete Deliverables
- `E:\re0\stock-hub\` 完整项目目录
- `pyproject.toml` 项目配置（依赖管理）
- `src/stock_hub/` Python 包：scrapers/ + storage/ + api/ + quotes/ + scheduler/
- `src/stock_hub/frontend/` 静态前端文件：HTML + JS + CSS
- `config.example.toml` 配置模板
- `tests/` pytest 测试套件
- SQLite 数据库文件（自动初始化）

### Definition of Done
- [ ] `cd E:\re0\stock-hub && python -m stock_hub` 启动完整系统
- [ ] 浏览器打开 `http://localhost:8000` 看到信息流主页
- [ ] 搜索框输入"茅台" → 返回来自多个源的相关帖子
- [ ] Tab 切换过滤源（全部/巨潮/上证互动/深证互动/韭研/知识星球）
- [ ] 设定关键词"半导体" → 新帖命中时浏览器弹窗通知
- [ ] 点击股票代码/进入个股详情页 → K线图 + 实时价格 + 相关帖子
- [ ] 任一数据源故障不影响其他源运行
- [ ] `cd E:\re0\stock-hub && python -m pytest tests/ -v` 全部通过

### Must Have
- 5个信息源爬虫（巨潮/上证互动/深证互动/韭研/知识星球）
- SQLite + FTS5 中文全文搜索
- 多源 Tab 切换过滤
- 关键词监控 + 浏览器 Notification 弹窗
- 行情数据（mootdx 主 + easyquotation 备）
- TradingView Lightweight Charts K线图
- 个股详情页（K线 + 实时价 + 该股相关帖子）
- 后台定时拓取 + 开始/停止控制
- 每源独立故障隔离
- 配置文件驱动（scrape 间隔、Cookie、API Key）
- pytest 测试套件（mock 外部 API）

### Must NOT Have (Guardrails)
- ❌ 买卖建议、交易信号、自动下单——这不是交易工具
- ❌ React/Vue/Angular 等 SPA 框架——纯原生 HTML/JS
- ❌ Redis、Celery、PostgreSQL——只用 SQLite + FastAPI
- ❌ Scrapy 框架——5个源用 httpx + asyncio 足够
- ❌ 研报 PDF 下载、财报数据、公告原文（2.0）
- ❌ 全景问答爬虫（需 Playwright 浏览器自动化，延后到 2.0）
- ❌ 过度抽象/泛化设计（如通用爬虫框架）
- ❌ 知识星球/韭研的密码明文存储——敏感信息走配置文件
- ❌ 用户注册/登录系统——自己用的本地工具

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: NO（新项目）
- **Automated tests**: YES (TDD)
- **Framework**: pytest
- **Each task**: 写测试 → 写实现 → 验证通过

### QA Policy
Every task MUST include agent-executed QA scenarios。
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`。

- **Backend/API**: Bash (curl / httpx TestClient)
- **Frontend/UI**: Playwright（playwright skill）
- **WebSocket**: Custom async test client
- **Database**: pytest with in-memory SQLite
- **Scrapers**: pytest with mocked HTTP responses (fixtures)

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — start immediately):
├── Task 1: 项目脚手架 + 配置 [quick]
├── Task 2: 数据库层 + FTS5 [deep]
└── Task 3: 爬虫基础设施 [deep]

Wave 2 (Scrapers — after Wave 1, MAX PARALLEL):
├── Task 4: 上证互动爬虫 (depends: 2, 3) [quick]
├── Task 5: 深证互动爬虫 (depends: 2, 3) [quick]
├── Task 6: 巨潮信息爬虫 (depends: 2, 3) [unspecified-high]
├── Task 7: 韭研公社爬虫 (depends: 2, 3) [unspecified-high]
└── Task 8: 知识星球爬虫 (depends: 2, 3) [unspecified-high]

Wave 3 (API + Scheduler — after Wave 2):
├── Task 9: FastAPI 核心 + REST API (depends: 2) [deep]
├── Task 10: 行情模块 + WebSocket (depends: 9) [unspecified-high]
└── Task 11: 后台调度器 (depends: 3, 9) [unspecified-high]

Wave 4 (Frontend — after Wave 3, MAX PARALLEL):
├── Task 12: 前端骨架 + 布局 (depends: 9) [visual-engineering]
├── Task 13: 搜索 + 结果列表 + Tab 过滤 (depends: 12) [visual-engineering]
├── Task 14: K线图 + 个股详情页 (depends: 10, 12) [visual-engineering]
├── Task 15: 关键词监控 + 弹窗通知 (depends: 12) [visual-engineering]
└── Task 16: 数据源状态面板 + 配置页 (depends: 11, 12) [visual-engineering]

Wave 5 (Integration — after Wave 4):
└── Task 17: 端到端集成 + 入口脚本 (depends: ALL) [deep]

Wave FINAL (Review — after ALL):
├── F1: Plan compliance audit (oracle)
├── F2: Code quality review (unspecified-high)
├── F3: Real manual QA (unspecified-high + playwright)
└── F4: Scope fidelity check (deep)
-> Present results -> Get explicit user okay
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | — | 2, 3, 9, 12 | 1 |
| 2 | 1 | 4-8, 9, 13 | 1 |
| 3 | 1 | 4-8, 11 | 1 |
| 4 | 2, 3 | 11, 17 | 2 |
| 5 | 2, 3 | 11, 17 | 2 |
| 6 | 2, 3 | 11, 17 | 2 |
| 7 | 2, 3 | 11, 17 | 2 |
| 8 | 2, 3 | 11, 17 | 2 |
| 9 | 2 | 10, 11, 12-16 | 3 |
| 10 | 9 | 14, 17 | 3 |
| 11 | 3, 9 | 16, 17 | 3 |
| 12 | 9 | 13-16 | 4 |
| 13 | 12 | 17 | 4 |
| 14 | 10, 12 | 17 | 4 |
| 15 | 12 | 17 | 4 |
| 16 | 11, 12 | 17 | 4 |
| 17 | ALL | F1-F4 | 5 |

### Agent Dispatch Summary

- **Wave 1**: 3 tasks — T1 → `quick`, T2 → `deep`, T3 → `deep`
- **Wave 2**: 5 tasks — T4-5 → `quick`, T6-8 → `unspecified-high`
- **Wave 3**: 3 tasks — T9 → `deep`, T10-11 → `unspecified-high`
- **Wave 4**: 5 tasks — T12-16 → `visual-engineering`
- **Wave 5**: 1 task — T17 → `deep`
- **FINAL**: 4 tasks — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high` + `playwright`, F4 → `deep`

---

## TODOs

- [ ] 1. 项目脚手架 + 配置

  **What to do**:
  - 创建 `E:\re0\stock-hub\` 目录结构：
    ```
    stock-hub/
    ├── pyproject.toml
    ├── config.example.toml
    ├── .gitignore
    ├── README.md
    ├── src/
    │   └── stock_hub/
    │       ├── __init__.py
    │       ├── __main__.py          # entry point
    │       ├── config.py            # TOML config loader
    │       ├── scrapers/
    │       │   └── __init__.py
    │       ├── storage/
    │       │   └── __init__.py
    │       ├── api/
    │       │   └── __init__.py
    │       ├── quotes/
    │       │   └── __init__.py
    │       ├── scheduler/
    │       │   └── __init__.py
    │       └── frontend/
    │           ├── index.html       # placeholder
    │           ├── css/
    │           └── js/
    └── tests/
        ├── __init__.py
        ├── conftest.py              # shared fixtures
        └── fixtures/                # saved HTTP responses for mocking
    ```
  - `pyproject.toml`: 使用 `[project]` 标准格式，dependencies 包含：
    - `fastapi>=0.110`, `uvicorn[standard]`, `httpx`, `websockets`
    - `mootdx[all]`, `easyquotation`, `akshare`
    - `pywencai`（2.0用，先声明依赖）
    - `pytest`, `pytest-asyncio`, `pytest-httpx`（dev deps）
  - `config.example.toml`: 定义所有配置项结构（scrape intervals, cookie paths, keywords）
  - `config.py`: 用 `tomllib`（Python 3.11+）加载 TOML 配置，提供 `get_config()` 单例
  - `.gitignore`: Python标准 + `config.toml`（含敏感信息）+ `*.db` + `.pytest_cache`

  **Must NOT do**:
  - 不要安装 React/Vue/Angular
  - 不要引入 Redis/Celery
  - 不要创建 Dockerfile（本地工具）

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (foundation task)
  - **Parallel Group**: Wave 1 (sequential prerequisite)
  - **Blocks**: Tasks 2, 3, 10, 13
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `E:\re0\.sisyphus\plans\quant-trading-system.md:64-76` — 类似的 src/ 包结构和 config.yaml 设计（本项目改用 TOML）

  **External References**:
  - Python Packaging Guide: https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
  - tomllib (Python 3.11+): https://docs.python.org/3/library/tomllib.html

  **WHY Each Reference Matters**:
  - quant-trading-system 的 src 布局是用户之前同意的结构，保持一致性
  - tomllib 是标准库，零依赖配置加载

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Project structure is complete
    Tool: Bash
    Preconditions: stock-hub/ directory created
    Steps:
      1. Run `python -c "import stock_hub; print(stock_hub.__name__)"` in stock-hub/ directory
      2. Run `python -c "from stock_hub.config import get_config; print(type(get_config()))"` with config.toml present
      3. Run `ls src/stock_hub/scrapers/ src/stock_hub/storage/ src/stock_hub/api/ src/stock_hub/quotes/ src/stock_hub/scheduler/ src/stock_hub/frontend/`
    Expected Result: import succeeds printing "stock_hub"; config returns dict-like object; all 6 subdirectories exist
    Evidence: .sisyphus/evidence/task-1-project-structure.txt

  Scenario: Dependencies install correctly
    Tool: Bash
    Preconditions: pyproject.toml exists
    Steps:
      1. Run `cd E:\re0\stock-hub && pip install -e ".[dev]"` (or `pip install -e .`)
      2. Run `python -c "import fastapi, httpx, mootdx, easyquotation, akshare; print('all ok')"`
    Expected Result: Installation succeeds; all core imports work
    Evidence: .sisyphus/evidence/task-1-deps-install.txt
  ```

  **Commit**: YES
  - Message: `chore(stock-hub): project scaffold and configuration`
  - Files: `stock-hub/**`
  - Pre-commit: `python -c "from stock_hub.config import get_config"`

- [ ] 2. 数据库层 + FTS5 中文全文搜索

  **What to do**:
  - 创建 `src/stock_hub/storage/database.py`：
    - `Database` 类，管理 SQLite 连接（WAL 模式）
    - `init_db()`: 创建 schema + FTS5 虚拟表
    - `insert_post(post: Post)`: 插入帖子，去重 by (source, url) UNIQUE 约束
    - `search_posts(query: str, source: str|None, limit: int, offset: int) -> list[Post]`: FTS5 全文搜索，支持按源过滤
    - `get_posts_by_stock(stock_code: str, source: str|None) -> list[Post]`: 按股票代码查相关帖子
    - `get_recent_posts(source: str|None, limit: int) -> list[Post]`: 按时间获取最新帖子
    - `cleanup_old_posts(days: int)`: 清理 N 天前的数据
    - `get_source_stats() -> dict`: 每源帖子数+最后更新时间
  - 创建 `src/stock_hub/storage/models.py`：
    - `Post` dataclass: id, source, title, content, author, url, stock_codes(list), published_at, scraped_at, keywords_matched(list)
  - SQLite Schema:
    ```sql
    CREATE TABLE posts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      source TEXT NOT NULL,         -- 'cninfo'|'sse'|'szse'|'jiuyan'|'zsxq'
      title TEXT NOT NULL,
      content TEXT,
      author TEXT,
      url TEXT,
      stock_codes TEXT,             -- JSON array: ["600519","000001"]
      published_at TEXT,            -- ISO 8601
      scraped_at TEXT NOT NULL,
      UNIQUE(source, url)
    );
    CREATE VIRTUAL TABLE posts_fts USING fts5(
      title, content, author, stock_codes,
      content='posts',
      content_rowid='id',
      tokenize='unicode61'         -- 中文先用 unicode61 bigram workaround，或 simple tokenizer
    );
    -- 触发器: INSERT/DELETE 自动同步 FTS 索引
    CREATE TABLE keywords (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      keyword TEXT NOT NULL UNIQUE,
      created_at TEXT NOT NULL
    );
    ```
  - **中文搜索策略**: 先用 FTS5 `unicode61` tokenizer + 手动 bigram 索引（将中文文本拆成连续双字存入 FTS），无需额外 C 扩展。如果效果不好，2.0 升级为 `simple` tokenizer（需编译 C 扩展）。
  - 创建 `tests/test_storage.py`: 测试 CRUD、FTS5 搜索中文、去重、cleanup

  **Must NOT do**:
  - 不要用 SQLAlchemy ORM——直接用 sqlite3 标准库
  - 不要引入 Redis 缓存
  - 不要创建多个数据库文件

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 1)
  - **Parallel Group**: Wave 1 (after Task 1)
  - **Blocks**: Tasks 4-9, 10, 14
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `E:\re0\.sisyphus\plans\quant-trading-system.md:49` — SQLite WAL 模式设计决策

  **External References**:
  - SQLite FTS5: https://www.sqlite.org/fts5.html
  - FTS5 tokenizers: https://www.sqlite.org/fts5.html#tokenizers
  - Python sqlite3 WAL: `connection.execute("PRAGMA journal_mode=WAL")`

  **WHY Each Reference Matters**:
  - FTS5 文档是搜索功能的核心实现依据
  - WAL 模式确保多爬虫并发写入时不会锁数据库

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_storage.py -v` → PASS (≥8 tests)

  **QA Scenarios:**

  ```
  Scenario: Chinese full-text search works
    Tool: Bash (pytest)
    Preconditions: test_storage.py with Chinese text fixtures
    Steps:
      1. Insert 3 posts: one about "贵州茅台白酒", one about "宁德时代电池", one about "中芯国际半导体"
      2. Search "茅台" → expect 1 result containing "贵州茅台"
      3. Search "半导体" → expect 1 result containing "中芯国际"
      4. Search "不存在的关键词" → expect 0 results
    Expected Result: All search assertions pass
    Evidence: .sisyphus/evidence/task-2-fts5-chinese.txt

  Scenario: Deduplication works
    Tool: Bash (pytest)
    Preconditions: Empty database
    Steps:
      1. Insert post with source="cninfo", url="https://example.com/1"
      2. Insert same post again (same source+url)
      3. Query all posts → expect exactly 1
    Expected Result: Second insert ignored, no duplicate
    Evidence: .sisyphus/evidence/task-2-dedup.txt

  Scenario: Source filtering works
    Tool: Bash (pytest)
    Steps:
      1. Insert posts from 3 different sources
      2. get_recent_posts(source="cninfo") → only cninfo posts
      3. get_recent_posts(source=None) → all posts
    Expected Result: Filtering returns correct subset
    Evidence: .sisyphus/evidence/task-2-source-filter.txt
  ```

  **Commit**: YES
  - Message: `feat(storage): SQLite database layer with FTS5 Chinese search`
  - Files: `src/stock_hub/storage/*.py`, `tests/test_storage.py`
  - Pre-commit: `pytest tests/test_storage.py -v`

- [ ] 3. 爬虫基础设施

  **What to do**:
  - 创建 `src/stock_hub/scrapers/base.py`：
    - `BaseScraper` ABC:
      ```python
      class BaseScraper(ABC):
          source_name: str                          # 'cninfo'|'sse'|'szse'|...
          
          @abstractmethod
          async def fetch_latest(self, limit: int = 30) -> list[Post]: ...
          
          @abstractmethod
          async def search(self, keyword: str, limit: int = 30) -> list[Post]: ...
          
          async def scrape_and_store(self, db: Database) -> int:
              """Fetch latest → store → return count of new posts"""
      ```
    - 统一的错误处理: 单源异常 catch + log，不影响其他源
    - `ScraperRegistry`: 注册/获取所有爬虫实例的工厂
  - 创建 `src/stock_hub/scrapers/rate_limiter.py`：
    - Token bucket 限速器，每源独立配置（默认: 1 req/s）
    - `async def acquire(source: str)`: 等待直到有 token
  - 创建 `src/stock_hub/scrapers/http_client.py`：
    - 封装 `httpx.AsyncClient`，统一 headers、timeout、retry（3次指数退避）
    - 每个爬虫通过 `self.client` 使用
  - 创建 `tests/test_base_scraper.py`: 测试 BaseScraper 接口、rate limiter、retry 逻辑

  **Must NOT do**:
  - 不要引入 Scrapy
  - 不要在 base 中写具体爬虫逻辑
  - 不要创建线程池——用 asyncio

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 2, after Task 1)
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 4-9, 12
  - **Blocked By**: Task 1

  **References**:

  **External References**:
  - httpx async: https://www.python-httpx.org/async/
  - Token bucket algorithm: https://en.wikipedia.org/wiki/Token_bucket

  **WHY Each Reference Matters**:
  - httpx 是我们的 HTTP 客户端选型，需要了解 async 用法
  - Token bucket 是限速器的实现算法

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_base_scraper.py -v` → PASS (≥5 tests)

  **QA Scenarios:**

  ```
  Scenario: Rate limiter respects per-source limits
    Tool: Bash (pytest)
    Steps:
      1. Create rate limiter with limit=2 req/sec for source "test"
      2. Fire 5 requests in quick succession
      3. Measure total elapsed time
    Expected Result: Total time ≥ 2 seconds (5 reqs at 2/s = 2.5s)
    Evidence: .sisyphus/evidence/task-3-rate-limiter.txt

  Scenario: HTTP client retries on failure
    Tool: Bash (pytest)
    Steps:
      1. Mock httpx to return 500 for first 2 calls, 200 for third
      2. Call http_client.get(url)
      3. Assert final response is 200
      4. Assert 3 total attempts were made
    Expected Result: Successful response after retries
    Evidence: .sisyphus/evidence/task-3-retry.txt

  Scenario: Scraper error isolation
    Tool: Bash (pytest)
    Steps:
      1. Create two mock scrapers: one raises Exception, one returns data
      2. Run both via ScraperRegistry.scrape_all()
      3. Assert: failing scraper logged error, successful scraper's data was stored
    Expected Result: One failure doesn't crash the other
    Evidence: .sisyphus/evidence/task-3-isolation.txt
  ```

  **Commit**: YES
  - Message: `feat(scrapers): base scraper infrastructure with rate limiting`
  - Files: `src/stock_hub/scrapers/base.py`, `scrapers/rate_limiter.py`, `scrapers/http_client.py`, `tests/test_base_scraper.py`
  - Pre-commit: `pytest tests/test_base_scraper.py -v`

- [ ] 4. 上证互动爬虫（SSE Interactive）

  **What to do**:
  - 创建 `src/stock_hub/scrapers/sse_interactive.py`：
    - 继承 `BaseScraper`，`source_name = "sse"`
    - `fetch_latest()`: 调用 AKShare `ak.stock_sns_sseinfo()` 或直接请求 `http://sns.sseinfo.com/ajax/userfeeds.do`
    - `search()`: 按关键词/股票代码搜索上证互动问答
    - 解析返回的 HTML（BeautifulSoup），提取：时间、提问者、问题内容、公司回复
    - 构建 `Post` 对象，stock_codes 从公司映射表获取
  - 创建 `tests/fixtures/sse_response.html`: 保存真实响应 HTML 作为 mock fixture
  - 创建 `tests/test_sse_scraper.py`: 用 fixture mock HTTP，测试解析逻辑

  **Must NOT do**:
  - 不要在测试中发送真实 HTTP 请求

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 5-9)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 12, 18
  - **Blocked By**: Tasks 2, 3

  **References**:

  **API References**:
  - 上证互动 AJAX: `http://sns.sseinfo.com/ajax/userfeeds.do?typeCode=company&type=11&pageSize=10&uid={uid}&page=1`
  - AKShare: `ak.stock_sns_sseinfo(symbol="600000")` — 直接返回 DataFrame

  **Pattern References**:
  - AKShare 源码中 stock_sns_sseinfo 的实现模式

  **WHY Each Reference Matters**:
  - AKShare 已封装好上证互动接口，优先使用避免造轮子
  - 如果 AKShare 接口不稳定，备选直接 HTTP + BeautifulSoup 解析

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_sse_scraper.py -v` → PASS (≥3 tests)

  **QA Scenarios:**

  ```
  Scenario: Parse SSE Interactive responses correctly
    Tool: Bash (pytest)
    Preconditions: tests/fixtures/sse_response.html contains saved response
    Steps:
      1. Load fixture HTML
      2. Call scraper.parse_response(html)
      3. Assert: returned list has ≥1 Post
      4. Assert: each Post has title, content, published_at, source="sse"
    Expected Result: All posts parsed with correct fields
    Evidence: .sisyphus/evidence/task-4-sse-parse.txt

  Scenario: fetch_latest returns valid posts
    Tool: Bash (pytest)
    Steps:
      1. Mock httpx to return fixture HTML
      2. Call scraper.fetch_latest(limit=10)
      3. Assert: returned list length ≤ 10
      4. Assert: all posts have source="sse"
    Expected Result: Posts fetched and parsed correctly
    Evidence: .sisyphus/evidence/task-4-sse-fetch.txt
  ```

  **Commit**: YES
  - Message: `feat(scrapers): SSE Interactive (上证互动) via AKShare`
  - Files: `src/stock_hub/scrapers/sse_interactive.py`, `tests/test_sse_scraper.py`, `tests/fixtures/sse_response.html`
  - Pre-commit: `pytest tests/test_sse_scraper.py -v`

- [ ] 5. 深证互动爬虫（SZSE Interactive）

  **What to do**:
  - 创建 `src/stock_hub/scrapers/szse_interactive.py`：
    - 继承 `BaseScraper`，`source_name = "szse"`
    - `fetch_latest()`: 调用 AKShare `ak.stock_irm_cninfo(symbol)` 或直接请求 `http://irm.cninfo.com.cn/ircs/interaction/lastQuestionforSzseSsgs.do`
    - `search()`: 按股票代码搜索深证互动问答
    - 解析返回数据，提取：时间、提问内容、公司回复
    - 与上证互动爬虫结构高度相似，但 API 端点和解析逻辑不同
  - 创建 `tests/fixtures/szse_response.html`: 保存真实响应作为 mock fixture
  - 创建 `tests/test_szse_scraper.py`

  **Must NOT do**:
  - 不要在测试中发送真实 HTTP 请求
  - 不要和上证互动爬虫共用解析逻辑——它们的 HTML 结构不同

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 4, 6-9)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 12, 18
  - **Blocked By**: Tasks 2, 3

  **References**:

  **API References**:
  - 深证互动 API: `http://irm.cninfo.com.cn/ircs/interaction/lastQuestionforSzseSsgs.do?condition.type=2&condition.stockcode=000001`
  - AKShare: `ak.stock_irm_cninfo(symbol="000001")` 获取提问, `ak.stock_irm_ans_cninfo(symbol="000001")` 获取回答

  **WHY Each Reference Matters**:
  - AKShare 提供了深证互动的提问和回答两个独立接口

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_szse_scraper.py -v` → PASS (≥3 tests)

  **QA Scenarios:**

  ```
  Scenario: Parse SZSE Interactive responses correctly
    Tool: Bash (pytest)
    Preconditions: tests/fixtures/szse_response.html
    Steps:
      1. Load fixture
      2. Call scraper.parse_response(data)
      3. Assert: returned list has ≥1 Post with source="szse"
      4. Assert: each Post has question content and optional answer
    Expected Result: All posts parsed correctly
    Evidence: .sisyphus/evidence/task-5-szse-parse.txt
  ```

  **Commit**: YES
  - Message: `feat(scrapers): SZSE Interactive (深证互动) via AKShare`
  - Files: `src/stock_hub/scrapers/szse_interactive.py`, `tests/test_szse_scraper.py`, `tests/fixtures/szse_response.html`
  - Pre-commit: `pytest tests/test_szse_scraper.py -v`

- [ ] 6. 巨潮信息爬虫（CNInfo）

  **What to do**:
  - 创建 `src/stock_hub/scrapers/cninfo.py`：
    - 继承 `BaseScraper`，`source_name = "cninfo"`
    - `fetch_latest()`: POST `http://www.cninfo.com.cn/new/hisAnnouncement/query`
      - Headers: `User-Agent`, `X-Requested-With: XMLHttpRequest`, `Referer: http://www.cninfo.com.cn/`
      - Body: `tabName=fulltext`, `pageSize=30`, `pageNum=1`, `isHLtitle=true`
    - `search(keyword)`: 同一 API，`searchkey` 参数传关键词
    - 解析 JSON 响应，提取：announcementTitle, announcementContent (摘要), adjunctUrl (PDF链接), announcementTime
    - 构建 Post，url 为 `http://static.cninfo.com.cn/{adjunctUrl}` (公告原文链接)
    - 从公告标题中正则提取股票代码（如"贵州茅台(600519)"）
  - 创建 `tests/fixtures/cninfo_response.json`: 保存真实 JSON 响应
  - 创建 `tests/test_cninfo_scraper.py`

  **Must NOT do**:
  - 不要下载 PDF 文件（2.0 功能）
  - 不要存储公告全文——只存标题+摘要+链接

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 4-5, 7-9)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 12, 18
  - **Blocked By**: Tasks 2, 3

  **References**:

  **API References**:
  - 巨潮公告查询 API: `POST http://www.cninfo.com.cn/new/hisAnnouncement/query`
  - PDF 下载: `http://static.cninfo.com.cn/{adjunctUrl}`
  - 需要的 Headers: `Referer: http://www.cninfo.com.cn/`, `X-Requested-With: XMLHttpRequest`

  **External References**:
  - GitHub CnInfoReports: https://github.com/tr1s7an/CnInfoReports — 巨潮公告下载参考实现

  **WHY Each Reference Matters**:
  - API 端点和参数是从 Metis/Librarian 调研中确认的，CnInfoReports 提供了 Python 实现参考

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_cninfo_scraper.py -v` → PASS (≥4 tests)

  **QA Scenarios:**

  ```
  Scenario: Parse CNInfo announcement JSON correctly
    Tool: Bash (pytest)
    Preconditions: tests/fixtures/cninfo_response.json
    Steps:
      1. Load fixture JSON
      2. Call scraper.parse_response(json_data)
      3. Assert: returned list has ≥1 Post with source="cninfo"
      4. Assert: each Post has title, url (static.cninfo.com.cn/...), published_at
      5. Assert: stock_codes extracted from title (e.g., "600519" from "贵州茅台(600519)")
    Expected Result: Announcements parsed with stock codes extracted
    Evidence: .sisyphus/evidence/task-6-cninfo-parse.txt

  Scenario: Search by keyword returns filtered results
    Tool: Bash (pytest)
    Steps:
      1. Mock httpx to return fixture with keyword "半导体" in search results
      2. Call scraper.search("半导体")
      3. Assert: all returned posts relate to "半导体"
    Expected Result: Keyword search works correctly
    Evidence: .sisyphus/evidence/task-6-cninfo-search.txt
  ```

  **Commit**: YES
  - Message: `feat(scrapers): CNInfo announcements (巨潮信息)`
  - Files: `src/stock_hub/scrapers/cninfo.py`, `tests/test_cninfo_scraper.py`, `tests/fixtures/cninfo_response.json`
  - Pre-commit: `pytest tests/test_cninfo_scraper.py -v`

- [ ] 7. 韭研公社爬虫（Jiuyangongshe）

  **What to do**:
  - 创建 `src/stock_hub/scrapers/jiuyangongshe.py`：
    - 继承 `BaseScraper`，`source_name = "jiuyan"`
    - **认证**: MD5 token 签名
      ```python
      import hashlib, time
      SALT = "Uu0KfOB8iUP69d3c"  # 从 config.toml 读取，可配置
      timestamp = str(int(time.time() * 1000))
      token = hashlib.md5(f"{SALT}:{timestamp}".encode()).hexdigest()
      headers = {"platform": "3", "timestamp": timestamp, "token": token}
      ```
    - `fetch_latest()`: POST `https://app.jiuyangongshe.com/jystock-app/api/v2/article/community`
      - Body: `{"category_id":"","limit":30,"order":0,"start":1,"type":0,"back_garden":0}`
    - `search(keyword)`: POST `https://app.jiuyangongshe.com/jystock-app/api/v2/article/search`
      - Body: `{"keyword":"xxx","limit":30,"start":1}`
    - 可选: 时间轴 API `POST /v1/timeline/list`
    - 解析 JSON 响应，提取文章标题、内容摘要、作者、发布时间、相关股票
  - **盐值配置化**: SALT 写入 `config.example.toml` 的 `[scrapers.jiuyan]` 部分，方便盐值变更时快速更新
  - 创建 `tests/fixtures/jiuyan_community.json` + `jiuyan_search.json`
  - 创建 `tests/test_jiuyan_scraper.py`

  **Must NOT do**:
  - 不要硬编码盐值在代码中——放 config
  - 不要做 Selenium/Playwright 版本——有 REST API

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 4-6, 8-9)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 12, 18
  - **Blocked By**: Tasks 2, 3

  **References**:

  **API References**:
  - 社群文章: `POST https://app.jiuyangongshe.com/jystock-app/api/v2/article/community`
  - 搜索: `POST https://app.jiuyangongshe.com/jystock-app/api/v2/article/search`
  - 时间轴: `POST https://app.jiuyangongshe.com/jystock-app/api/v1/timeline/list`
  - 认证 Headers: `platform: "3"`, `timestamp: <ms>`, `token: md5("Uu0KfOB8iUP69d3c:<timestamp>")`

  **External References**:
  - RSSHub 韭研实现: https://github.com/DIYgod/RSSHub `lib/routes/jiuyangongshe/community.tsx` — 最完整的 API 逆向工程
  - LeekHub search: https://github.com/LeekHub/leek-fund `src/webview/jiuyangongshe-news.ts` — 搜索 API 实现
  - go-stock timeline: https://github.com/ArvinLovegood/go-stock `backend/data/market_news_api.go:1079` — 时间轴 API Go 实现

  **WHY Each Reference Matters**:
  - RSSHub 提供了最完整的 API 逆向（认证方式、请求体、响应格式）
  - LeekHub 的搜索接口是从另一个角度实现的，可交叉验证
  - go-stock 展示了时间轴 API 的用法

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_jiuyan_scraper.py -v` → PASS (≥4 tests)

  **QA Scenarios:**

  ```
  Scenario: Token generation matches expected format
    Tool: Bash (pytest)
    Steps:
      1. Call generate_token() with fixed timestamp 1714800000000
      2. Assert: returned token is 32-char hex string (MD5)
      3. Assert: token matches md5("Uu0KfOB8iUP69d3c:1714800000000")
    Expected Result: Token generation is deterministic and correct
    Evidence: .sisyphus/evidence/task-7-jiuyan-token.txt

  Scenario: Parse community articles correctly
    Tool: Bash (pytest)
    Preconditions: tests/fixtures/jiuyan_community.json
    Steps:
      1. Load fixture JSON
      2. Call scraper.parse_community_response(json_data)
      3. Assert: returned list has ≥1 Post with source="jiuyan"
      4. Assert: each Post has title, content, author, published_at
    Expected Result: Articles parsed correctly
    Evidence: .sisyphus/evidence/task-7-jiuyan-parse.txt

  Scenario: Search API returns keyword-relevant results
    Tool: Bash (pytest)
    Steps:
      1. Mock httpx with fixture search response for "茅台"
      2. Call scraper.search("茅台")
      3. Assert: all returned posts contain "茅台" in title or content
    Expected Result: Search returns relevant results
    Evidence: .sisyphus/evidence/task-7-jiuyan-search.txt
  ```

  **Commit**: YES
  - Message: `feat(scrapers): Jiuyangongshe (韭研公社) REST API`
  - Files: `src/stock_hub/scrapers/jiuyangongshe.py`, `tests/test_jiuyan_scraper.py`, `tests/fixtures/jiuyan_*.json`
  - Pre-commit: `pytest tests/test_jiuyan_scraper.py -v`

- [ ] 8. 知识星球爬虫（Zsxq）

  **What to do**:
  - 创建 `src/stock_hub/scrapers/zsxq.py`：
    - 继承 `BaseScraper`，`source_name = "zsxq"`
    - **认证**: Cookie (`zsxq_access_token`) + MD5 签名
      ```python
      SECRET = "zsxqapi2020"
      # 签名: path + sorted_params + secret → MD5
      ```
    - Cookie 从 `config.toml` 的 `[scrapers.zsxq]` 读取
    - `fetch_latest()`: GET `https://api.zsxq.com/v2/groups/{group_id}/topics?count=20&scope=all`
    - `search()`: 知识星球搜索能力有限，改为本地 FTS5 搜索（数据入库后搜）
    - 支持多个星球 group（从 config 读 group_id 列表）
    - 解析 topic 数据：text content、images（只存URL）、files（只存URL）、create_time
    - 处理 topic 内的 stock mentions（正则提取股票代码）
  - **Cookie 过期处理**: 请求返回 401 时标记 status="cookie_expired"，在 UI 状态面板显示
  - 创建 `tests/fixtures/zsxq_topics.json`
  - 创建 `tests/test_zsxq_scraper.py`

  **Must NOT do**:
  - 不要实现自动登录/获取 Cookie——手动从浏览器复制
  - 不要存储图片/文件内容——只存 URL
  - 不要爬取非已加入的星球

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 4-7, 9)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 12, 18
  - **Blocked By**: Tasks 2, 3

  **References**:

  **API References**:
  - 星球列表: `GET https://api.zsxq.com/v2/groups?count=50`
  - 主题列表: `GET https://api.zsxq.com/v2/groups/{group_id}/topics?count=20&scope=all`
  - 签名密钥: `zsxqapi2020`
  - Headers: `Origin: https://wx.zsxq.com`, `Referer: https://wx.zsxq.com/`

  **External References**:
  - ZsxqCrawler: https://github.com/2977094657/ZsxqCrawler — 可视化工具，完整 API 实现
  - zsxq-spider: https://github.com/wbsabc/zsxq-spider — 经典项目

  **WHY Each Reference Matters**:
  - ZsxqCrawler 有最新的 API 端点和签名算法实现，直接参考避免反复调试

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_zsxq_scraper.py -v` → PASS (≥4 tests)

  **QA Scenarios:**

  ```
  Scenario: Signature generation is correct
    Tool: Bash (pytest)
    Steps:
      1. Call generate_signature(path="/v2/groups", params={"count":"50"}, timestamp="1714800000000")
      2. Assert: returned signature is 32-char hex MD5
      3. Assert: matches manually computed md5(path + & + sorted_params + & + "zsxqapi2020")
    Expected Result: Signature matches expected value
    Evidence: .sisyphus/evidence/task-8-zsxq-signature.txt

  Scenario: Parse topic data correctly
    Tool: Bash (pytest)
    Preconditions: tests/fixtures/zsxq_topics.json
    Steps:
      1. Load fixture
      2. Call scraper.parse_topics(data)
      3. Assert: ≥1 Post returned with source="zsxq"
      4. Assert: text content extracted, create_time parsed to ISO format
    Expected Result: Topics parsed into Posts
    Evidence: .sisyphus/evidence/task-8-zsxq-parse.txt

  Scenario: Cookie expiration detected
    Tool: Bash (pytest)
    Steps:
      1. Mock httpx to return 401 status
      2. Call scraper.fetch_latest()
      3. Assert: raises CookieExpiredError or returns empty list with status logged
    Expected Result: 401 handled gracefully, not crash
    Evidence: .sisyphus/evidence/task-8-zsxq-cookie-expired.txt
  ```

  **Commit**: YES
  - Message: `feat(scrapers): Zsxq (知识星球) REST API`
  - Files: `src/stock_hub/scrapers/zsxq.py`, `tests/test_zsxq_scraper.py`, `tests/fixtures/zsxq_topics.json`
  - Pre-commit: `pytest tests/test_zsxq_scraper.py -v`

- [ ] 9. FastAPI 核心 + REST API

  **What to do**:
  - 创建 `src/stock_hub/api/app.py`：
    - FastAPI 应用实例，挂载静态文件（frontend/）
    - CORS 中间件（localhost）
    - lifespan 中初始化 Database，关闭时 cleanup
  - 创建 `src/stock_hub/api/routes.py`：
    - `GET /api/health` → `{"status":"ok","sources":{"cninfo":{"last_scrape":"...","count":N,"status":"active"},...}}`
    - `GET /api/search?q={query}&source={source}&limit=20&offset=0` → `{"results":[Post...],"total":N}`
    - `GET /api/posts/recent?source={source}&limit=50` → `{"posts":[Post...]}`
    - `GET /api/stocks/{code}` → `{"code":"600519","name":"贵州茅台","posts":[...]}`
    - `GET /api/keywords` → 获取所有关键词
    - `POST /api/keywords` → 添加关键词 `{"keyword":"半导体"}`
    - `DELETE /api/keywords/{id}` → 删除关键词
    - `GET /api/sources` → 获取所有数据源配置和状态
  - 创建 `src/stock_hub/api/schemas.py`：Pydantic models for request/response
  - 创建 `tests/test_api.py`：用 `httpx.AsyncClient` + `app=app` 测试所有端点

  **Must NOT do**:
  - 不要用 Jinja2 模板——纯 API + 静态文件
  - 不要创建用户认证系统
  - 不要使用 SQLAlchemy

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 2)
  - **Parallel Group**: Wave 3
  - **Blocks**: Tasks 11, 12, 13-17
  - **Blocked By**: Task 2

  **References**:

  **Pattern References**:
  - `E:\re0\.sisyphus\plans\quant-trading-system.md:61-68` — FastAPI + SSE Dashboard 架构（本项目用 WebSocket 替代 SSE）

  **External References**:
  - FastAPI TestClient: https://fastapi.tiangolo.com/tutorial/testing/
  - FastAPI StaticFiles: https://fastapi.tiangolo.com/tutorial/static-files/

  **WHY Each Reference Matters**:
  - quant-trading-system 中的 FastAPI 模式是同一用户之前同意的架构
  - StaticFiles 用来直接 serve 前端 HTML/JS/CSS

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_api.py -v` → PASS (≥8 tests)

  **QA Scenarios:**

  ```
  Scenario: Health endpoint returns source status
    Tool: Bash (curl)
    Preconditions: Server running on localhost:8000
    Steps:
      1. curl http://localhost:8000/api/health
      2. Assert: response status 200
      3. Assert: JSON has "status":"ok" and "sources" object with keys for each source
    Expected Result: Health check returns structured status
    Evidence: .sisyphus/evidence/task-10-health.txt

  Scenario: Search returns Chinese results
    Tool: Bash (curl)
    Preconditions: Database has posts with Chinese content
    Steps:
      1. curl "http://localhost:8000/api/search?q=茅台&limit=5"
      2. Assert: response status 200
      3. Assert: JSON has "results" array with ≥1 item containing "茅台"
      4. Assert: JSON has "total" field (integer)
    Expected Result: Chinese search returns relevant posts
    Evidence: .sisyphus/evidence/task-10-search.txt

  Scenario: Invalid stock code returns 404
    Tool: Bash (curl)
    Steps:
      1. curl http://localhost:8000/api/stocks/999999
      2. Assert: response status 404
      3. Assert: JSON has "detail" field with error message
    Expected Result: Graceful 404 for unknown stock
    Evidence: .sisyphus/evidence/task-10-stock-404.txt

  Scenario: Keyword CRUD works
    Tool: Bash (curl)
    Steps:
      1. POST /api/keywords body={"keyword":"半导体"} → 201, returns {id, keyword}
      2. GET /api/keywords → list includes "半导体"
      3. DELETE /api/keywords/{id} → 204
      4. GET /api/keywords → list no longer includes "半导体"
    Expected Result: Full CRUD lifecycle works
    Evidence: .sisyphus/evidence/task-10-keywords-crud.txt
  ```

  **Commit**: YES
  - Message: `feat(api): FastAPI core with search and stock endpoints`
  - Files: `src/stock_hub/api/*.py`, `tests/test_api.py`
  - Pre-commit: `pytest tests/test_api.py -v`

- [ ] 10. 行情模块 + WebSocket 实时推送

  **What to do**:
  - 创建 `src/stock_hub/quotes/provider.py`：
    - `QuoteProvider` 类：
      - `get_realtime_quote(code: str) -> Quote`: 获取单股实时行情
      - `get_batch_quotes(codes: list[str]) -> list[Quote]`: 批量获取
      - `get_kline(code: str, frequency: str, count: int) -> list[Candle]`: K线数据
    - 双源策略: mootdx 为主，easyquotation（腾讯）为备
      ```python
      try:
          data = await self._mootdx_quote(code)
      except Exception:
          data = await self._tencent_quote(code)
      ```
    - `Quote` dataclass: code, name, price, change, change_pct, volume, amount, high, low, open, prev_close
    - `Candle` dataclass: time, open, high, low, close, volume
  - 创建 `src/stock_hub/quotes/stock_info.py`：
    - 股票代码 → 名称映射（akshare `stock_zh_a_spot_em()` 缓存，每日更新一次）
    - 股票代码 → 交易所映射（6xxxxx=SH, 0/3xxxxx=SZ）
  - 创建 `src/stock_hub/api/ws.py`：
    - WebSocket endpoint: `ws://localhost:8000/ws/quotes/{code}`
    - `ConnectionManager`: 管理连接，广播行情更新
    - 后台 asyncio task: 每 5 秒从 QuoteProvider 拉数据，推送给已连接客户端
    - 心跳检测: 30秒无消息发 ping，清理死连接
  - 创建 `tests/test_quotes.py` + `tests/test_ws.py`

  **Must NOT do**:
  - 不要每秒拉一次行情——5秒间隔足够（避免被封）
  - 不要对全市场股票推送——只推送客户端订阅的股票

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 12)
  - **Parallel Group**: Wave 3
  - **Blocks**: Tasks 15, 18
  - **Blocked By**: Task 10

  **References**:

  **API References**:
  - mootdx: `Quotes.factory(market='std').quotes(symbol=['000001','600300'])` — 批量实时行情
  - mootdx: `Quotes.factory(market='std').bars(symbol='600036', frequency=9, offset=100)` — K线数据
  - easyquotation: `easyquotation.use('tencent').real(['000001','600519'])` — 腾讯实时行情备选
  - 腾讯HTTP: `https://web.sqt.gtimg.cn/q=sh600519` — 直接 HTTP 备选

  **External References**:
  - FastAPI WebSocket: https://fastapi.tiangolo.com/advanced/websockets/
  - mootdx docs: https://mootdx.readthedocs.io/

  **WHY Each Reference Matters**:
  - mootdx 和 easyquotation 是用户指定的行情数据双源
  - FastAPI WebSocket 文档指导 ConnectionManager 实现

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_quotes.py -v` → PASS (≥4 tests)
  - [ ] `pytest tests/test_ws.py -v` → PASS (≥3 tests)

  **QA Scenarios:**

  ```
  Scenario: Quote provider returns valid data
    Tool: Bash (pytest)
    Steps:
      1. Mock mootdx client to return fixture quote data
      2. Call provider.get_realtime_quote("600519")
      3. Assert: Quote has code="600519", price > 0, name is not empty
    Expected Result: Quote data returned with all fields
    Evidence: .sisyphus/evidence/task-11-quote-provider.txt

  Scenario: Fallback to Tencent when mootdx fails
    Tool: Bash (pytest)
    Steps:
      1. Mock mootdx to raise ConnectionError
      2. Mock easyquotation to return valid data
      3. Call provider.get_realtime_quote("600519")
      4. Assert: Quote returned successfully (from Tencent source)
    Expected Result: Fallback works transparently
    Evidence: .sisyphus/evidence/task-11-quote-fallback.txt

  Scenario: K-line data formatted for TradingView
    Tool: Bash (pytest)
    Steps:
      1. Mock mootdx.bars() with fixture DataFrame
      2. Call provider.get_kline("600519", "daily", 100)
      3. Assert: list of Candle dicts with keys: time, open, high, low, close, volume
      4. Assert: time format is "YYYY-MM-DD" (TradingView requirement)
    Expected Result: K-line data ready for TradingView chart
    Evidence: .sisyphus/evidence/task-11-kline-format.txt
  ```

  **Commit**: YES
  - Message: `feat(quotes): market data module with WebSocket streaming`
  - Files: `src/stock_hub/quotes/*.py`, `src/stock_hub/api/ws.py`, `tests/test_quotes.py`, `tests/test_ws.py`
  - Pre-commit: `pytest tests/test_quotes.py tests/test_ws.py -v`

- [ ] 11. 后台调度器 + 健康监控

  **What to do**:
  - 创建 `src/stock_hub/scheduler/scheduler.py`：
    - `ScrapeScheduler` 类：管理所有爬虫的定时执行
    - 使用 `asyncio` 循环（不引入 APScheduler）：
      ```python
      async def run_scraper_loop(scraper: BaseScraper, interval_seconds: int):
          while self.running:
              try:
                  count = await scraper.scrape_and_store(self.db)
                  self.update_source_status(scraper.source_name, "active", count)
              except Exception as e:
                  self.update_source_status(scraper.source_name, "error", str(e))
              await asyncio.sleep(interval_seconds)
      ```
    - `start()`: 启动所有爬虫循环（每源一个 asyncio.Task）
    - `stop()`: 取消所有 Task
    - 从 config.toml 读取每源的 scrape interval（默认: 60秒）
    - **关键词匹配**: 每次入库新帖后，检查是否命中关键词列表，命中则通过 WebSocket 推送告警
  - 创建 `src/stock_hub/scheduler/keyword_matcher.py`：
    - `match_keywords(post: Post, keywords: list[str]) -> list[str]`: 返回命中的关键词列表
    - 匹配标题 + 内容
  - 创建 `src/stock_hub/scheduler/status.py`：
    - `SourceStatus` dataclass: source_name, status, last_scrape_time, post_count, error_message
    - 供 /api/health 和前端状态面板使用
  - 集成到 FastAPI lifespan: 启动时 start(), 关闭时 stop()
  - 创建 `tests/test_scheduler.py`

  **Must NOT do**:
  - 不要引入 APScheduler/Celery——纯 asyncio
  - 不要在调度器里直接发邮件/微信通知——通过 WebSocket 推到前端

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 11)
  - **Parallel Group**: Wave 3
  - **Blocks**: Tasks 17, 18
  - **Blocked By**: Tasks 3, 10

  **References**:

  **Pattern References**:
  - `E:\re0\.sisyphus\plans\quant-trading-system.md:30-33` — 消息爬虫的定时循环 + 降级策略

  **WHY Each Reference Matters**:
  - quant-trading-system 有类似的多源定时爬取+降级模式，可参考故障隔离策略

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_scheduler.py -v` → PASS (≥4 tests)

  **QA Scenarios:**

  ```
  Scenario: Keyword matching detects hits
    Tool: Bash (pytest)
    Steps:
      1. Create keywords: ["茅台", "半导体"]
      2. Create post with title="贵州茅台业绩大增"
      3. Call match_keywords(post, keywords)
      4. Assert: returns ["茅台"]
    Expected Result: Keyword match correctly identified
    Evidence: .sisyphus/evidence/task-12-keyword-match.txt

  Scenario: Scheduler starts and stops cleanly
    Tool: Bash (pytest)
    Steps:
      1. Create mock scrapers (instant return, no real HTTP)
      2. Start scheduler with 1-second interval
      3. Wait 3 seconds
      4. Stop scheduler
      5. Assert: each scraper was called ≥2 times
      6. Assert: no background tasks leaked (all cancelled)
    Expected Result: Clean lifecycle with no leaks
    Evidence: .sisyphus/evidence/task-12-scheduler-lifecycle.txt

  Scenario: Source failure doesn't stop other scrapers
    Tool: Bash (pytest)
    Steps:
      1. Create 3 mock scrapers: scraper_a (OK), scraper_b (raises Exception), scraper_c (OK)
      2. Start scheduler, wait 3 seconds, stop
      3. Assert: scraper_a and scraper_c each called ≥2 times
      4. Assert: scraper_b status is "error" with error message
    Expected Result: Failure isolation works
    Evidence: .sisyphus/evidence/task-12-failure-isolation.txt
  ```

  **Commit**: YES
  - Message: `feat(scheduler): background scrape scheduler with health monitoring`
  - Files: `src/stock_hub/scheduler/*.py`, `tests/test_scheduler.py`
  - Pre-commit: `pytest tests/test_scheduler.py -v`

- [ ] 12. 前端骨架 + 布局

  **What to do**:
  - 创建 `src/stock_hub/frontend/index.html`：主页面
    - 暗色主题（深蓝/深灰背景，白色文字，参考截图风格）
    - 顶部导航栏: 搜索框 + 关键词输入 + 开始/停止按钮
    - Tab 栏: 全部 | 巨潮 | 上证互动 | 深证互动 | 韭研公社 | 知识星球
    - 主内容区: 帖子列表表格（时间 | 来源 | 标题 | 关键词命中）
    - 底部状态栏: 数据源状态指示灯 + TradingView attribution
  - 创建 `src/stock_hub/frontend/stock.html`：个股详情页
    - 股票代码输入/跳转
    - K线图区域（TradingView 容器）
    - 实时行情数据面板
    - 该股相关帖子列表
  - 创建 `src/stock_hub/frontend/css/style.css`：
    - 暗色主题变量: `--bg-primary: #1a1a2e`, `--bg-secondary: #16213e`, `--text: #e0e0e0`, `--accent: #0f3460`
    - Tab 样式: 激活态高亮（蓝色），类似截图
    - 表格样式: 紧凑行高，hover 高亮
    - 响应式: 最小宽度 1024px
  - 创建 `src/stock_hub/frontend/js/app.js`：
    - 全局路由: SPA-like 页面切换（hash-based: `#/`, `#/stock/600519`）
    - API 请求封装: `api.get()`, `api.post()`, `api.delete()`
    - WebSocket 连接管理
    - 共用的 DOM 操作工具函数

  **Must NOT do**:
  - 不要使用 React/Vue/Angular/Svelte
  - 不要用 Tailwind/Bootstrap CSS 框架——手写 CSS
  - 不要引入 TypeScript 构建步骤——纯 JS

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 10)
  - **Parallel Group**: Wave 4 (foundation)
  - **Blocks**: Tasks 14-17
  - **Blocked By**: Task 10

  **References**:

  **Pattern References**:
  - 用户截图（红字快讯监控）: Tab切换、表格列（时间|来源|标题|识别原因）、开始/停止按钮、搜索框
  - `E:\re0\.sisyphus\plans\quant-trading-system.md:79` — `dashboard.html` SSE Dashboard 设计（本项目用 WebSocket）

  **External References**:
  - TradingView Lightweight Charts CDN: `https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js`

  **WHY Each Reference Matters**:
  - 用户截图定义了 UI 的目标体验——Tab 式信息流切换
  - quant-trading-system 中的 dashboard 可参考布局思路

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Main page renders correctly
    Tool: Playwright
    Preconditions: Server running on localhost:8000
    Steps:
      1. Navigate to http://localhost:8000
      2. Assert: page title contains "Stock Hub"
      3. Assert: search input exists (selector: input#search-input or input[type="search"])
      4. Assert: tab bar exists with ≥7 tabs (全部, 巨潮, 上证互动, etc.)
      5. Assert: start/stop button exists
      6. Take screenshot
    Expected Result: Main page renders with all UI elements
    Evidence: .sisyphus/evidence/task-13-main-page.png

  Scenario: Stock detail page renders
    Tool: Playwright
    Steps:
      1. Navigate to http://localhost:8000#/stock/600519
      2. Assert: chart container exists (selector: #chart-container or div[data-chart])
      3. Assert: stock info panel exists showing code "600519"
      4. Assert: related posts section exists
      5. Take screenshot
    Expected Result: Stock detail page layout is complete
    Evidence: .sisyphus/evidence/task-13-stock-page.png

  Scenario: Dark theme is applied
    Tool: Playwright
    Steps:
      1. Navigate to http://localhost:8000
      2. Get computed background-color of body
      3. Assert: background is dark (#1a1a2e or similar dark color, not white)
      4. Get computed color of text elements
      5. Assert: text is light (#e0e0e0 or similar light color)
    Expected Result: Dark theme applied consistently
    Evidence: .sisyphus/evidence/task-13-dark-theme.png
  ```

  **Commit**: YES
  - Message: `feat(frontend): HTML/CSS layout with tab navigation`
  - Files: `src/stock_hub/frontend/*.html`, `frontend/css/style.css`, `frontend/js/app.js`
  - Pre-commit: —

- [ ] 13. 搜索 + 结果列表 + Tab 过滤

  **What to do**:
  - 创建 `src/stock_hub/frontend/js/search.js`：
    - 搜索框 keydown Enter → `GET /api/search?q={query}&source={activeTab}`
    - 实时搜索（debounce 300ms，输入停止后自动搜索）
    - 结果渲染为表格行: 时间 | 来源（带颜色标签） | 标题 | 关键词命中（高亮）
    - 点击行 → 展开详情（标题+正文摘要，命中词高亮）
    - 帖子中的股票代码自动变为可点击链接 → 跳转个股详情页
  - 创建 `src/stock_hub/frontend/js/tabs.js`：
    - Tab 切换: 点击 Tab → 过滤结果列表（调 API 带 source 参数 或本地过滤）
    - 激活态样式切换
    - "全部" Tab 显示所有源
  - 创建 `src/stock_hub/frontend/js/posts.js`：
    - `GET /api/posts/recent?source={tab}` → 默认信息流（无搜索时显示最新帖子）
    - 无限滚动或分页加载
    - 来源标签颜色映射: cninfo=红, sse=蓝, szse=绿, jiuyan=橙, zsxq=紫, p5w=青

  **Must NOT do**:
  - 不要做复杂的排序功能（时间倒序足够）
  - 不要做帖子收藏/点赞功能

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 15-17, after Task 13)
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 18
  - **Blocked By**: Task 13

  **References**:

  **Pattern References**:
  - 用户截图: 表格列布局（时间|来源|标题|识别原因）、选中行展开详情

  **API References**:
  - `GET /api/search?q={query}&source={source}&limit=20&offset=0` — Task 10 定义的搜索 API
  - `GET /api/posts/recent?source={source}&limit=50` — Task 10 定义的最新帖子 API

  **WHY Each Reference Matters**:
  - API 端点在 Task 10 中已定义，前端调用需要匹配

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Search returns and displays results
    Tool: Playwright
    Preconditions: Database has posts containing "茅台"
    Steps:
      1. Navigate to http://localhost:8000
      2. Type "茅台" into search input
      3. Press Enter or wait 300ms
      4. Assert: results table has ≥1 row
      5. Assert: first result contains text "茅台" (highlighted)
      6. Take screenshot
    Expected Result: Search results rendered with highlighting
    Evidence: .sisyphus/evidence/task-14-search-results.png

  Scenario: Tab filtering works
    Tool: Playwright
    Preconditions: Database has posts from multiple sources
    Steps:
      1. Navigate to http://localhost:8000
      2. Click "巨潮" tab
      3. Assert: all visible rows have source="cninfo" label
      4. Click "全部" tab
      5. Assert: rows from multiple sources visible
    Expected Result: Tab switching filters correctly
    Evidence: .sisyphus/evidence/task-14-tab-filter.png

  Scenario: Click post row expands detail
    Tool: Playwright
    Steps:
      1. Navigate to http://localhost:8000 (with posts loaded)
      2. Click first row in results table
      3. Assert: detail panel appears below/beside the row
      4. Assert: detail panel shows title + content excerpt
      5. Assert: stock codes in content are clickable links
    Expected Result: Post detail expansion works
    Evidence: .sisyphus/evidence/task-14-post-detail.png
  ```

  **Commit**: YES
  - Message: `feat(frontend): search results with source tab filtering`
  - Files: `src/stock_hub/frontend/js/search.js`, `js/tabs.js`, `js/posts.js`
  - Pre-commit: —

- [ ] 14. TradingView K线图 + 个股详情页

  **What to do**:
  - 创建 `src/stock_hub/frontend/js/chart.js`：
    - 引入 TradingView Lightweight Charts（CDN `<script>` 标签在 stock.html 中）
    - `initChart(containerId)`: 创建暗色主题 chart
      ```javascript
      const chart = LightweightCharts.createChart(container, {
          layout: { background: { color: '#1a1a2e' }, textColor: '#e0e0e0' },
          grid: { vertLines: { color: '#2a2a3e' }, horzLines: { color: '#2a2a3e' } },
      });
      ```
    - 添加 CandlestickSeries（上涨绿#26a69a，下跌红#ef5350——A股习惯是红涨绿跌，调整为: 上涨红#ef5350，下跌绿#26a69a）
    - 添加 HistogramSeries 成交量（overlay 底部30%）
    - 添加 LineSeries MA5/MA10/MA20 均线
    - `loadStock(code)`: `fetch(/api/stocks/{code}/kline)` → `setData()`
    - WebSocket 连接: `ws://localhost:8000/ws/quotes/{code}` → `series.update()`
    - 股票切换: 输入框改变 → 断开旧 WS → loadStock(newCode) → 连接新 WS
  - 完善 `src/stock_hub/frontend/stock.html`：
    - 股票搜索/切换输入框
    - 实时行情面板: 当前价、涨跌幅、成交量、成交额、最高、最低
    - K线图容器（宽度100%，高度400px）
    - 相关帖子列表（复用 search.js 的渲染逻辑，过滤 stock_code）
  - 添加后端 API：
    - `GET /api/stocks/{code}/kline?frequency=daily&count=200` → K线数据（TradingView 格式）

  **Must NOT do**:
  - 不要使用 TradingView Widget（iframe）——用 Lightweight Charts 本地库
  - 不要忘记 TradingView attribution（页面底部加链接）
  - 不要做分钟级 K线（1.0 只做日K）

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 14, 16-17)
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 18
  - **Blocked By**: Tasks 11, 13

  **References**:

  **External References**:
  - TradingView Lightweight Charts CDN: `https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js`
  - TradingView CandlestickSeries: `chart.addSeries(LightweightCharts.CandlestickSeries, { upColor, downColor })`
  - TradingView HistogramSeries (volume): `chart.addSeries(LightweightCharts.HistogramSeries, { priceFormat: { type: 'volume' }, priceScaleId: '' })`
  - TradingView real-time: `series.update({ time, open, high, low, close })`
  - License: Apache 2.0, 需要 attribution link to https://www.tradingview.com/

  **API References**:
  - K线数据: `GET /api/stocks/{code}/kline` → `[{time:"2024-01-01",open:100,high:105,low:98,close:103,volume:1234},...]`
  - WebSocket: `ws://localhost:8000/ws/quotes/{code}` → Task 11 定义

  **WHY Each Reference Matters**:
  - TradingView LC 是用户选择的K线方案，CDN引入最简单
  - A股颜色习惯（红涨绿跌）与国际惯例相反，必须特别注意

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: K-line chart renders with data
    Tool: Playwright
    Preconditions: Server running, mootdx quote provider mocked
    Steps:
      1. Navigate to http://localhost:8000#/stock/600519
      2. Wait for chart container to have child elements (canvas)
      3. Assert: chart canvas exists within #chart-container
      4. Assert: stock info panel shows "600519" and "贵州茅台"
      5. Take screenshot
    Expected Result: K-line chart rendered with candles
    Evidence: .sisyphus/evidence/task-15-kline-chart.png

  Scenario: Stock switching updates chart
    Tool: Playwright
    Steps:
      1. Navigate to http://localhost:8000#/stock/600519
      2. Wait for chart to render
      3. Change stock input to "000001"
      4. Press Enter
      5. Wait for chart to update
      6. Assert: stock info panel now shows "000001"
      7. Take screenshot
    Expected Result: Chart reloaded with new stock data
    Evidence: .sisyphus/evidence/task-15-stock-switch.png

  Scenario: Related posts shown for stock
    Tool: Playwright
    Preconditions: Database has posts mentioning stock 600519
    Steps:
      1. Navigate to http://localhost:8000#/stock/600519
      2. Scroll to related posts section
      3. Assert: ≥1 post visible with content related to 600519
    Expected Result: Related posts displayed below chart
    Evidence: .sisyphus/evidence/task-15-related-posts.png
  ```

  **Commit**: YES
  - Message: `feat(frontend): TradingView K-line chart and stock detail page`
  - Files: `src/stock_hub/frontend/js/chart.js`, `frontend/stock.html`, `src/stock_hub/api/routes.py` (add kline endpoint)
  - Pre-commit: `pytest tests/test_api.py -v`

- [ ] 15. 关键词监控 + 弹窗通知

  **What to do**:
  - 创建 `src/stock_hub/frontend/js/keywords.js`：
    - 关键词管理 UI:
      - 输入框 + "添加" 按钮 → `POST /api/keywords`
      - 已有关键词列表，每个带"删除"按钮 → `DELETE /api/keywords/{id}`
    - 关键词告警 WebSocket:
      - 连接 `ws://localhost:8000/ws/alerts`
      - 收到告警消息时:
        1. 浏览器 Notification API 弹窗: `new Notification("关键词命中: {keyword}", { body: "{post.title}" })`
        2. 表格中该行高亮闪烁
        3. 播放提示音（可选，Web Audio API）
    - 首次使用时请求 Notification 权限: `Notification.requestPermission()`
  - 后端补充:
    - `ws://localhost:8000/ws/alerts` WebSocket endpoint（在 api/ws.py 中添加）
    - 调度器每次发现关键词命中时，通过此 WS 广播告警消息
    - 告警消息格式: `{"type":"keyword_alert","keyword":"茅台","post":{"title":"...","source":"jiuyan","url":"..."}}`

  **Must NOT do**:
  - 不要做邮件/微信/飞书通知——只用浏览器 Notification
  - 不要做正则匹配——简单 `keyword in (title + content)` 即可

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 14-15, 17)
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 18
  - **Blocked By**: Task 13

  **References**:

  **External References**:
  - Browser Notification API: https://developer.mozilla.org/en-US/docs/Web/API/Notification

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Add and delete keywords via UI
    Tool: Playwright
    Steps:
      1. Navigate to http://localhost:8000
      2. Type "半导体" into keyword input
      3. Click "添加" button
      4. Assert: "半导体" appears in keyword list
      5. Click delete button next to "半导体"
      6. Assert: "半导体" removed from list
    Expected Result: Keyword CRUD works via UI
    Evidence: .sisyphus/evidence/task-16-keyword-crud.png

  Scenario: Alert triggers on keyword match
    Tool: Playwright
    Steps:
      1. Add keyword "测试关键词"
      2. Trigger mock post with title containing "测试关键词"
      3. Assert: WebSocket receives alert with type="keyword_alert"
    Expected Result: Alert delivered via WebSocket
    Evidence: .sisyphus/evidence/task-16-keyword-alert.txt
  ```

  **Commit**: YES
  - Message: `feat(frontend): keyword monitor with browser notifications`
  - Files: `src/stock_hub/frontend/js/keywords.js`, `src/stock_hub/api/ws.py`
  - Pre-commit: `pytest tests/test_api.py -v`

- [ ] 16. 数据源状态面板 + 配置页

  **What to do**:
  - 创建 `src/stock_hub/frontend/js/status.js`：
    - 底部状态栏: 每源一个指示灯（绿=活跃, 黄=等待, 红=错误）
    - 点击展开详细面板: 每源名称、状态、最后抓取时间、帖子数、错误信息
    - 开始/停止按钮控制调度器
    - 轮询 `GET /api/health` 每 10 秒更新
  - 创建 `src/stock_hub/frontend/config.html`（或模态弹窗）：
    - 知识星球 Cookie 配置输入框
    - 各源 scrape interval 调整
    - 数据保留天数设置
  - 后端补充:
    - `POST /api/config/{source}` → 更新配置
    - `POST /api/scheduler/start` / `stop` → 控制调度器

  **Must NOT do**:
  - 不要做 OAuth 登录流程

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 14-16)
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 18
  - **Blocked By**: Tasks 12, 13

  **References**:

  **Pattern References**:
  - 用户截图: 顶部"开始/停止"按钮

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: Status indicators display correctly
    Tool: Playwright
    Steps:
      1. Navigate to http://localhost:8000
      2. Assert: status bar at bottom with ≥5 indicators
      3. Click to expand status panel
      4. Assert: each source shows last scrape time
      5. Take screenshot
    Expected Result: Status panel renders with per-source info
    Evidence: .sisyphus/evidence/task-17-status-panel.png

  Scenario: Start/stop scheduler via UI
    Tool: Playwright
    Steps:
      1. Click "停止" button → indicators turn yellow
      2. Click "开始" button → indicators turn green
    Expected Result: Scheduler control works
    Evidence: .sisyphus/evidence/task-17-scheduler-control.png
  ```

  **Commit**: YES
  - Message: `feat(frontend): source status dashboard and config page`
  - Files: `src/stock_hub/frontend/js/status.js`, `frontend/config.html`, `src/stock_hub/api/routes.py`
  - Pre-commit: —

- [ ] 17. 端到端集成 + 入口脚本

  **What to do**:
  - 完善 `src/stock_hub/__main__.py`：
    ```python
    """python -m stock_hub"""
    import uvicorn
    from stock_hub.config import get_config
    
    def main():
        config = get_config()
        uvicorn.run("stock_hub.api.app:app",
            host=config.get("server", {}).get("host", "127.0.0.1"),
            port=config.get("server", {}).get("port", 8000))
    
    if __name__ == "__main__":
        main()
    ```
  - 完善 `src/stock_hub/api/app.py` lifespan：
    - startup: init_db → register scrapers → start scheduler → start WS managers
    - shutdown: stop scheduler → close DB → close httpx clients → close Playwright
  - 端到端验证: 从零启动 → 自动建库 → 爬虫抓取 → 搜索返回结果 → K线加载
  - 创建 `tests/test_integration.py`: 完整流程测试（mock 外部 API，真实 SQLite）

  **Must NOT do**:
  - 不要添加 Docker 配置
  - 不要修改已完成模块（除集成修复）

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: [`playwright`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 5
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 1-17

  **References**:

  **Pattern References**:
  - 所有前序 Task 的 API/WS 端点

  **Acceptance Criteria**:
  - [ ] `python -m stock_hub` → server starts without errors
  - [ ] `python -m pytest tests/ -v` → ALL PASS

  **QA Scenarios:**

  ```
  Scenario: Full system startup from clean state
    Tool: Bash
    Steps:
      1. Delete stock_hub.db if exists
      2. Copy config.example.toml to config.toml
      3. Run `python -m stock_hub` (background)
      4. Wait 10 seconds
      5. curl http://localhost:8000/api/health → status 200, all sources listed
    Expected Result: System starts from scratch
    Evidence: .sisyphus/evidence/task-18-clean-startup.txt

  Scenario: End-to-end search after scraping
    Tool: Playwright
    Steps:
      1. Navigate to http://localhost:8000
      2. Wait 60 seconds for first scrape
      3. Check ≥1 source green in status bar
      4. Search a keyword → results appear
    Expected Result: Full pipeline: scrape → store → search → display
    Evidence: .sisyphus/evidence/task-18-e2e-search.png

  Scenario: Stock detail with live data
    Tool: Playwright
    Steps:
      1. Navigate to http://localhost:8000#/stock/600519
      2. Wait for K-line chart canvas
      3. Assert: price > 0 in info panel
      4. Wait 10s → price updates (WebSocket working)
    Expected Result: K-line + live price end-to-end
    Evidence: .sisyphus/evidence/task-18-stock-detail.png
  ```

  **Commit**: YES
  - Message: `feat(stock-hub): end-to-end integration and entry point`
  - Files: `__main__.py`, `main.py`, `api/app.py`, `tests/test_integration.py`
  - Pre-commit: `python -m pytest tests/ -v`

---

## Final Verification Wave

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, curl endpoint, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in `.sisyphus/evidence/`. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run linter + `python -m pytest tests/ -v`. Review all changed files for: `# type: ignore`, empty catches, print() in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names (data/result/item/temp). Verify all scrapers implement `BaseScraper` interface consistently.
  Output: `Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high` (+ `playwright` skill)
  Start from clean state (`python -m stock_hub`). Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration: search returns results from multiple scrapers, stock detail page shows K-line + posts. Test edge cases: empty search, invalid stock code, source down. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff. Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

| # | Message | Files | Pre-commit |
|---|---------|-------|------------|
| 1 | `chore(stock-hub): project scaffold and configuration` | pyproject.toml, src/stock_hub/**, config.example.toml, .gitignore | — |
| 2 | `feat(storage): SQLite database layer with FTS5 Chinese search` | storage/*.py, tests/test_storage.py | pytest tests/test_storage.py |
| 3 | `feat(scrapers): base scraper infrastructure with rate limiting` | scrapers/base.py, scrapers/rate_limiter.py, tests/test_base_scraper.py | pytest tests/ |
| 4 | `feat(scrapers): SSE Interactive (上证互动) via AKShare` | scrapers/sse_interactive.py, tests/test_sse.py, fixtures/ | pytest tests/ |
| 5 | `feat(scrapers): SZSE Interactive (深证互动) via AKShare` | scrapers/szse_interactive.py, tests/test_szse.py, fixtures/ | pytest tests/ |
| 6 | `feat(scrapers): CNInfo announcements (巨潮信息)` | scrapers/cninfo.py, tests/test_cninfo.py, fixtures/ | pytest tests/ |
| 7 | `feat(scrapers): Jiuyangongshe (韭研公社) REST API` | scrapers/jiuyangongshe.py, tests/test_jiuyan.py, fixtures/ | pytest tests/ |
| 8 | `feat(scrapers): Zsxq (知识星球) REST API` | scrapers/zsxq.py, tests/test_zsxq.py, fixtures/ | pytest tests/ |
| 9 | `feat(api): FastAPI core with search and stock endpoints` | api/*.py, tests/test_api.py | pytest tests/ |
| 10 | `feat(quotes): market data module with WebSocket streaming` | quotes/*.py, tests/test_quotes.py | pytest tests/ |
| 11 | `feat(scheduler): background scrape scheduler with health monitoring` | scheduler/*.py, tests/test_scheduler.py | pytest tests/ |
| 12 | `feat(frontend): HTML/CSS layout with tab navigation` | frontend/*.html, frontend/css/, frontend/js/ | — |
| 13 | `feat(frontend): search results with source tab filtering` | frontend/js/search.js, frontend/js/results.js | — |
| 14 | `feat(frontend): TradingView K-line chart and stock detail page` | frontend/js/chart.js, frontend/stock.html | — |
| 15 | `feat(frontend): keyword monitor with browser notifications` | frontend/js/keywords.js, api endpoints | pytest tests/ |
| 16 | `feat(frontend): source status dashboard and config page` | frontend/js/status.js, frontend/config.html | — |
| 17 | `feat(stock-hub): end-to-end integration and entry point` | __main__.py, main.py | pytest tests/ -v |

---

## Success Criteria

### Verification Commands
```bash
cd E:\re0\stock-hub
python -m pytest tests/ -v                           # Expected: ALL PASS
python -m stock_hub &                                 # Expected: server starts on :8000
curl http://localhost:8000/api/health                  # Expected: {"status":"ok","sources":{...}}
curl "http://localhost:8000/api/search?q=茅台"        # Expected: {"results":[...],"total":N}
curl http://localhost:8000/api/stocks/600519           # Expected: {"code":"600519","name":"贵州茅台",...}
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
- [ ] All 5 scrapers independently operational
- [ ] FTS5 Chinese search returns relevant results
- [ ] K-line chart renders with real data
- [ ] Keyword alert popup fires on match
