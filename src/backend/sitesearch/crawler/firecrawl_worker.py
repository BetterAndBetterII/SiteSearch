"""
基于Firecrawl的爬虫实现
提供使用Firecrawl API的爬取功能
"""

import logging
import time
from datetime import datetime
import os
from typing import Dict, List, Any, Optional, Set, Callable
from urllib.parse import urlparse, urljoin
import threading
import json

from firecrawl.firecrawl import (
    FirecrawlApp, 
    ScrapeOptions, 
    CrawlStatusResponse, 
    FirecrawlDocument, 
    CrawlResponse, 
    ScrapeResponse
)
from .exceptions import FirecrawlError
from .base_crawler import BaseCrawler

# 配置日志
logger = logging.getLogger('firecrawl_worker')

class FirecrawlWorker(BaseCrawler):
    """
    基于Firecrawl的爬虫实现，使用Firecrawl云服务进行网页爬取
    """
    
    def __init__(
        self,
        base_url: str,
        api_key: str,
        max_urls: int = 100,
        max_depth: int = 3,
        request_delay: float = 1.0,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        excluded_patterns: Optional[List[str]] = None,
        included_patterns: Optional[List[str]] = None,
        proxy: Optional[str] = None,
        timeout: int = 60,
        verify_ssl: bool = True,
        follow_redirects: bool = True,
        on_page_crawled: Optional[Callable[[str, str, Dict[str, Any]], None]] = None,
        formats: Optional[List[str]] = None
    ):
        """
        初始化Firecrawl爬虫
        
        Args:
            base_url: 起始URL
            api_key: Firecrawl API密钥
            max_urls: 最大爬取URL数量
            max_depth: 最大爬取深度
            request_delay: 每次请求之间的延迟（秒）
            headers: 请求头
            cookies: 请求cookies
            excluded_patterns: 要排除的URL正则表达式模式列表
            included_patterns: 要包含的URL正则表达式模式列表
            proxy: 代理服务器URL
            timeout: 请求超时时间（秒）
            verify_ssl: 是否验证SSL证书
            follow_redirects: 是否跟随重定向
            on_page_crawled: 当页面爬取完成时的回调函数
            formats: 内容格式列表，如["markdown", "links", "html"]
        """
        super().__init__(
            base_url=base_url,
            max_urls=max_urls,
            max_depth=max_depth,
            request_delay=request_delay,
            headers=headers,
            cookies=cookies,
            excluded_patterns=excluded_patterns,
            included_patterns=included_patterns,
            proxy=proxy,
            timeout=timeout,
            verify_ssl=verify_ssl,
            follow_redirects=follow_redirects,
            on_page_crawled=on_page_crawled,
        )
        
        self.api_key = api_key
        self.available_formats = ["markdown", "links", "html", "rawHtml", "content", "screenshot"]
        self.formats = formats or ["markdown"]
        
        # 校验格式
        for fmt in self.formats:
            if fmt not in self.available_formats:
                raise ValueError(f"不支持的格式: {fmt}，支持的格式为: {', '.join(self.available_formats)}")
        
        # 初始化Firecrawl客户端
        print(f"Firecrawl API Key: {self.api_key}, API URL: {os.environ.get('FIRECRAWL_API_ENDPOINT')}")
        self.client = FirecrawlApp(api_key=self.api_key, api_url=os.environ.get("FIRECRAWL_API_ENDPOINT"))
        
        # 爬取结果存储
        self.results: Dict[str, Dict[str, Any]] = {}
        
        # 任务状态跟踪
        self.current_job_id: Optional[str] = None
        self.job_status: Optional[Dict[str, Any]] = None
        
        # 爬虫锁，用于线程安全操作
        self.lock = threading.Lock()
        
        # 爬取任务ID
        self.active_job_id = None
    
    def extract_links(self, url: str, html_content: str) -> List[str]:
        """
        从HTML内容中提取链接
        
        Args:
            url: 当前页面的URL
            html_content: HTML内容
            
        Returns:
            List[str]: 提取到的链接列表
        """
        # 在Firecrawl工作模式中，链接提取由API服务完成
        # 这里主要是为了满足接口要求，返回结果中的链接
        links = []
        try:
            # 尝试解析JSON内容
            if self.results and url in self.results:
                result = self.results[url]
                if "links" in result:
                    links = result["links"]
        except Exception as e:
            logger.error(f"提取链接时出错: {str(e)}")
        
        return links
    
    def crawl_page(self, url: str) -> Dict[str, Any]:
        """
        爬取单个页面
        
        Args:
            url: 要爬取的URL
            
        Returns:
            Dict[str, Any]: 包含页面内容和元数据的字典
        """
        result = {
            "url": url,
            "content": "",
            "status_code": 0,
            "headers": {},
            "timestamp": time.time(),
            "metadata": {}
        }
        
        try:
            # 设置抓取选项
            options = {
                'formats': self.formats,
                'timeout': self.timeout
            }
            
            # 添加请求头
            if self.headers:
                options["headers"] = self.headers
            
            # 添加Cookie
            if self.cookies:
                # v2 API不再支持直接设置Cookie字符串
                # 需要在headers中设置
                if "headers" not in options:
                    options["headers"] = {}
                cookie_string = "; ".join([f"{k}={v}" for k, v in self.cookies.items()])
                options["headers"]["Cookie"] = cookie_string
            
            # 调用Firecrawl API抓取页面
            logger.info(f"正在抓取页面: {url}")
            response: ScrapeResponse = self.client.scrape_url(
                url,
                **options
            )
            
            # v2 API直接返回结果，不需要获取job_id和轮询状态
            
            # 提取内容
            content = ""
            if "markdown" in response and "markdown" in self.formats:
                content = response["markdown"]
            elif "html" in response and "html" in self.formats:
                content = response["html"]
            elif "links" in response and "links" in self.formats:
                content = str(response["links"])
            elif "content" in response and "content" in self.formats:
                content = response["content"]
            else:
                content = str(response)
            
            # 提取元数据
            metadata = {
                "url": url,
                "timestamp": time.time(),
                "source": urlparse(url).netloc,
            }
            
            # 添加额外元数据
            if "title" in response:
                metadata["title"] = response["title"]
            if "description" in response:
                metadata["description"] = response["description"]
            
            # 提取链接
            related_links = []
            if "links" in response:
                related_links = response["links"]
            
            # 更新结果
            result["content"] = content
            result["metadata"] = metadata
            result["status_code"] = 200  # 假设成功
            
            # 保存链接信息
            metadata["related_links"] = related_links
            
            # 将结果添加到结果集
            self.results[url] = {
                "content": content,
                "metadata": metadata,
                "links": related_links
            }
            
            # 如果有回调函数，调用它
            print("有回调函数" if self.on_page_crawled else "没有回调函数")
            print("Callback:url, content, metadata", url, content, metadata)
            if self.on_page_crawled:
                self.on_page_crawled(url, content, metadata)
            
            return result
            
        except Exception as e:
            logger.exception(f"爬取页面 {url} 时发生未知错误: {str(e)}")
            result["error"] = f"未知错误: {str(e)}"
            raise
    
    # def crawl(self) -> Dict[str, Any]:
    #     """
    #     开始爬取网站
        
    #     Returns:
    #         Dict[str, Any]: 爬取结果统计
    #     """
    #     if self.in_progress:
    #         logger.warning("爬虫已在运行中")
    #         return {
    #             "status": "running",
    #             "crawled_count": len(self.crawled_urls),
    #             "queue_count": len(self.url_queue),
    #             "failed_count": len(self.failed_urls),
    #         }
        
    #     self.in_progress = True
    #     self.start_time = datetime.now()
        
    #     try:
    #         # 设置爬取选项
    #         crawl_options = {
    #             "limit": self.max_urls,
    #             "max_depth": self.max_depth,
    #             "respect_robots_txt": False,
    #             "formats": self.formats
    #         }
            
    #         # 添加请求头
    #         if self.headers:
    #             crawl_options["headers"] = self.headers
            
    #         # 添加Cookie
    #         if self.cookies:
    #             if "headers" not in crawl_options:
    #                 crawl_options["headers"] = {}
    #             cookie_string = "; ".join([f"{k}={v}" for k, v in self.cookies.items()])
    #             crawl_options["headers"]["Cookie"] = cookie_string
            
    #         # 添加延迟
    #         if self.request_delay > 0:
    #             crawl_options["delay"] = int(self.request_delay * 1000)  # 转换为毫秒
            
    #         # 添加超时
    #         if self.timeout:
    #             crawl_options["timeout"] = self.timeout
            
    #         # 添加代理
    #         if self.proxy:
    #             crawl_options["proxy"] = 'basic'
            
    #         # 添加包含和排除模式
    #         if self.included_patterns:
    #             crawl_options["include_patterns"] = self.included_patterns
            
    #         if self.excluded_patterns:
    #             crawl_options["exclude_patterns"] = self.excluded_patterns
            
    #         # 调用Firecrawl API开始爬取
    #         logger.info(f"开始爬取网站: {self.base_url}")
    #         response: CrawlResponse = self.client.crawl_url(
    #             self.base_url,
    #             ignore_sitemap=True,
    #             limit=self.max_urls,
    #             scrape_options=ScrapeOptions(**crawl_options),
    #         )
    #         print("response", response)
            
    #         # 获取任务ID
    #         job_id = response.id
    #         if not job_id:
    #             raise FirecrawlError(f"未从API响应中获取到job_id: {response}")
            
    #         self.active_job_id = job_id
    #         logger.info(f"爬取任务已启动，任务ID: {job_id}")
            
    #         # 轮询查询爬取状态
    #         poll_interval = 10  # 轮询间隔（秒）
    #         while self.in_progress:
    #             try:
    #                 job_status: CrawlStatusResponse = self.client.check_crawl_status(job_id)
    #                 status = job_status.status
                    
    #                 if status == "completed":
    #                     logger.info(f"爬取任务完成: {job_id}")
                        
    #                     # 获取爬取结果
    #                     job_result: List[FirecrawlDocument] = job_status.data
                        
    #                     # 处理爬取到的页面
    #                     print("job_result", job_status)
    #                     if job_result:
    #                         for page in job_result:
    #                             url = page.url
    #                             if url:
    #                                 self.crawled_urls.add(url)
                                    
    #                                 # 提取内容
    #                                 content = ""
    #                                 if "markdown" in page and "markdown" in self.formats:
    #                                     content = page.markdown
    #                                 elif "html" in page and "html" in self.formats:
    #                                     content = page.html
    #                                 elif "links" in page and "links" in self.formats:
    #                                     content = page.links
                                    
    #                                 # 构建元数据
    #                                 metadata = {
    #                                     "url": url,
    #                                     "timestamp": time.time(),
    #                                     "source": urlparse(url).netloc,
    #                                 }
                                    
    #                                 # 添加更多元数据
    #                                 if "title" in page:
    #                                     metadata["title"] = page.title
    #                                 if "description" in page:
    #                                     metadata["description"] = page.description
                                    
    #                                 # 提取链接
    #                                 links = []
    #                                 if "links" in page:
    #                                     links = page.links
                                    
    #                                 # 添加链接到元数据
    #                                 metadata["related_links"] = links
                                    
    #                                 # 保存结果
    #                                 self.results[url] = {
    #                                     "content": content,
    #                                     "metadata": metadata,
    #                                     "links": links
    #                                 }
                                    
    #                                 # 如果有回调函数，调用它
    #                                 print("有回调函数" if self.on_page_crawled else "没有回调函数")
    #                                 print("Callback:url, content, metadata", url, content, metadata)
    #                                 if self.on_page_crawled:
    #                                     self.on_page_crawled(url, content, metadata)
                        
    #                     break
                    
    #                 elif status == "failed":
    #                     error_message = job_status.get("error", "未知错误")
    #                     logger.error(f"爬取任务失败: {error_message}")
    #                     self.failed_urls[self.base_url] = error_message
    #                     break
                    
    #                 elif status == "scraping":
    #                     # 更新爬取统计
    #                     data: List[FirecrawlDocument] = job_status.data
    #                     total = job_status.total
                        
    #                     logger.info(f"爬取进度: 已爬取 {len(data)}/{total} 页")
                        
    #                     # 等待一段时间再次查询
    #                     time.sleep(poll_interval)
                    
    #                 else:
    #                     logger.warning(f"未知的任务状态: {status}")
    #                     break
                
    #             except Exception as e:
    #                 logger.error(f"查询爬取状态时发生错误: {str(e)}")
    #                 self.failed_urls[self.base_url] = str(e)
    #                 break
        
    #     except Exception as e:
    #         logger.exception(f"爬取过程中发生错误: {str(e)}")
    #         self.failed_urls[self.base_url] = str(e)
        
    #     finally:
    #         self.in_progress = False
    #         self.end_time = datetime.now()
        
    #     # 返回爬取统计信息
    #     return {
    #         "status": "completed",
    #         "crawled_count": len(self.crawled_urls),
    #         "failed_count": len(self.failed_urls),
    #         "duration": self.end_time - self.start_time,
    #         "crawled_urls": list(self.crawled_urls),
    #         "failed_urls": self.failed_urls
    #     }
    
    def discover_sitemap(self) -> List[str]:
        """
        尝试发现并解析网站的sitemap
        
        Returns:
            List[str]: 从sitemap中提取的URL列表
        """
        try:
            # 在v2 API中可能没有discover_sitemap方法，需要用其他方式实现
            # 这里尝试使用搜索功能
            logger.info(f"尝试发现网站 {self.base_url} 的URLs")
            
            urls = []
            try:
                # 先尝试获取robots.txt中的sitemap信息
                base_domain = urlparse(self.base_url).netloc
                robots_url = f"http://{base_domain}/robots.txt"
                
                # 抓取robots.txt
                robots_response = self.client.scrape_url(
                    robots_url, 
                    formats=["content"],
                    timeout=self.timeout
                )
                
                # 简单解析robots.txt查找Sitemap
                if "content" in robots_response:
                    content = robots_response["content"]
                    lines = content.split("\n")
                    for line in lines:
                        if line.lower().startswith("sitemap:"):
                            sitemap_url = line.split(":", 1)[1].strip()
                            logger.info(f"在robots.txt中找到sitemap: {sitemap_url}")
                            
                            # 抓取sitemap
                            sitemap_response = self.client.scrape_url(
                                sitemap_url,
                                formats=["content"],
                                timeout=self.timeout
                            )
                            
                            # 简单解析sitemap XML
                            if "content" in sitemap_response:
                                sitemap_content = sitemap_response["content"]
                                # 非常简单的XML解析，实际使用应该用XML解析库
                                import re
                                loc_tags = re.findall(r"<loc>(.*?)</loc>", sitemap_content)
                                urls.extend(loc_tags)
            except Exception as e:
                logger.warning(f"通过robots.txt获取sitemap失败: {str(e)}")
                
            # 如果没有从robots.txt获取到urls，尝试常见的sitemap位置
            if not urls:
                common_sitemap_urls = [
                    f"{self.base_url}/sitemap.xml",
                    f"{self.base_url}/sitemap_index.xml",
                    f"{self.base_url}/sitemap/"
                ]
                
                for sitemap_url in common_sitemap_urls:
                    try:
                        # 抓取sitemap
                        sitemap_response = self.client.scrape_url(
                            sitemap_url,
                            formats=["content"],
                            timeout=self.timeout
                        )
                        
                        # 简单解析sitemap XML
                        if "content" in sitemap_response:
                            sitemap_content = sitemap_response["content"]
                            # 非常简单的XML解析，实际使用应该用XML解析库
                            import re
                            loc_tags = re.findall(r"<loc>(.*?)</loc>", sitemap_content)
                            if loc_tags:
                                urls.extend(loc_tags)
                                logger.info(f"从 {sitemap_url} 获取到 {len(loc_tags)} 个URL")
                                break
                    except Exception as e:
                        logger.warning(f"抓取 {sitemap_url} 失败: {str(e)}")
            
            logger.info(f"从sitemap中发现了 {len(urls)} 个URL")
            return urls
            
        except Exception as e:
            logger.error(f"发现sitemap时发生错误: {str(e)}")
            return []
    
    def stop(self) -> None:
        """
        停止爬虫
        """
        if not self.in_progress:
            logger.info("爬虫未在运行")
            return
        
        try:
            # 如果有活动的任务，尝试取消它
            if self.active_job_id:
                logger.info(f"尝试取消爬取任务: {self.active_job_id}")
                self.client.cancel_crawl(self.active_job_id)
                logger.info(f"爬取任务已取消: {self.active_job_id}")
        except Exception as e:
            logger.error(f"取消爬取任务时发生错误: {str(e)}")
        
        # 更新状态
        self.in_progress = False
        self.end_time = datetime.now()
        logger.info("爬虫已停止")
    
    def add_url(self, url: str, depth: int = 0) -> None:
        """
        添加URL到爬取队列
        注意：由于使用Firecrawl API，此方法仅在单页爬取模式下有效
        
        Args:
            url: 要添加的URL
            depth: URL的深度
        """
        if self.is_valid_url(url) and url not in self.crawled_urls:
            with self.lock:
                # 检查队列中是否已有此URL
                if not any(item["url"] == url for item in self.url_queue):
                    self.url_queue.append({
                        "url": url,
                        "depth": depth
                    })
                    logger.debug(f"添加URL到队列: {url}")
    
    def close(self):
        """
        关闭爬虫并释放资源
        """
        # 如果爬虫正在运行，首先停止它
        if self.in_progress:
            self.stop()
        
        # 清理资源
        self.client = None
        logger.info("Firecrawl爬虫已关闭") 