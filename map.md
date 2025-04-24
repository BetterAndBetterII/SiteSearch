# SiteSearch 技术构建方案

## 一、项目目录树

```
SiteSearch/
├── deploy/
│   ├── docker-compose.yml
│   ├── Dockerfile.web
│   ├── Dockerfile.worker
│   └── nginx.conf
├── docs/
│   ├── architecture.md
│   ├── api_reference.md
│   └── deployment_guide.md
├── scripts/
│   ├── init_db.sql
│   └── manage_worker.sh
├── src/
│   ├── backend/
│   │   ├── sitesearch/
│   │   │   ├── asgi.py
│   │   │   ├── settings.py
│   │   │   ├── urls.py
│   │   │   ├── wsgi.py
│   │   │   ├── handler.py                     # Handler工厂和基类
│   │   │   ├── manager.py                     # 多进程管理器
│   │   │   └── examples/
│   │   │       └── multiprocessing_manager_example.py  # 管理器示例
│   │   ├── crawler/
│   │   │   ├── firecrawl_worker.py
│   │   │   ├── httpx_worker.py
│   │   │   ├── handler.py                     # 爬虫handler实现
│   │   │   └── __init__.py
│   │   ├── cleaner/
│   │   │   ├── markdown_converter.py
│   │   │   ├── handler.py                     # 清洗器handler实现
│   │   │   └── __init__.py
│   │   ├── storage/
│   │   │   ├── models.py
│   │   │   ├── utils.py
│   │   │   ├── handler.py                     # 存储器handler实现
│   │   │   └── __init__.py
│   │   ├── indexer/
│   │   │   ├── llama_index_worker.py
│   │   │   ├── handler.py                     # 索引器handler实现
│   │   │   └── __init__.py
│   │   └── tasks/
│   │       ├── scheduler.py
│   │       └── __init__.py
│   └── frontend/
│       ├── static/
│       ├── templates/
│       │   └── index.html
│       └── views.py
├── tests/
│   ├── crawler/
│   ├── cleaner/
│   ├── storage/
│   └── indexer/
├── requirements.txt
└── README.md
```

## 二、项目地图（架构图）

```
用户 ──→ Web界面(Django + Daphne ASGI)
            │
            ├─ 配置站点 (正则/前缀匹配)                  ┌──> 语义问答接口 ──┐
            │            │                            │                   │
            │            ▼                            │                   ▼
            │  多进程管理器(MultiProcessSiteSearchManager) │          Agent 智能问答
            │      /      |       |       \           │          /    │    \
            │     /       |       |        \          │         /     │     \
            │    ▼        ▼       ▼         ▼         │        ▼      ▼      ▼
            │爬虫Handler 清洗Handler 存储Handler 索引Handler  │   Optimizer Analyzer 多轮对话
            │(并行进程)  (并行进程)  (并行进程)  (并行进程)   │   (提示词优化)(查询分析)(深度思考)
            │    |        |        |          |        │        │      │       │
            │    ▼        ▼        ▼          ▼        │        │      │       │
            │URL队列 → 爬取队列 → 清洗队列 → 索引队列────┘        │      │       │
            │(Redis)   (Redis)   (Redis)    (Redis)            │      │       │
            │    |        |        |          |                 │      │       │
            │    ▼        ▼        ▼          ▼                 │      │       │
            │爬取内容   格式化文本  PostgreSQL  Milvus向量库 ─────┼──────┘       │
            │                                /    \            │              │
            │                               /      \           │              │
            └───────────────────────→ 搜索端点      RAG接口 ────┘              │
                                       │                                     │
                                       ▼                                     │
                                    文本搜索 ─────────────────────────────────┘
```

## 三、开发指南

### 环境准备
- Python 3.10+
- Docker & Docker Compose
- Redis 7+
- PostgreSQL 15+
- Milvus VectorDB

### 项目安装
```bash
# 克隆项目
git clone your_repo_url
cd SiteSearch

# 安装依赖
pip install -r requirements.txt

# 初始化数据库
psql -U postgres < scripts/init_db.sql

# 启动服务
cd deploy
docker-compose up -d
```

### 启动 Worker
```bash
# 使用多进程管理器启动所有worker
python src/backend/sitesearch/examples/multiprocessing_manager_example.py \
  --crawler-workers 8 \
  --cleaner-workers 2 \
  --storage-workers 2 \
  --indexer-workers 8 \
  --site-id cuhksz \
  --base-url https://www.cuhk.edu.cn \
  --max-urls 1000 \
  --max-depth 3
```

