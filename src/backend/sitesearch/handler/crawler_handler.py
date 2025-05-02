import logging
import time
import json
from typing import Dict, Any, Optional, List
import hashlib
import re
import base64
from asgiref.sync import sync_to_async

from src.backend.sitesearch.handler.base_handler import BaseHandler, SkipError, StatusCodeError
from src.backend.sitesearch.crawler.httpx_worker import HttpxWorker

class CrawlerHandler(BaseHandler):
    """爬虫Handler，用于从队列获取URL并进行爬取"""
    
    def __init__(self, 
                 redis_url: str,
                 component_type: str,
                 input_queue: str = "url",
                 output_queue: str = "crawler",
                 handler_id: str = None,
                 batch_size: int = 1,  # 爬虫通常一次处理一个URL
                 sleep_time: float = 0.5,  # 爬虫休眠时间稍长，避免过于频繁请求
                 start_delay: float = 0.0,
                 max_retries: int = 3,
                 crawler_config: Dict[str, Any] = None,
                 auto_exit: bool = False):
        """
        初始化爬虫Handler
        
        Args:
            redis_url: Redis连接URL
            input_queue: 输入队列名称，默认为"url"
            output_queue: 输出队列名称，默认为"crawl"
            handler_id: Handler标识符
            batch_size: 批处理大小
            sleep_time: 队列为空时的睡眠时间（秒）
            max_retries: 最大重试次数
            crawler_type: 爬虫类型，默认为"httpx"
            crawler_config: 爬虫配置
        """
        super().__init__(
            redis_url=redis_url,
            component_type=component_type,
            input_queue=input_queue,
            output_queue=output_queue,
            handler_id=handler_id,
            batch_size=batch_size,
            sleep_time=sleep_time,
            start_delay=start_delay,
            max_retries=max_retries,
            auto_exit=auto_exit
        )
        
        # 初始化配置
        self.crawler_config = crawler_config or {}
        self.regpattern = self.crawler_config.pop("regpattern", "*")
        self.crawler_type = self.crawler_config.pop("crawler_type", "httpx")
        self.bfs = self.crawler_config.pop("bfs", True)

        # 初始化爬虫
        self._init_crawler()

        print(f"爬虫初始化完成，监听队列：{self.input_queue}，输出队列：{self.output_queue}")
        
        # 爬取历史，用于去重
        # self.crawled_urls = set()  改用基于redis的共享爬取历史
        self.crawled_urls_key = f"crawler:crawled_urls:{self.input_queue}"
        
        self.logger = logging.getLogger(f"CrawlerHandler:{self.handler_id}")
        self.logger.setLevel(logging.WARNING)
    
    def _init_crawler(self):
        """初始化爬虫实例"""
        if self.crawler_type == "httpx":
            self.crawler = HttpxWorker(
                base_url=self.crawler_config.get("base_url", ""),
                **self.crawler_config
            )
        else:
            raise ValueError(f"不支持的爬虫类型: {self.crawler_type}")
    
    def _is_url_match_pattern(self, url: str) -> bool:
        """检查URL是否匹配正则表达式模式"""
        # 如果是通配符*，则匹配所有URL
        if self.regpattern == "*":
            return True
        
        try:
            return bool(re.match(self.regpattern, url))
        except re.error:
            self.logger.warning(f"正则表达式格式错误: {self.regpattern}，将使用默认全匹配")
            return True
    
    def _generate_content_hash(self, content: str) -> str:
        """生成内容哈希值"""
        if not content:
            return ""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _is_url_crawled(self, url: str) -> bool:
        """检查URL是否已爬取"""
        return self.redis_client.sismember(self.crawled_urls_key, url)

    def _add_url_to_crawled(self, url: str):
        """添加URL到爬取历史"""
        self.redis_client.sadd(self.crawled_urls_key, url)

    def _get_crawled_urls_length(self) -> int:
        """获取爬取历史长度"""
        return self.redis_client.scard(self.crawled_urls_key)

    async def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理爬取任务
        
        Args:
            task_data: 包含爬取URL和配置的任务数据
            
        Returns:
            Dict[str, Any]: 爬取结果
        """
        from src.backend.sitesearch.storage.manager import DataStorage
        # 提取URL和额外参数
        url = task_data.get('url')
        if not url:
            raise ValueError("任务数据缺少必要字段: url")
        
        # 检查是否已爬取过该URL
        url = self.crawler.normalize_url(url)
        if self._is_url_crawled(url):
            self.logger.info(f"URL已爬取，跳过: {url}")
            return {
                "url": url,
                "status": "skipped",
                "reason": "already_crawled"
            }
        
        if self._get_crawled_urls_length() >= self.crawler_config.get("max_urls"):
            self.logger.info(f"爬取数量达到限制，跳过: {url}")
            # 清空队列
            self.logger.info(f"清空队列: {self.input_queue}")
            self.redis_client.ltrim(self.input_queue, 0, 0)
            return {
                "url": url,
                "status": "skipped",
                "reason": "limit_reached"
            }
        
        # 获取站点ID
        site_id = task_data.get('site_id', 'default')
        
        # 记录开始时间
        start_time = time.time()
        self.logger.info(f"开始爬取URL: {url}")
        storage = DataStorage()
        
        try:
            # 执行爬取
            crawl_result = self.crawler.crawl_page(url)

            if 'redirect_url' in crawl_result:
                crawl_result['url'] = crawl_result['redirect_url']
            
            # 计算内容哈希
            if 'content' in crawl_result:
                content = crawl_result['content']
                if isinstance(content, bytes):
                    content_hash = hashlib.sha256(content).hexdigest()
                    # 二进制content数据编码为b64，后续存储要用
                    crawl_result['content'] = base64.b64encode(content).decode('utf-8')
                else:
                    content_hash = self._generate_content_hash(content)
                    # 字符串content先编码为bytes再编码为b64
                    crawl_result['content'] = base64.b64encode(content.encode('utf-8')).decode('utf-8')

                crawl_result['content_hash'] = content_hash
            
            # 添加元数据
            crawl_result['site_id'] = site_id
            crawl_result['crawler_id'] = self.handler_id
            crawl_result['crawler_type'] = self.crawler_type
            crawl_result['crawler_config'] = self.crawler_config
            crawl_result['timestamp'] = time.time()

            # 获取links，将没有爬取过的links添加到队列中
            if not self._is_url_crawled(crawl_result['url']) and self.bfs:
                links = crawl_result.get('links', [])
                for link in links:
                    link = self.crawler.normalize_url(link)
                    if not self._is_url_crawled(link) and self._is_url_match_pattern(link):
                        self.redis_client.lpush(self.input_queue, json.dumps({
                            "url": link,
                            "site_id": site_id,
                            "timestamp": time.time(),
                            "task_id": f"task-{int(time.time())}"
                        }))
            self._add_url_to_crawled(crawl_result['url'])
            
            # 记录处理时间
            processing_time = time.time() - start_time
            self.logger.info(f"URL爬取完成: {url} mimetype:{crawl_result.get('mimetype')}, 耗时: {processing_time:.2f}秒")

            # 检查版本
            exists, existing_doc, operation = await sync_to_async(storage.check_exists)(
                url=url, 
                site_id=site_id,
                content_hash=crawl_result.get('content_hash')
            )
            if operation == "skip":
                self.logger.info(f"跳过文档: {url}")
                raise SkipError(f"跳过文档: {url} 因为版本相同")
            
            return crawl_result
        except SkipError as e:
            self.logger.info(f"URL爬取跳过: {url}, 原因: {str(e)}")
            raise e
        except StatusCodeError as e:
            self.logger.info(f"URL爬取跳过: {url}, 原因: {str(e)}")
            status_code = e.status_code
            exists, existing_doc, operation = await sync_to_async(storage.check_exists)(
                url=url, 
                site_id=site_id
            )
            # operation 可能的值：skip, new_site, edit, new
            if operation == "skip":
                # 文档在当前站点中存在且内容未变化，现在访问不了，需要删除
                return {
                    "url": url,
                    "crawler_operation": "delete",
                    "status_code": status_code,
                    "timestamp": time.time(),
                    "site_id": site_id
                }
            elif operation == "new_site" or operation == "new":
                # 跳过
                return {
                    "url": url,
                    "crawler_operation": "skip",
                    "status_code": status_code,
                    "timestamp": time.time(),
                    "site_id": site_id
                }
            else:
                raise e
        except Exception as e:
            # 记录错误
            self.logger.exception(f"爬取URL时发生错误: {url}, 错误: {str(e)}")
            return {
                "url": url,
                "status": "error",
                "error": str(e),
                "timestamp": time.time(),
                "site_id": site_id
            } 
        finally:
            # 记录已爬取的URL
            self._add_url_to_crawled(url)
