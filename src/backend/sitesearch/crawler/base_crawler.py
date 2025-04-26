"""
基础爬虫类
定义了爬虫的通用接口和方法
"""

import logging
import re
import time
from datetime import datetime
from typing import Dict, List, Set, Optional, Any, Callable
from urllib.parse import urljoin, urlparse, unquote, urlunparse
from pydantic import BaseModel

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('base_crawler')

class BaseCrawlerConfig(BaseModel):
    base_url: str
    max_urls: int = 1
    max_depth: int = 3
    request_delay: float = 0.5,
    headers: Optional[Dict[str, str]] = None,
    cookies: Optional[Dict[str, str]] = None,
    excluded_patterns: Optional[List[str]] = None,
    included_patterns: Optional[List[str]] = None,
    proxy: Optional[str] = None,
    timeout: int = 30,
    verify_ssl: bool = True,
    follow_redirects: bool = True,
    on_page_crawled: Optional[Callable[[str, str, Dict[str, Any]], None]] = None,


class BaseCrawler:
    """
    爬虫基类，定义爬虫接口，实现通用爬虫功能
    """
    
    def __init__(
        self,
        base_url: str,
        max_urls: int = 100,
        max_depth: int = 3,
        request_delay: float = 0.5,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        excluded_patterns: Optional[List[str]] = None,
        included_patterns: Optional[List[str]] = None,
        proxy: Optional[str] = None,
        timeout: int = 30,
        verify_ssl: bool = True,
        follow_redirects: bool = True,
        on_page_crawled: Optional[Callable[[str, str, Dict[str, Any]], None]] = None,
    ):
        """
        初始化爬虫
        
        Args:
            max_urls: 最大爬取URL数量
            max_depth: 最大爬取深度
            request_delay: 每次请求之间的延迟（秒）
            headers: 请求头
            cookies: 请求cookies
            excluded_patterns: 要排除的URL正则表达式模式列表
            included_patterns: 要包含的URL正则表达式模式列表（白名单）
            proxy: 代理服务器URL
            timeout: 请求超时时间（秒）
            verify_ssl: 是否验证SSL证书
            follow_redirects: 是否跟随重定向
            on_page_crawled: 当页面爬取完成时的回调函数
        """
        self.base_url = base_url
        self.max_urls = max_urls
        self.max_depth = max_depth
        self.request_delay = request_delay
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        self.cookies = cookies or {}
        self.excluded_patterns = excluded_patterns or []
        self.included_patterns = included_patterns or []
        self.proxy = proxy
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.follow_redirects = follow_redirects
        self.on_page_crawled = on_page_crawled
        
        # 爬虫状态
        self.crawled_urls: Set[str] = set()  # 已爬取的URL集合
        self.url_queue: List[Dict[str, Any]] = []  # 待爬取的URL队列，包含URL和深度信息
        self.failed_urls: Dict[str, str] = {}  # 爬取失败的URL及原因
        self.in_progress: bool = False  # 爬虫是否正在进行
        self.start_time: datetime = datetime.now()  # 爬虫开始时间
        self.end_time: datetime = datetime.now()  # 爬虫结束时间
    
    def is_valid_url(self, url: str) -> bool:
        """
        检查URL是否有效（符合爬取规则）
        
        Args:
            url: 要检查的URL
            
        Returns:
            bool: URL是否有效
        """
        # 检查是否是HTTP或HTTPS URL
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False
        
        # 排除锚点链接
        if '#' in url:
            url = url.split('#')[0]
            if not url:
                return False
        
        # 检查是否匹配包含模式（如果有）
        if self.included_patterns:
            if not any(re.search(pattern, url) for pattern in self.included_patterns):
                return False
        
        # 检查是否匹配排除模式
        if any(re.search(pattern, url) for pattern in self.excluded_patterns):
            return False
        
        return True
    
    def normalize_url(self, url: str) -> str:
        """
        标准化URL，处理相对路径、多重编码、锚点、结尾斜杠等。
        
        Args:
            url: 原始URL

        Returns:
            str: 规范化后的URL
        """
        # Step 1: 解析相对URL
        url = urljoin(self.base_url, url)

        # Step 2: 多重解码（避免像 %252525 这种情况）
        max_decode = 5  # 防止死循环
        for _ in range(max_decode):
            decoded = unquote(url)
            if decoded == url:
                break
            url = decoded

        # Step 3: 去掉 URL 的锚点
        parsed = urlparse(url)
        parsed = parsed._replace(fragment='')

        # Step 4: 处理路径结尾
        path = parsed.path
        if not path.endswith('/') and '.' not in path.split('/')[-1]:
            path += '/'
        parsed = parsed._replace(path=path)

        # Step 5: 构建回 URL
        normalized_url = urlunparse(parsed)

        return normalized_url
    
    def extract_links(self, url: str, html_content: str) -> List[str]:
        """
        从HTML内容中提取链接
        
        Args:
            url: 当前页面的URL
            html_content: HTML内容
            
        Returns:
            List[str]: 提取到的链接列表
        """
        # 基类中只提供接口，具体实现由子类完成
        raise NotImplementedError("必须由子类实现")
    
    def crawl_page(self, url: str) -> Dict[str, Any]:
        """
        爬取单个页面
        
        Args:
            url: 要爬取的URL
            
        Returns:
            Dict[str, Any]: 包含页面内容和元数据的字典
        """
        # 基类中只提供接口，具体实现由子类完成
        raise NotImplementedError("必须由子类实现")
    
    def crawl(self) -> Dict[str, Any]:
        """
        开始爬取网页
        
        Returns:
            Dict[str, Any]: 爬取结果统计
        """
        if self.in_progress:
            logger.warning("爬虫已在运行中")
            return {
                "status": "running",
                "crawled_count": len(self.crawled_urls),
                "queue_count": len(self.url_queue),
                "failed_count": len(self.failed_urls),
            }
        
        self.in_progress = True
        self.start_time = datetime.now()
        
        try:
            # 将起始URL添加到队列
            self.url_queue.append({
                "url": self.base_url,
                "depth": 0
            })
            
            # 开始爬取
            while self.url_queue and len(self.crawled_urls) < self.max_urls:
                # 从队列中取出URL
                url_info = self.url_queue.pop(0)
                url = url_info["url"]
                depth = url_info["depth"]
                
                # 如果URL已经爬取过，跳过
                if url in self.crawled_urls:
                    continue
                
                # 爬取页面
                try:
                    logger.info(f"爬取页面 ({len(self.crawled_urls) + 1}/{self.max_urls}): {url}")
                    result = self.crawl_page(url)
                    print("爬取+1", result.keys())
                    self.crawled_urls.add(url)
                    
                    # 如果设置了回调函数，调用它
                    if self.on_page_crawled:
                        self.on_page_crawled(url, result.get("content", ""), result.get("metadata", {}))
                    
                    # 如果深度小于最大深度，提取链接并添加到队列
                    if depth < self.max_depth:
                        links = result.get("links", [])
                        print(f"相关链接数量：{len(links)}")
                        for link in links:
                            # 标准化链接
                            normalized_link = self.normalize_url(link)
                            
                            # 检查链接是否有效
                            if self.is_valid_url(normalized_link) and normalized_link not in self.crawled_urls:
                                self.url_queue.append({
                                    "url": normalized_link,
                                    "depth": depth + 1
                                })
                        print(f"当前深度：{depth}，当前爬取数量：{len(self.crawled_urls)}，当前队列数量：{len(self.url_queue)}")
                    else:
                        logger.info(f"当前深度：{depth}，达到最大深度{self.max_depth}，爬取完成")
                    
                    # 请求之间添加延迟
                    if self.request_delay > 0:
                        time.sleep(self.request_delay)
                
                except Exception as e:
                    logger.error(f"爬取页面 {url} 失败: {str(e)}")
                    self.failed_urls[url] = str(e)

            if not self.url_queue:
                logger.info("队列为空，爬取完成")
            if len(self.crawled_urls) >= self.max_urls:
                logger.info("达到最大爬取数量，爬取完成")
        finally:
            self.in_progress = False
            self.end_time = datetime.now()
        
        # 返回爬取统计信息
        return {
            "status": "completed",
            "crawled_count": len(self.crawled_urls),
            "failed_count": len(self.failed_urls),
            "duration": self.end_time - self.start_time,
            "crawled_urls": list(self.crawled_urls),
            "failed_urls": self.failed_urls
        }

    
    def discover_sitemap(self) -> List[str]:
        """
        尝试发现并解析网站的sitemap
        
        Returns:
            List[str]: 从sitemap中提取的URL列表
        """
        # 基类中只提供接口，具体实现由子类完成
        raise NotImplementedError("必须由子类实现")
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取爬虫当前状态
        
        Returns:
            Dict[str, Any]: 爬虫状态信息
        """
        return {
            "in_progress": self.in_progress,
            "crawled_count": len(self.crawled_urls),
            "queue_count": len(self.url_queue),
            "failed_count": len(self.failed_urls),
            "start_time": self.start_time,
            "elapsed_time": datetime.now() - self.start_time if self.in_progress else self.end_time - self.start_time
        }
    
    def stop(self) -> None:
        """
        停止爬虫
        """
        self.in_progress = False
        self.end_time = datetime.now()
        logger.info("爬虫已停止")
    
    def reset(self) -> None:
        """
        重置爬虫状态
        """
        self.crawled_urls = set()
        self.url_queue = []
        self.failed_urls = {}
        self.in_progress = False
        self.start_time = 0
        self.end_time = 0
        logger.info("爬虫状态已重置") 