### 多进程管理器使用
- 通过单一脚本控制完整流水线处理
- 自动监控所有队列和进程状态
- 支持通过命令行参数配置worker数量和爬取规则
- 提供Python API进行编程控制
```python
# 示例Python代码：
from src.backend.sitesearch.manager import MultiProcessSiteSearchManager

# 创建管理器实例
manager = MultiProcessSiteSearchManager(
    redis_url="redis://localhost:6379/0",
    milvus_uri="http://localhost:19530"
)

# 初始化组件配置
manager.initialize_components(
    crawler_config={
        "base_url": "https://example.com",
        "regpattern": r"https://(.*\.example\.com).*"
    }
)

# 启动worker进程
manager.start_workers(
    crawler_workers=4,
    cleaner_workers=2,
    storage_workers=2,
    indexer_workers=4
)

# 添加URL到爬取队列
manager.add_url_to_queue("https://example.com", "example")

# 启动监控
manager.start_monitoring()

# 优雅关闭（通常在退出前调用）
# manager.shutdown()
```

### Web界面
- Django 后端提供站点配置与 Worker 调度接口。
- 前端提供站点添加界面，URL规则配置，实时查看爬取与索引进度。

### 定时任务
- Django 内置 `Celery beat` 或 `APScheduler` 执行定期抓取。
- 热更新数据自动触发索引器。

### 监控与管理
- 多进程管理器内置监控功能，实时显示队列状态与进程健康
- 监控数据包括：
  - 各队列的待处理/处理中/已完成/失败任务数量
  - 各组件活跃进程数量与健康状态
  - 系统资源使用情况(CPU/内存)
- 支持通过监控数据触发自动告警
- 可以与Prometheus + Grafana集成进行高级监控
- 后期将扩展到API形式，支持Web管理界面的进程与队列管理

### 单元测试与集成测试
- 使用 `pytest` 和 Django 测试框架编写单元测试。
- 集成测试覆盖从爬取到索引全流程。

### CI/CD 流程
- GitHub Actions 执行自动化测试。
- Docker Hub 或私有Registry自动构建镜像。
- 部署脚本自动更新线上环境。

## 四、技术栈总结
- **后端框架**: Django (ASGI Daphne)
- **队列**: Redis
- **爬虫**: Firecrawl, Httpx
- **数据清洗**: MarkdownConverter
- **数据库**: PostgreSQL
- **索引与搜索**: Llama-index, Redis(Doc), Milvus(Vector)
- **AI问答**: OpenAI API, GPT-4o/GPT-4o-mini, Optimizer, Analyzer
- **多轮对话**: 上下文管理, 深度思考, RAG技术
- **部署与扩展**: Docker, Docker Compose, Docker Swarm

## 五、具体实施步骤

0. **数据流转结构**：
    - 在以下所有组件之间流转的统一数据结构（每个阶段都新增内容，但不删改内容）：
    - {  
         <!-- 基础信息 -->
         "url": "页面URL",
         "content": "页面内容（纯文本或二进制）",
         "clean_content": "清洗后的内容（纯文本Markdown）",
         "status_code": 200,
         "headers": {"响应头字典"},
         "timestamp": 1234567890,
         "links": ["提取的链接列表"],
         "mimetype": "内容类型",
         "metadata": {
            "title": "页面标题",
            "description": "页面描述",
            "keywords": "关键词",
            "source": "域名来源",
            "og_title": "Open Graph标题",
            "og_description": "Open Graph描述",
            "meta_description": "Meta描述",
            "meta_keywords": "Meta关键词",
            "headings_h1": ["H1标题列表"],
            "headings_h2": ["H2标题列表"],
            "images": [{"src": "图片URL", "alt": "图片描述"}]
         },
         <!-- 爬虫相关 -->
         "content_hash": "内容哈希值(用于去重和变更检测)",
         "crawler_id": "爬虫ID",
         "crawler_type": "爬虫类型",
         "crawler_config": "爬虫配置",
         "site_id": "站点ID",
         <!-- 版本控制 -->
         "created_at": "创建时间",
         "updated_at": "更新时间",
         "version": "版本号",
         "index_operation": "索引操作：new/edit/delete",
      }

