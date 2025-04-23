import hashlib
import os
from datetime import datetime
from threading import Lock
from typing import Optional, Dict
from urllib.parse import urljoin, unquote

from sqlalchemy import text, select

from backend.sitesearch.crawler.base import DataCrawler, CrawlerResult, CrawlerMetadata, NoStrategyMatch
from crawlers.strategies import *
from rag.models import Knowledge, get_db_session, init_db, get_async_db_session
import retry

VERBOSE = False


def get_title(response: httpx.Response) -> str:
    """获取网页标题"""
    tree = BeautifulSoup(response.text, 'lxml')
    # 从url中获取title
    url = urlparse(str(response.url))
    if url.path and '/' in url.path:
        tail_path = url.path.split('/')[-1]
        basename = os.path.basename(tail_path) if '.' in tail_path else tail_path
        basename = basename.replace('.html', '').replace('.pdf', '')
        # 转义回正常字符串
        basename = unquote(basename)
        basename = (basename[:245] + '...') if len(basename) > 250 else basename
        return basename if not tree.title else (tree.title.text[:245] + '...') if len(tree.title.text) > 250 else tree.title.text
    else:
        title = tree.title.text if tree.title else url.netloc
        return (title[:245] + '...') if len(title) > 250 else title


def get_related_links(url: str, response: httpx.Response) -> List[str]:
    """获取网页相关链接"""
    tree = BeautifulSoup(response.text, 'lxml')
    links = [link.get('href') for link in tree.find_all('a') if link.get('href')]
    # 过滤掉javascript:void(0)类型的链接
    valid_links = [link for link in links if not link.startswith('javascript:')]
    # 将链接转换为绝对路径
    return [urljoin(url, link) for link in valid_links if link]


