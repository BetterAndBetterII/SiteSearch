# SiteSearch 爬虫系统

SiteSearch 是一个高效的网站爬取和搜索系统，用于对网站内容进行爬取、清洗、索引和检索。

## 功能特点

- **高效爬取**：支持多种爬虫引擎，包括本地HTTPX爬虫和Firecrawl云服务
- **智能清洗**：多种内容清洗策略，适应不同类型的网页
- **灵活配置**：可自定义爬取深度、速率、过滤规则等
- **网站地图支持**：自动发现和解析sitemap.xml
- **结果存储**：支持将爬取结果保存为JSON格式
- **爬虫管理**：统一管理多个爬虫实例，支持创建、启动、停止和监控

## 系统架构

```
用户 ──→ Web界面(Django + Daphne ASGI)
            │
            └─ 配置站点 (正则/前缀匹配)
                         │
                         ▼
爬取器(Firecrawl/Httpx, Redis队列)
            │
            ▼
清洗器(MarkdownConverter, Redis队列)
            │
            ▼
数据库持久化(PostgreSQL, URL去重校验)
            │───▶ 已存在，Skip
            │
            ▼ 新数据或数据更新
索引器(Llama-index导入Redis(Doc)、Milvus(Vector))
            │
            ▼
搜索端点(RAG)
            │
            ▼
         用户搜索查询
```

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 使用示例

我们提供了两个示例脚本，展示如何使用不同类型的爬虫：

#### HTTPX爬虫 (本地爬虫)

```bash
# 爬取指定网站，最多爬取10个页面，最大深度为2
python examples/crawler_demo.py https://example.com

# 自定义配置
python examples/crawler_demo.py https://example.com --id my_crawler --max-pages 20 --max-depth 3 --delay 1.0
```

#### Firecrawl爬虫 (云服务爬虫)

需要先获取Firecrawl API密钥：https://firecrawl.dev

```bash
# 设置API密钥环境变量
export FIRECRAWL_API_KEY="fc-your-api-key"

# 爬取指定网站，最多爬取10个页面，最大深度为2
python examples/firecrawl_demo.py https://example.com

# 自定义配置
python examples/firecrawl_demo.py https://example.com --id my_crawler --max-pages 20 --max-depth 3 --formats markdown html
```

### 代码示例

```python
from src.backend.sitesearch.crawler.crawler_manager import CrawlerManager

# 创建爬虫管理器
manager = CrawlerManager(storage_dir="./crawl_results")

# 创建HTTPX爬虫
manager.create_crawler(
    crawler_id="httpx_crawler",
    crawler_type="httpx",
    base_url="https://example.com",
    config={
        "max_pages": 10,
        "max_depth": 2,
        "delay": 0.5,
        "timeout": 30,
        "headers": {"User-Agent": "SiteSearch-Crawler/1.0"},
        "follow_external_links": False,
    }
)

# 或者创建Firecrawl爬虫
manager.create_crawler(
    crawler_id="firecrawl_crawler",
    crawler_type="firecrawl",
    base_url="https://example.com",
    config={
        "api_key": "fc-your-api-key",  # 也可以通过环境变量FIRECRAWL_API_KEY设置
        "max_urls": 10,
        "max_depth": 2,
        "formats": ["markdown", "html"],
    }
)

# 启动爬虫
manager.start_crawler("httpx_crawler", discover_sitemap=True)

# 等待爬虫完成
import time
while True:
    status = manager.get_crawler_status("httpx_crawler")
    print(f"状态: {status['status']}, 已爬取: {status['stats'].get('pages_crawled', 0)}")
    
    if status["status"] not in ["running", "created"]:
        break
        
    time.sleep(2)

# 保存结果
result_file = manager.save_results("httpx_crawler")
print(f"结果已保存到: {result_file}")

# 关闭管理器
manager.close()
```

## 爬虫类型

目前支持的爬虫类型：

- **httpx**：基于HTTPX库的本地爬虫，适用于大多数网站
- **firecrawl**：基于Firecrawl API的云服务爬虫，具有高性能和更好的JavaScript渲染支持

## 配置参数

### 通用配置参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| max_pages / max_urls | 最大爬取页面数 | 100 |
| max_depth | 最大爬取深度 | 3 |
| delay / request_delay | 请求延迟(秒) | 0.5 |
| timeout | 请求超时(秒) | 30 |
| headers | 请求头 | User-Agent等默认值 |
| cookies | 请求Cookies | {} |
| excluded_patterns | 要排除的URL正则表达式模式 | [] |
| included_patterns | 要包含的URL正则表达式模式 | [] |
| proxy | 代理服务器URL | None |

### HTTPX爬虫特有参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| verify_ssl | 是否验证SSL证书 | True |
| follow_redirects | 是否跟随重定向 | True |
| follow_external_links | 是否跟随外部链接 | False |

### Firecrawl爬虫特有参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| api_key | Firecrawl API密钥 | 环境变量FIRECRAWL_API_KEY |
| formats | 输出格式列表 | ["markdown"] |

## 文档清洗策略

HTTPX爬虫支持多种内容清洗策略：

- **CommonPageStrategy**：通用网页清洗，识别和提取主要内容区域
- **MarkdownStrategy**：将HTML转换为Markdown格式
- **HTMLStrategy**：基本HTML清洗，移除脚本和样式
- **PlainTextStrategy**：纯文本清洗
- **PDFStrategy**：PDF文档处理
- **DocxStrategy**：Word文档处理
- **SearchPageStrategy**：搜索页面处理

## 高级用法

### 自定义回调处理

您可以提供自定义回调函数来处理爬取到的页面数据：

```python
def my_page_handler(url, content, metadata):
    print(f"处理页面: {url}")
    # 处理内容...

manager.create_crawler(
    crawler_id="my_crawler",
    base_url="https://example.com",
    config={...},
    callback=my_page_handler
)
```

### 使用正则表达式过滤URL

```python
manager.create_crawler(
    crawler_id="my_crawler",
    base_url="https://example.com",
    config={
        "included_patterns": [r"example\.com/blog/.*"],
        "excluded_patterns": [r"example\.com/blog/tag/.*", r".*\.(jpg|png|gif)$"]
    }
)
```

## Firecrawl vs HTTPX

| 特性 | Firecrawl | HTTPX |
|------|----------|-------|
| JavaScript渲染 | ✅ 支持 | ❌ 不支持 |
| 速度 | ⚡ 更快(云服务) | 🐢 一般(本地) |
| 资源消耗 | 🌟 低(云服务) | 📈 高(本地) |
| 自定义能力 | 🔒 有限 | 🔓 完全自定义 |
| 成本 | 💰 按使用量收费 | 🆓 免费 |
| 适用场景 | 现代JavaScript网站 | 静态网站、内部网络 |

## 技术依赖

- Python 3.10+
- HTTPX
- BeautifulSoup4
- Firecrawl Python客户端
- Redis (对于队列管理)

## 许可证

MIT 