1. **共用队列管理器**
   - 1.1 设计统一的队列接口，支持 Redis 作为后端
     - 核心接口
       ```python
       # 队列任务状态
       TaskStatus: PENDING, PROCESSING, COMPLETED, FAILED, RETRY
       
       # 队列指标数据类
       QueueMetrics:
         - queue_name: str
         - pending_tasks: int
         - processing_tasks: int
         - completed_tasks: int
         - failed_tasks: int
         - avg_processing_time: float
       
       # 接口方法
       QueueManager:
         - enqueue(queue_name, task_data, task_id=None) -> str  # 任务入队
         - dequeue(queue_name, block=True, timeout=0) -> dict   # 任务出队
         - complete_task(queue_name, task_id, result=None)      # 标记任务完成
         - fail_task(queue_name, task_id, error, retry=False)   # 标记任务失败
         - get_task_status(task_id) -> dict                     # 获取任务状态
         - get_queue_metrics(queue_name) -> QueueMetrics        # 获取队列指标
         - clear_queue(queue_name) -> bool                      # 清空队列
         - get_queue_length(queue_name) -> int                  # 获取队列长度
         - process_queue(queue_name, processor, max_tasks=None) # 批量处理队列任务
       ```
     - 单例模式实现
       ```python
       get_queue_manager(redis_url=None) -> QueueManager  # 获取全局单例
       ```
   - 1.2 实现任务入队、出队和状态追踪方法
     - 任务元数据结构设计
       ```json
       {
         "id": "唯一任务ID",
         "queue": "队列名称",
         "status": "任务状态",
         "data": "任务数据",
         "created_at": "创建时间戳",
         "updated_at": "更新时间戳",
         "started_at": "开始处理时间戳",
         "completed_at": "完成时间戳",
         "error": "错误信息",
         "retry_count": "重试次数",
         "result": "处理结果"
       }
       ```
     - Redis键设计模式
       ```
       队列: sitesearch:queue:{queue_name}
       处理中: sitesearch:processing:{queue_name}
       已完成: sitesearch:completed:{queue_name}
       失败: sitesearch:failed:{queue_name}
       元数据: sitesearch:task:meta:{task_id}
       统计: sitesearch:stats:{queue_name}
       ```
   - 1.3 实现队列健康监控和指标收集
     - 监控器接口
       ```python
       QueueMonitor:
         - start()                                          # 启动监控
         - stop()                                           # 停止监控
         - add_alert_callback(callback)                     # 添加告警回调
         - get_queue_health(queue_name) -> QueueHealthStatus  # 获取健康状态
         - get_all_queue_health() -> dict                   # 获取所有队列健康状态
         - get_metrics_history(queue_name) -> list          # 获取指标历史记录
         - get_summary_report() -> dict                     # 获取摘要报告
       ```
     - 健康状态数据类
       ```python
       QueueHealthStatus:
         - queue_name: str              # 队列名称
         - is_healthy: bool             # 健康状态
         - pending_tasks: int           # 等待任务数
         - processing_tasks: int        # 处理中任务数
         - completed_tasks: int         # 完成任务数
         - failed_tasks: int            # 失败任务数
         - avg_processing_time: float   # 平均处理时间
         - last_activity_time: float    # 最后活动时间
         - stalled: bool                # 是否停滞
         - backlog_size_warning: bool   # 积压警告
         - error_rate_warning: bool     # 错误率警告
         - message: str                 # 状态消息
       ```
     - 监控告警机制
       ```python
       # 告警回调函数签名
       callback_function(QueueHealthStatus) -> None
       
       # 告警触发条件
       - 队列积压任务过多(> max_pending_threshold)
       - 队列错误率过高(> max_error_rate)
       - 队列处理活动长时间无变化(> activity_timeout)
       ```
   - 1.4 编写队列管理器单元测试
     - 测试用例覆盖
       - 任务入队与出队
       - 任务状态变更
       - 队列统计信息获取
       - 异常情况处理
       - 并发安全性测试
       - 监控告警触发
       - Redis连接断开恢复