class WebCrawler(DataCrawler):
    """网页数据采集器"""
    
    def __init__(self, timeout: int = 5, strategies: Optional[List[CleaningStrategy]] = None, max_retries: int = 8):
        """初始化网页采集器
        
        Args:
            timeout: 请求超时时间（秒）
            strategies: 清洗策略列表，如果不指定则使用默认策略
            max_retries: 最大重试次数
        """
        super().__init__()
        self.timeout = timeout
        self.max_retries = max_retries
        
        # 设置更细粒度的超时控制
        timeout_config = httpx.Timeout(
            connect=timeout,  # 连接超时
            read=timeout * 2,  # 读取超时设置更长
            write=timeout,  # 写入超时
            pool=timeout * 3  # 连接池超时设置最长
        )

        limits = httpx.Limits(max_keepalive_connections=1000, max_connections=1000, keepalive_expiry=30)
        
        self.client = httpx.Client(
            timeout=timeout_config,
            limits=limits,
            follow_redirects=True  # 自动处理重定向
        )
        self.async_client = httpx.AsyncClient(
            timeout=timeout_config,
            limits=limits,
            follow_redirects=True  # 自动处理重定向
        )
        
        init_db()
        self.lock = Lock()
        self._session = None

        # 设置清洗策略，优先使用自定义策略
        self.strategies = strategies or [
            PDFStrategy(),
            DocxStrategy(),
            SearchPageStrategy(),  # 针对搜索页面的策略
            CommonPageStrategy(),  # 优先使用针对常见page页面的策略
            MarkdownStrategy(),  # 其次尝试转换为Markdown
            HTMLStrategy(),  # 再次尝试普通HTML清洗
            PlainTextStrategy(),  # 最后是纯文本清洗
        ]
    
    @property
    def session(self):
        """获取同步会话"""
        if self._session is None:
            self._session = get_db_session()
        return self._session
        
    def __del__(self):
        """确保关闭资源"""
        import asyncio
        self.client.close()
        # 创建新的事件循环来关闭async_client
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.async_client.aclose())
            loop.close()
        except:
            pass  # 忽略关闭时的错误
        if self._session:
            self._session.close()

    def clean_data(self, url: str, mimetype: str, response: httpx.Response | dict) -> str:
        """根据策略清洗数据
        
        Args:
            url: 内容的URL
            mimetype: 内容的MIME类型
            response: 原始响应
            
        Returns:
            清洗后的内容
        """
        raw_content_str: str = response.text if isinstance(response, httpx.Response) else response["text"]
        decoded_content: bytes = response.content if isinstance(response, httpx.Response) else response["content"]
        # 遍历所有策略，使用第一个匹配的策略
        for strategy in self.strategies:
            if strategy.should_handle(url, mimetype, raw_content_str):
                if VERBOSE:
                    print(f"使用策略: {strategy.__class__.__name__}")
                return strategy.clean(content=decoded_content, content_str=raw_content_str)
        
        # 如果没有匹配的策略，返回原始内容
        raise NoStrategyMatch(f"没有匹配的策略: {mimetype}")
        # return response.text

    def check_if_exists(self, response: httpx.Response) -> Knowledge | None:
        """检查URL是否已存在"""
        raw_content_hash = hashlib.sha256(response.text.encode()).hexdigest()
        obj = self.session.query(Knowledge).filter(Knowledge.raw_content_hash == raw_content_hash).first()
        result = obj if obj else None
        if result and len(result.content) > 0:
            return result
    
    async def acheck_if_exists(self, response: httpx.Response) -> Knowledge | None:
        """异步检查URL是否已存在"""
        raw_content_hash = hashlib.sha256(response.text.encode()).hexdigest()
        current_url = str(response.url)
        
        async with get_async_db_session() as session:
            async with session.begin():
                # 查找所有匹配的记录
                query = select(Knowledge).filter(Knowledge.raw_content_hash == raw_content_hash)
                result_proxy = await session.execute(query)
                results = result_proxy.scalars().all()
                
                if not results:
                    return None
                    
                if len(results) > 1:
                    if VERBOSE:
                        print(f"发现多条记录具有相同的content hash: {raw_content_hash}")
                    # 按更新时间排序，保留最新的记录
                    results = sorted(results, key=lambda x: x.updated_at, reverse=True)
                    latest_result = results[0]
                    # 删除其他重复记录
                    for result in results[1:]:
                        await session.delete(result)
                else:
                    latest_result = results[0]
                
                # 检查并更新URL
                stored_url = latest_result.result_metadata.get('url')
                if stored_url != current_url:
                    new_result_metadata = latest_result.result_metadata.copy()
                    new_result_metadata['url'] = current_url
                    latest_result.result_metadata = new_result_metadata
                    latest_result.updated_at = datetime.now()
                
                await session.commit()
                return latest_result

    def crawl(self, url: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> CrawlerResult | None:
        """采集网页数据
        
        Args:
            url: 目标网页URL
            headers: 请求头
            **kwargs: 其他参数
            
        Returns:
            包含清洗后HTML内容和元数据的CrawlerResult对象
            
        Raises:
            httpx.RequestError: 请求失败
            httpx.HTTPStatusError: HTTP状态码错误
        """
        # 设置默认headers
        if headers is None:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
        # 发送请求
        @retry.retry(tries=self.max_retries, delay=1, backoff=2)
        def _get_response(url: str, headers: Dict[str, str]) -> httpx.Response:
            response = self.client.get(url, headers=headers)
            if response.status_code // 100 == 3:
                # 重定向
                response = self.client.get(response.headers['Location'], headers=headers)
            response.raise_for_status()
            return response
        
        response = _get_response(url, headers)

        if obj := self.check_if_exists(response):
            if VERBOSE:
                print(f"cache hit: {url}")
            return CrawlerResult(
                mimetype=obj.mimetype,
                content=obj.content,
                metadata=CrawlerMetadata(**obj.result_metadata),
                raw_data=obj.raw_content_hash
            )
        
        # 获取原始内容
        mimetype = response.headers.get('content-type', 'text/html')
        raw_content = response.text if mimetype.startswith('text') else ""

        # 使用策略清洗数据
        cleaned_content = self.clean_data(url, mimetype, response)

        if not cleaned_content:
            return None
        
        # 提取域名作为source
        domain = urlparse(url).netloc
        
        # 构建元数据

        metadata = CrawlerMetadata(
            source=domain,
            url=url,
            date=datetime.now(),
            title=get_title(response),
            related_links=get_related_links(url, response),
            extra={
                'status_code': response.status_code,
                'headers': dict(response.headers),
            }
        )

        crawler_result = CrawlerResult(
            mimetype=mimetype,
            content=cleaned_content,
            metadata=metadata,
            raw_data=raw_content
        )
        self.save_to_db(response, crawler_result)
        
        return crawler_result
    
    async def acrawl(self, url: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> CrawlerResult | None:
        # 设置默认headers
        if headers is None:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
        # 发送请求
        response = await self.async_client.get(url, headers=headers)
        if response.status_code // 100 == 3:
            # 重定向
            response = await self.async_client.get(response.headers['Location'], headers=headers)
        response.raise_for_status()

        if obj := await self.acheck_if_exists(response):
            if VERBOSE:
                print(f"cache hit: {url}")
            return CrawlerResult(
                mimetype=obj.mimetype,
                content=obj.content,
                metadata=CrawlerMetadata(**obj.result_metadata),
                raw_data=obj.raw_content_hash
            ), True
        
        # 获取原始内容
        mimetype = response.headers.get('content-type', 'text/html')
        raw_content = {
            "text": response.text,
            "content": response.content
        }
        
        # 提取域名作为source
        domain = urlparse(url).netloc
        
        # 构建元数据
        metadata = CrawlerMetadata(
            source=domain,
            url=url,
            date=datetime.now(),
            title=get_title(response),
            related_links=get_related_links(url, response),
            extra={
                'status_code': response.status_code,
                'headers': dict(response.headers),
            }
        )

        # # 使用策略清洗数据
        # cleaned_content = self.clean_data(url, mimetype, response)

        # if not cleaned_content:
        #     return None

        crawler_result = CrawlerResult(
            mimetype=mimetype,
            content=None,
            metadata=metadata,
            raw_data=raw_content
        )
        # self.save_to_db(response, crawler_result)
        
        return crawler_result, False

    async def asave_to_db(self, raw_content: str, result: CrawlerResult):
        """异步保存结果到数据库"""
        raw_content_hash = hashlib.sha256(raw_content.encode()).hexdigest()
        async with get_async_db_session() as session:
            async with session.begin():
                knowledge = Knowledge(
                    mimetype=result.mimetype,
                    title=result.metadata.title,
                    content=result.content,
                    result_metadata=result.metadata.to_dict(),
                    raw_content_hash=raw_content_hash,
                    source=result.metadata.source,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    is_active=True
                )
                query = select(Knowledge).filter(
                    text("result_metadata->>'url' = :url")
                ).params(url=result.metadata.url)
                existing_knowledges = (await session.execute(query)).scalars().all()
                if len(existing_knowledges) > 1:
                    if VERBOSE:
                        print(f"相同url: {result.metadata.url} 存在 {len(existing_knowledges)} 条知识")
                    existing_knowledges = sorted(existing_knowledges, key=lambda x: x.updated_at, reverse=True)
                    latest_knowledge = existing_knowledges[0]
                    # 删除其他重复的知识条目
                    for knowledge in existing_knowledges:
                        if knowledge.id != latest_knowledge.id:
                            await session.delete(knowledge)
                if len(existing_knowledges) > 0:
                    existing_knowledge = existing_knowledges[0]
                    existing_knowledge.mimetype = result.mimetype
                    existing_knowledge.title = result.metadata.title
                    existing_knowledge.content = result.content
                    existing_knowledge.result_metadata = result.metadata.to_dict()
                    existing_knowledge.updated_at = datetime.now()
                    # 覆盖已存在的知识条目
                    if VERBOSE:
                        print(f"覆盖已存在的知识条目: {existing_knowledge.title}")
                    await session.merge(existing_knowledge)
                else:
                    # 新增知识条目
                    if VERBOSE:
                        print(f"新增知识条目: {knowledge.title}")
                    session.add(knowledge)
                await session.commit()

    def save_to_db(self, response: httpx.Response, result: CrawlerResult):
        """将结果保存到数据库"""
        raw_content_hash = hashlib.sha256(response.text.encode()).hexdigest()
        with self.lock:
            knowledge = Knowledge(
                mimetype=result.mimetype,
                title=result.metadata.title,
                content=result.content,
                result_metadata=result.metadata.to_dict(),
                raw_content_hash=raw_content_hash,
                source=result.metadata.source,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                is_active=True
            )
            # 根据url查询已存在的知识条目
            existing_knowledges = self.session.query(Knowledge).filter(
                    text("result_metadata->>'url' = :url")
                ).params(url=result.metadata.url)
            if existing_knowledges.count() > 1:
                if VERBOSE:
                    print(f"相同url: {result.metadata.url} 存在 {existing_knowledges.count()} 条知识")
                latest_knowledge = existing_knowledges.order_by(Knowledge.updated_at.desc()).first()
                existing_knowledge = latest_knowledge
                # 删除其他重复的知识条目
                for knowledge in existing_knowledges:
                    if knowledge.id != latest_knowledge.id:
                        self.session.delete(knowledge)
            else:
                existing_knowledge = existing_knowledges.first()
            if existing_knowledge:
                existing_knowledge.mimetype = result.mimetype
                existing_knowledge.title = result.metadata.title
                existing_knowledge.content = result.content
                existing_knowledge.result_metadata = result.metadata.to_dict()
                existing_knowledge.updated_at = datetime.now()
                # 覆盖已存在的知识条目
                if VERBOSE:
                    print(f"覆盖已存在的知识条目: {existing_knowledge.title}")
                self.session.merge(existing_knowledge)
            else:
                # 新增知识条目
                if VERBOSE:
                    print(f"新增知识条目: {knowledge.title}")
                self.session.add(knowledge)

            self.session.commit()