2. **数据爬取器**
   - 2.1 实现基于 Firecrawl 的高性能爬虫
     - 支持并发控制和请求限速
     - 实现 URL 过滤规则（正则/前缀匹配）
     - 添加网站地图（sitemap.xml）自动发现
     - 核心接口设计
       ```python
       BaseCrawler:  # 爬虫基类
         - __init__(base_url, max_urls, max_depth, ...)  # 初始化爬虫配置
         - crawl() -> Dict[str, Any]                     # 开始爬取
         - crawl_page(url) -> Dict[str, Any]             # 爬取单个页面
         - extract_links(url, html_content) -> List[str] # 从HTML提取链接
         - add_url(url, depth=0)                         # 添加URL到队列
         - is_valid_url(url) -> bool                     # 检查URL是否有效
         - discover_sitemap() -> List[str]               # 发现网站地图
         - stop()                                        # 停止爬取
         - close()                                       # 关闭爬虫资源
         - get_status() -> Dict[str, Any]                # 获取爬虫状态
       ```
     - 数据格式设计
       ```json
       {
         "url": "页面URL",
         "content": "页面内容（纯文本或二进制）",
         "status_code": 200,
         "headers": {"响应头字典"},
         "timestamp": 1234567890,
         "links": ["提取的链接列表"],
         "mimetype": "内容类型",
         "metadata": {
           "title": "页面标题",
           "description": "页面描述",
           "keywords": "关键词",
           "source": "域名来源",
           "og_title": "Open Graph标题",
           "og_description": "Open Graph描述",
           "meta_description": "Meta描述",
           "meta_keywords": "Meta关键词",
           "headings_h1": ["H1标题列表"],
           "headings_h2": ["H2标题列表"],
           "images": [{"src": "图片URL", "alt": "图片描述"}]
         },
         "content_hash": "内容哈希值(用于去重和变更检测)",
         "crawler_id": "爬虫ID",
         "crawler_type": "爬虫类型",
         "crawler_config": "爬虫配置",
         "site_id": "站点ID",
       }
       ```
     - 队列任务格式
       ```json
       {
         "task": "crawl_page",
         "url": "要爬取的URL",
         "depth": 0,
         "parent_url": "来源URL",
         "site_id": "站点ID",
         "priority": 1,
         "retry_count": 0,
         "options": {
           "timeout": 30,
           "force_update": false
         }
       }
       ```
   - 2.2 实现基于 Httpx 的备选爬虫
     - 爬虫管理器接口设计
       ```python
       CrawlerManager:
         - create_crawler(crawler_id, crawler_type, base_url, config) -> str  # 创建爬虫
         - start_crawler(crawler_id, discover_sitemap) -> bool                # 启动爬虫
         - stop_crawler(crawler_id) -> bool                                   # 停止爬虫
         - get_crawler_status(crawler_id) -> dict                             # 获取爬虫状态
         - get_all_crawler_statuses() -> dict                                 # 获取所有爬虫状态
         - delete_crawler(crawler_id) -> bool                                 # 删除爬虫
         - save_results(crawler_id, file_format) -> str                       # 保存爬虫结果
         - clear_results(crawler_id) -> bool                                  # 清除爬虫结果
         - get_crawler_results(crawler_id) -> list                            # 获取爬虫结果
         - wait_for_crawler(crawler_id, timeout) -> bool                      # 等待爬虫完成
         - close()                                                           # 关闭管理器
       ```
     - 队列选择
       ```
       推荐使用"sitesearch:queue:crawl"作为爬虫队列名称
       - 爬虫任务队列: sitesearch:queue:crawl
       - 爬虫结果队列: sitesearch:queue:clean (直接连接到清洗器队列)
       - 爬虫失败队列: sitesearch:queue:crawl_failed (用于重试失败任务)
       - 高优先级队列: sitesearch:queue:crawl_priority (用于优先处理特定任务)
       ```
   - 2.3 实现爬虫状态监控和错误处理
     - 爬虫状态数据结构
       ```json
       {
         "id": "爬虫ID",
         "type": "爬虫类型(httpx/firecrawl)",
         "base_url": "起始URL",
         "status": "状态(created/running/completed/error/stopped)",
         "created_at": "创建时间",
         "stats": {
           "pages_crawled": 0,
           "pages_failed": 0,
           "start_time": "开始时间",
           "end_time": "结束时间",
           "total_time": "总耗时(秒)",
           "urls_per_second": 0.0,
           "average_page_size": 0,
           "memory_usage": 0
         },
         "config": {"爬虫配置"},
         "error": "错误信息(如果有)"
       }
       ```
     - 错误处理策略
       ```
       1. 连接错误: 自动重试3次，间隔递增
       2. 超时错误: 自动重试2次，增加超时时间
       3. HTTP 5xx错误: 延迟后重试
       4. HTTP 4xx错误: 记录错误不重试(除了429)
       5. 解析错误: 记录错误，尝试备选解析方法
       6. 严重错误: 记录详细错误堆栈，通知管理员
       ```
     - 监控指标收集
       ```
       - 爬虫吞吐量(URLs/秒)
       - 平均响应时间
       - 内存使用情况
       - 错误率和类型分布
       - 队列积压情况
       - 最近爬取的URLs列表
       ```

3. **数据清洗器**
   - 3.1 实现 HTML 到 Markdown 的转换器
     - 支持基础格式（标题、列表、表格）保留
     - 实现图片和链接处理
   - 3.2 实现 PDF，Word，Excel，PPT，Zip，等文件的清洗器
   - 3.3 实现内容提取算法，过滤导航栏和页脚
   - 3.4 添加特殊字符和编码处理
   - 3.5 不重复清理：content_hash如果存在于数据库，则不重复清理！

4. **数据库存储器**
   - 4.1 设计 PostgreSQL 数据模型
     - 文档：就是上面完整的流转数据字典
     - 站点：不存储！后面django管理
     - 爬取历史：存储，用户回溯版本
     - 索引和约束优化
   - 4.2 如果同一个url，content_hash变化：
      - content_hash变化：则表明更新了，则存储新内容，并新增一条记录。
      - 新增content_hash：则表明新增，则存储新内容，并新增一条记录。
   - 4.3 添加数据版本控制和变更追踪
   - 4.4 将新内容传递给索引器（数据流转的格式不变）

5. **索引器**
   - 5.1 集成 Llama-index 框架
     - 实现文档分块和向量化
     - 配置 Milvus 向量存储
   - 5.2 存储content_hash，实现增量索引更新机制（index_operation）
   - 5.3 添加文本搜索和语义搜索接口
   - 5.4 编写索引器单元测试

6. **Docker Swarm 扩缩容**（弃用，改用直接多进程）
   <!-- - 6.1 设计容器化服务架构
     - Web 服务、爬虫、清洗器、索引器分离
   - 6.2 编写 Docker Compose 和 Swarm 配置
   - 6.3 实现自动扩缩容规则和脚本
   - 6.4 添加容器健康检查和故障恢复
   - 6.5 编写部署和回滚脚本 -->
   - 6.1 多进程管理器实现
     - 设计基于进程的流水线架构
       ```python
       MultiProcessSiteSearchManager:
         - __init__(redis_url, milvus_uri=None)                 # 初始化管理器
         - initialize_components(...)                          # 初始化组件配置
         - start_workers(crawler_workers, cleaner_workers, ...) # 启动工作进程
         - start_monitoring()                                  # 开始系统监控
         - stop_monitoring()                                   # 停止监控
         - add_url_to_queue(url, site_id)                      # 添加URL到爬取队列
         - shutdown()                                          # 关闭所有资源和进程
       ```
     - 组件进程与Handler设计
       ```python
       # 组件worker进程函数
       component_worker(component_type, redis_url, milvus_uri, worker_id, config):
         # 支持的组件类型: crawler, cleaner, storage, indexer
         # 初始化对应的handler并启动
       
       # Handler工厂
       HandlerFactory:
         - create_crawler_handler(redis_url, handler_id, ...)  # 创建爬虫handler
         - create_cleaner_handler(redis_url, handler_id, ...)  # 创建清洗器handler
         - create_storage_handler(redis_url, handler_id, ...)  # 创建存储器handler
         - create_indexer_handler(redis_url, milvus_uri, ...) # 创建索引器handler
       
       # 组件状态类
       ComponentStatus:
         - IDLE        # 空闲
         - RUNNING     # 运行中
         - STOPPED     # 已停止
         - ERROR       # 错误
       ```
     - 组件Handler接口设计
       ```python
       BaseHandler:
         - __init__(redis_url, handler_id, ...)    # 初始化Handler
         - start()                                # 启动处理循环
         - stop()                                 # 停止处理循环
         - process_task(task)                     # 处理单个任务
         - get_stats()                            # 获取处理统计信息
         - get_status()                           # 获取当前状态
       ```
   - 6.2 任务流转与处理机制
     - 管理器职责:
       - 初始化并维护四个组件(爬虫、清洗器、存储器、索引器)的进程池
       - 管理Redis队列作为组件间的通信管道
       - 提供统一的监控接口查看系统状态
     - 队列结构:
       - url队列: sitesearch:queue:url (爬虫输入)
       - crawl队列: sitesearch:queue:crawl (爬虫输出/清洗器输入)
       - clean队列: sitesearch:queue:clean (清洗器输出/存储器输入)
       - index队列: sitesearch:queue:index (存储器输出/索引器输入)
     - 任务传递流程:
       1. URL添加到url队列 → 爬虫进程获取URL并爬取
       2. 爬虫将爬取结果放入crawl队列 → 清洗器获取并处理
       3. 清洗器将清洗结果放入clean队列 → 存储器获取并存储
       4. 存储器将需要索引的数据放入index队列 → 索引器获取并索引
     - 状态监控:
       - 每个队列监控待处理、处理中、已完成、失败任务数量
       - 组件进程存活状态监控
       - 系统资源使用情况监控(CPU、内存)
   - 6.3 多进程通信与同步
     - Redis作为进程间通信媒介
     - 通过Redis的原子操作确保任务不被重复处理
     - 处理状态通过Redis键值存储共享
     - 任务元数据和处理时间统计
   - 6.4 错误处理与恢复机制
     - 进程异常退出自动记录
     - 任务处理失败自动进入失败队列
     - 支持任务重试机制
     - 关键操作事务保护
   - 6.5 扩展与API化准备
     - 配置驱动的组件初始化
     - 易于转换为API接口的管理器设计
     - 支持动态调整工作进程数量
     - 可插拔的组件和策略设计
   
   - 6.6 与已实现的多进程管理器示例对照
     - 已实现的流水线管理核心类
       ```python
       # 已实现的MultiProcessSiteSearchManager核心功能:
       class MultiProcessSiteSearchManager:
           def __init__(self, redis_url: str, milvus_uri: str = None):
               # 初始化Redis客户端
               # 设置进程池字典，包含crawler/cleaner/storage/indexer
               # 设置组件配置字典
               # 设置监控线程
           
           def initialize_components(self, crawler_config, cleaner_strategies, 
                                    storage_config, indexer_config):
               # 配置各组件参数，如批处理大小、睡眠时间等
           
           def start_workers(self, crawler_workers, cleaner_workers, 
                           storage_workers, indexer_workers):
               # 根据配置启动对应数量的进程
               # 每个进程调用component_worker函数启动特定类型的处理器
           
           def start_monitoring(self):
               # 启动监控线程，定期检查系统状态
           
           def add_url_to_queue(self, url: str, site_id: str) -> bool:
               # 将URL任务添加到爬取队列
           
           def shutdown(self):
               # 关闭所有进程和资源
       ```
     - 已实现的组件Worker函数
       ```python
       def component_worker(component_type, redis_url, milvus_uri, worker_id, config):
           # 根据组件类型创建相应的handler
           # crawler: 爬虫handler，从url队列获取任务，结果放入crawl队列
           # cleaner: 清洗handler，从crawl队列获取任务，结果放入clean队列
           # storage: 存储handler，从clean队列获取任务，结果放入index队列
           # indexer: 索引handler，从index队列获取任务，进行向量索引
           
           # 设置信号处理
           # 启动handler处理循环
           # 定期检查状态
       ```
     - 实际实现中的处理流程
       1. 主进程启动多个组件worker进程
       2. 每个worker进程初始化对应的handler
       3. Handler通过Redis队列获取任务并处理
       4. 处理结果放入下一个组件的输入队列
       5. 所有组件通过队列形成完整的处理流水线
       6. 主进程通过监控线程跟踪系统状态

7. **Django+Daphne Web 服务**
   - 7.1 配置 Django 项目结构和设置
   - 7.2 实现 ASGI 接口（基于 Daphne）
   - 7.3 设计 RESTful API 接口
   - 7.4 添加简单认证与权限管理
   - 7.5 实现功能接口：
      - **站点管理模块**
        1. `POST /api/sites/` - 创建新站点，支持设置站点名称、描述和基础URL
        2. `GET /api/sites/` - 获取所有站点列表，支持分页和过滤
        3. `GET /api/sites/{id}/` - 获取单个站点详情
        4. `PUT /api/sites/{id}/` - 更新站点配置
        5. `DELETE /api/sites/{id}/` - 删除站点及其所有关联配置
        
      - **爬取策略模块**
        1. `POST /api/sites/{id}/crawl-policies/` - 创建爬取策略，配置起始URL、最大页面数、深度限制、URL过滤规则(正则表达式)
        2. `GET /api/sites/{id}/crawl-policies/` - 获取站点所有爬取策略
        3. `PUT /api/sites/{id}/crawl-policies/{policy_id}/` - 更新爬取策略
        4. `DELETE /api/sites/{id}/crawl-policies/{policy_id}/` - 删除爬取策略
        5. `POST /api/sites/{id}/crawl-policies/{policy_id}/execute/` - 立即执行特定爬取策略
        
      - **爬取状态监控模块**
        1. `GET /api/sites/{id}/status/` - 获取站点当前爬取状态、队列状态、工作进程状态
        2. `GET /api/queue-metrics/` - 获取所有队列的指标数据(待处理/处理中/已完成/失败任务数)
        3. `GET /api/worker-status/` - 获取所有工作进程状态
        4. `GET /api/sites/{id}/crawl-history/` - 获取站点爬取历史记录，支持按时间范围过滤
        
      - **已爬取内容管理模块**
        1. `GET /api/sites/{id}/documents/` - 获取站点已爬取的所有页面，支持分页、排序和过滤
        2. `GET /api/sites/{id}/documents/{doc_id}/` - 获取特定页面详情，包括原始内容、清洗后内容和元数据
        3. `POST /api/sites/{id}/documents/{doc_id}/refresh/` - 手动刷新特定页面内容
        
      - **搜索模块**
        1. `GET /api/search/` - 全文搜索接口，支持跨站点或特定站点搜索，支持分页和排序
        2. `GET /api/semantic-search/` - 语义搜索接口，支持自然语言查询和相关度排序
        3. `POST /api/chat/` - 基于已索引内容的对话问答接口
        
      - **定时任务模块**
        1. `POST /api/sites/{id}/crawl-policies/{policy_id}/schedule/` - 为爬取策略设置定时执行计划
        2. `GET /api/sites/{id}/schedules/` - 获取站点所有定时任务
        3. `PUT /api/sites/{id}/schedules/{schedule_id}/` - 更新定时任务配置
        4. `DELETE /api/sites/{id}/schedules/{schedule_id}/` - 删除定时任务
        5. `POST /api/sites/{id}/schedules/{schedule_id}/toggle/` - 启用/禁用定时任务
        
      - **内容刷新模块**
        1. `POST /api/sites/{id}/refresh-policy/` - 创建内容刷新策略，设置刷新间隔和条件
        2. `GET /api/sites/{id}/refresh-policy/` - 获取站点内容刷新策略
        3. `PUT /api/sites/{id}/refresh-policy/` - 更新内容刷新策略
        4. `POST /api/sites/{id}/refresh/` - 执行站点全量内容刷新
        
      - **系统管理模块**
        1. `GET /api/system/stats/` - 获取系统资源使用情况
        2. `POST /api/system/workers/restart/` - 重启工作进程
        3. `POST /api/system/queue/{queue_name}/clear/` - 清空指定队列
        4. `GET /api/system/logs/` - 获取系统日志

8. **AI Agent实现**
   - 8.1 实现基于Optimizer的提示词优化器
     - 自动识别专业术语和缩写并提供解释
     - 基于hint_table.json的提示词数据库
     - 添加专业术语上下文增强理解
     - 核心接口设计
       ```python
       class Optimizer:
         - __init__()                                    # 初始化优化器
         - _get_hint(message: str) -> str                # 从信息中提取关键词并生成提示
         - optimize(message: list[ChatCompletionMessageParam]) -> str  # 优化消息列表
       ```
     - 优化过程
       ```
       1. 从用户消息中识别专业术语
       2. 查找hint_table中对应术语的详细解释
       3. 生成包含中英文对照和上下文的提示信息
       4. 将提示信息添加到AI系统提示中
       ```

   - 8.2 实现基于Analyzer的查询分析器
     - 实现五种分析模式：关键词提取、多角度查询、问题分解、回溯思考和上下文分析
     - 每种分析模式使用特定的提示词模板
     - 实现并行分析处理以提高效率
     - 核心接口设计
       ```python
       class Analyzer:
         - __init__(openai_client)                        # 初始化分析器
         - analyze(messages, prompt, item_count) -> list  # 执行特定类型的分析
         - analyze_kmds(message) -> list                  # 并行执行关键词、多查询、分解和回溯分析
         - analyze_context(message) -> list               # 分析上下文，生成上下文查询
       ```
     - 分析模板枚举
       ```python
       class AnalyzerPrompt(Enum):
         - CONTEXT_PROMPT    # 上下文查询提示
         - KEYWORDS_PROMPT   # 关键词提取提示
         - MULTY_QUERY_PROMPT  # 多角度查询提示
         - DECOMPOSITION_PROMPT # 问题分解提示
         - STEP_BACK_PROMPT  # 回溯思考提示
       ```

   - 8.3 实现Agent核心逻辑
     - 实现消息管理和模型交互
     - 支持工具调用和流式响应
     - 添加多轮对话和深度思考能力
     - 核心接口设计
       ```python
       class Agent:
         - __init__(openai_client)                         # 初始化Agent
         - build_message(messages, related_messages) -> list  # 构建消息列表并控制token使用
         - run(messages, context) -> AsyncGenerator         # 基础问答流程
         - run_deep(messages, context) -> AsyncGenerator    # 深度思考流程
         - run_query(query, keywords, context) -> QueryResult  # 执行知识库查询
         - run_query_batch(main_queries, sub_queries, context) -> QueryResult  # 批量执行查询
       ```
     - 问答流程
       ```
       1. 用户提问 → 构建系统消息和上下文
       2. 首次调用LLM生成初步回答和工具调用
       3. 执行工具调用(知识库查询)获取相关信息
       4. 将查询结果融入上下文
       5. 再次调用LLM生成最终答案
       6. 返回答案和参考资料
       ```
     - 深度思考流程
       ```
       1. 用户提问 → 分析器分解问题
       2. 执行多角度、多关键词批量查询
       3. 获取初步信息后开始多轮推理
       4. 动态决定是否需要进一步调查特定资料
       5. 通过反复思考和信息收集生成全面答案
       6. 返回答案和完整参考资料
       ```

   - 8.4 实现查询结果处理
     - 设计统一的QueryResult数据结构
     - 实现Reference处理和展示
     - 添加排序和去重逻辑
     - 数据结构设计
       ```python
       @dataclass
       class QueryResult:
         - query: str                      # 查询内容
         - node_text: str                  # 节点文本
         - results: List[CrawlerResult]    # 爬虫结果列表
         - nodes: Optional[List[NodeWithScore]] = None  # 可选的节点列表
         
         @staticmethod
         def from_multi_results(query_result_objs) -> "QueryResult"  # 合并多个查询结果
       
       @dataclass
       class Reference:
         - mimetype: str                   # 媒体类型
         - preview_url: str                # 预览URL
         - source: str                     # 来源
         - title: str                      # 标题
         - description: str                # 描述
         
         @staticmethod
         def from_crawler_result(crawler_result) -> "Reference"  # 从爬虫结果创建引用
       ```

   - 8.5 添加流式响应和前端集成
     - 实现基于AsyncGenerator的流式回复
     - 支持内容块、工具调用和引用的流式传输
     - 添加进度指示和中间结果展示
     - 流式响应格式
       ```json
       {
         "delta": {
           "role": "assistant",           // 角色信息(仅在第一个delta出现)
           "content": "回复内容片段",      // 内容片段
           "tool_calls": [{               // 工具调用信息(如果有)
             "id": "调用ID",
             "type": "function",
             "function": {
               "name": "函数名",
               "arguments": "函数参数"
             }
           }],
           "references": [{               // 引用信息(仅在返回参考资料时出现)
             "title": "标题",
             "preview_url": "URL",
             "source": "来源",
             "description": "描述"
           }]
         }
       }
       ```

   - 8.6 实现上下文管理和会话记录
     - 设计会话上下文结构
     - 实现消息过滤和历史压缩
     - 添加会话状态和结果持久化
     - 上下文管理
       ```python
       # 会话上下文结构
       {
         "user_id": "用户ID",
         "messages": [所有消息历史],
         "question": "当前问题",
         "query": "执行的查询",
         "nodes": [相关知识点],
         "score": 匹配分数,
         "answer": "生成的答案"
       }
       
       # UserRecord模型保存会话记录
       class UserRecord:
         - user_id: 用户ID
         - messages: 消息历史
         - question: 问题
         - query: 查询
         - nodes: 节点列表
         - score: 分数
         - answer: 答案
       ```

9. **前端实现**
   - 技术栈：React, tailwindcss, shadcn/ui, radix-ui, lucide-react, ndjson, react-markdown, katex
   - 9.1 设计用户界面原型
     - 站点配置页面
     - 爬取监控页面
     - 搜索结果页面
     - AI 对话页面
   - 9.2 实现基于 Django 模板的前端
     - 响应式布局，支持移动设备
     - 实时进度展示（WebSocket）
   - 9.3 添加搜索结果高亮和分页
   - 9.4 实现站点配置表单和验证
   - 9.5 实现AI对话界面
     - 支持流式响应显示
     - 实现打字机效果
     - 集成Markdown渲染
     - 添加参考资料展示
     - 实现聊天历史浏览
   - 9.6 实现智能搜索/深度思考切换
     - 快速搜索模式UI
     - 深度思考模式UI
     - 流程进度指示器
     - 搜索结果展示组件
   - 9.7 添加前端单元测试
   - 9.8 优化加载性能和用户体验

10. **集成测试与部署**
   - 10.1 编写端到端测试流程
   - 10.2 实现 CI/CD 管道（GitHub Actions）
   - 10.3 配置生产环境部署脚本
   - 10.4 添加监控和告警系统（Prometheus + Grafana）
   - 10.5 编写用户文档和开发者文档
   - 10.6 执行安全审计和性能测试

11. **优化与扩展**
    - 11.1 优化爬虫性能和资源利用
    - 11.2 改进搜索质量和相关性
    - 11.3 添加更多数据源支持（PDF, DOC 等）
    - 11.4 实现多语言支持
    - 11.5 添加用户反馈和搜索分析功能