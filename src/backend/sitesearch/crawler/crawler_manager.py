"""
爬虫管理器模块
提供网站爬虫的管理功能，包括爬虫创建、启动、停止和监控
"""

import logging
import os
import json
import time
from typing import Dict, List, Any, Optional, Union, Callable, Tuple, Type
from datetime import datetime
import threading

from .base_crawler import BaseCrawler, BaseCrawlerConfig
from .httpx_worker import HttpxWorker
from .firecrawl_worker import FirecrawlWorker

# 配置日志
logger = logging.getLogger('crawler_manager')

class CrawlerManager:
    """
    爬虫管理器，负责创建、配置、启动和监控爬虫
    """
    
    def __init__(self, storage_dir: str = "./crawl_data"):
        """
        初始化爬虫管理器
        
        Args:
            storage_dir: 爬取数据存储目录
        """
        self.storage_dir = storage_dir
        self.active_crawlers: Dict[str, BaseCrawler] = {}
        self.crawler_threads: Dict[str, threading.Thread] = {}
        self.crawler_statuses: Dict[str, Dict[str, Any]] = {}
        self.crawl_results: Dict[str, List[Dict[str, Any]]] = {}
        
        # 确保存储目录存在
        os.makedirs(storage_dir, exist_ok=True)
        
        # 初始化可用的爬虫类型
        self.available_crawler_types = {
            "httpx": HttpxWorker,
            "firecrawl": FirecrawlWorker,
            # 未来可以添加更多爬虫类型
        }
    
    def create_crawler(self, 
                       crawler_id: str,
                       crawler_type: str = "httpx",
                       base_url: str = "",
                       config: BaseCrawlerConfig = None,
                       callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> str:
        """
        创建新的爬虫实例
        
        Args:
            crawler_id: 爬虫ID，如果不指定则自动生成
            crawler_type: 爬虫类型，默认为"httpx"
            base_url: 起始URL
            config: 爬虫配置
            callback: 页面处理回调函数
            
        Returns:
            str: 爬虫ID
        
        Raises:
            ValueError: 如果爬虫类型无效或者爬虫ID已存在
        """
        # 验证爬虫类型
        if crawler_type not in self.available_crawler_types:
            raise ValueError(f"无效的爬虫类型: {crawler_type}。可用类型: {', '.join(self.available_crawler_types.keys())}")
        
        # 验证爬虫ID是否已存在
        if crawler_id in self.active_crawlers:
            raise ValueError(f"爬虫ID '{crawler_id}' 已存在")
        
        # 准备配置
        crawler_config = config or {}
        crawler_config["base_url"] = base_url
        
        # 设置页面处理回调
        if callback:
            crawler_config["on_page_crawled"] = callback
        else:
            # 默认回调函数，保存结果到内部存储
            def default_callback(url, content, metadata):
                if crawler_id not in self.crawl_results:
                    self.crawl_results[crawler_id] = []
                self.crawl_results[crawler_id].append({
                    "url": url,
                    "content": content,
                    "metadata": metadata,
                    "timestamp": time.time()
                })
            
            crawler_config["on_page_crawled"] = default_callback
        
        # 创建爬虫实例，处理特殊配置
        crawler_class = self.available_crawler_types[crawler_type]
        
        # 对于 FirecrawlWorker 特殊处理
        if crawler_type == "firecrawl":
            # 确保API密钥存在
            if "api_key" not in crawler_config and "FIRECRAWL_API_KEY" not in os.environ:
                raise ValueError("使用FirecrawlWorker必须提供API密钥，通过config['api_key']或环境变量FIRECRAWL_API_KEY")
        
        # 创建爬虫实例
        crawler = crawler_class(**crawler_config)
        
        # 注册爬虫
        self.active_crawlers[crawler_id] = crawler
        self.crawler_statuses[crawler_id] = {
            "id": crawler_id,
            "type": crawler_type,
            "base_url": base_url,
            "status": "created",
            "created_at": datetime.now().isoformat(),
            "config": crawler_config,
            "stats": {
                "pages_crawled": 0,
                "pages_failed": 0,
                "start_time": None,
                "end_time": None,
                "total_time": None
            }
        }
        
        logger.info(f"已创建爬虫: {crawler_id} (类型: {crawler_type}, URL: {base_url})")
        
        return crawler_id
    
    def start_crawler(self, crawler_id: str, discover_sitemap: bool = False) -> bool:
        """
        启动指定的爬虫
        
        Args:
            crawler_id: 爬虫ID
            discover_sitemap: 是否尝试发现和解析sitemap
            
        Returns:
            bool: 是否成功启动
            
        Raises:
            ValueError: 如果爬虫ID不存在
        """
        if crawler_id not in self.active_crawlers:
            raise ValueError(f"爬虫ID '{crawler_id}' 不存在")
        
        crawler = self.active_crawlers[crawler_id]
        status = self.crawler_statuses[crawler_id]
        
        # 如果爬虫已经在运行，返回失败
        if status["status"] == "running":
            logger.warning(f"爬虫 {crawler_id} 已经在运行")
            return False
        
        # 更新状态
        status["status"] = "running"
        status["stats"]["start_time"] = datetime.now()
        
        # 定义爬虫线程函数
        def crawler_thread_func():
            try:
                # 如果需要，尝试从sitemap获取URL
                if discover_sitemap:
                    sitemap_urls = crawler.discover_sitemap()
                    if sitemap_urls:
                        logger.info(f"爬虫 {crawler_id} 从sitemap发现了 {len(sitemap_urls)} 个URL")
                        # 将发现的URL添加到爬虫的待爬队列
                        for url in sitemap_urls:
                            crawler.add_url(url)
                
                # 开始爬取
                crawler.crawl()

                # 更新状态
                status["status"] = "completed"
                status["stats"]["end_time"] = datetime.now()
                
                # 计算总时间
                start_time = status["stats"]["start_time"]
                end_time = status["stats"]["end_time"]
                total_seconds = (end_time - start_time).total_seconds()
                status["stats"]["total_time"] = total_seconds
                
                logger.info(f"爬虫 {crawler_id} 已完成，耗时 {total_seconds:.2f} 秒")
                
            except Exception as e:
                logger.exception(f"爬虫 {crawler_id} 发生错误: {str(e)}")
                status["status"] = "error"
                status["error"] = str(e)
            finally:
                # 关闭爬虫
                try:
                    crawler.close()
                except Exception as e:
                    logger.exception(f"关闭爬虫 {crawler_id} 时发生错误: {str(e)}")
        
        # 创建并启动爬虫线程
        crawler_thread = threading.Thread(target=crawler_thread_func)
        crawler_thread.daemon = True
        crawler_thread.start()
        
        # 保存线程引用
        self.crawler_threads[crawler_id] = crawler_thread
        
        logger.info(f"爬虫 {crawler_id} 已启动")
        return True
    
    def stop_crawler(self, crawler_id: str) -> bool:
        """
        停止指定的爬虫
        
        Args:
            crawler_id: 爬虫ID
            
        Returns:
            bool: 是否成功停止
            
        Raises:
            ValueError: 如果爬虫ID不存在
        """
        if crawler_id not in self.active_crawlers:
            raise ValueError(f"爬虫ID '{crawler_id}' 不存在")
        
        crawler = self.active_crawlers[crawler_id]
        status = self.crawler_statuses[crawler_id]
        
        # 如果爬虫不在运行，返回失败
        if status["status"] != "running":
            logger.warning(f"爬虫 {crawler_id} 当前不在运行，状态为: {status['status']}")
            return False
        
        # 停止爬虫
        try:
            crawler.stop()
            status["status"] = "stopped"
            status["stats"]["end_time"] = datetime.now().isoformat()
            
            # 计算总时间
            start_time = datetime.fromisoformat(status["stats"]["start_time"])
            end_time = datetime.fromisoformat(status["stats"]["end_time"])
            total_seconds = (end_time - start_time).total_seconds()
            status["stats"]["total_time"] = total_seconds
            
            logger.info(f"爬虫 {crawler_id} 已停止，运行时间 {total_seconds:.2f} 秒")
            return True
            
        except Exception as e:
            logger.error(f"停止爬虫 {crawler_id} 时发生错误: {str(e)}")
            status["error"] = str(e)
            return False
    
    def get_crawler_status(self, crawler_id: str) -> Dict[str, Any]:
        """
        获取爬虫的状态
        
        Args:
            crawler_id: 爬虫ID
            
        Returns:
            Dict[str, Any]: 爬虫状态
            
        Raises:
            ValueError: 如果爬虫ID不存在
        """
        if crawler_id not in self.crawler_statuses:
            raise ValueError(f"爬虫ID '{crawler_id}' 不存在")
        
        status = self.crawler_statuses[crawler_id]
        
        # 如果爬虫正在运行，更新实时统计信息
        if status["status"] == "running" and crawler_id in self.active_crawlers:
            crawler = self.active_crawlers[crawler_id]
            crawler_status = crawler.get_status()
            status["stats"].update(crawler_status)
        
        return status
    
    def get_all_crawler_statuses(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有爬虫的状态
        
        Returns:
            Dict[str, Dict[str, Any]]: 所有爬虫的状态
        """
        # 更新每个运行中爬虫的状态
        for crawler_id, status in self.crawler_statuses.items():
            if status["status"] == "running" and crawler_id in self.active_crawlers:
                crawler = self.active_crawlers[crawler_id]
                crawler_status = crawler.get_status()
                status["stats"].update(crawler_status)
        
        return self.crawler_statuses
    
    def delete_crawler(self, crawler_id: str) -> bool:
        """
        删除指定的爬虫
        
        Args:
            crawler_id: 爬虫ID
            
        Returns:
            bool: 是否成功删除
            
        Raises:
            ValueError: 如果爬虫ID不存在
        """
        if crawler_id not in self.active_crawlers:
            raise ValueError(f"爬虫ID '{crawler_id}' 不存在")
        
        # 如果爬虫在运行，先停止它
        status = self.crawler_statuses[crawler_id]
        if status["status"] == "running":
            self.stop_crawler(crawler_id)
        
        # 删除爬虫
        crawler = self.active_crawlers.pop(crawler_id)
        try:
            crawler.close()
        except Exception as e:
            logger.error(f"关闭爬虫 {crawler_id} 时发生错误: {str(e)}")
        
        # 删除相关引用
        self.crawler_statuses.pop(crawler_id, None)
        self.crawler_threads.pop(crawler_id, None)
        
        logger.info(f"爬虫 {crawler_id} 已删除")
        return True
    
    def save_results(self, crawler_id: str, file_format: str = "json") -> str:
        """
        保存爬虫结果到文件
        
        Args:
            crawler_id: 爬虫ID
            file_format: 保存格式，目前支持"json"
            
        Returns:
            str: 保存的文件路径
            
        Raises:
            ValueError: 如果爬虫ID不存在或格式不支持
        """
        if file_format.lower() != "json":
            raise ValueError(f"不支持的文件格式: {file_format}。当前仅支持'json'")
        
        # 准备文件名
        timestamp = int(time.time())
        filename = f"{crawler_id}_{timestamp}.json"
        filepath = os.path.join(self.storage_dir, filename)
        
        # 保存结果
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.crawl_results[crawler_id], f, ensure_ascii=False, indent=2)
        
        logger.info(f"爬虫 {crawler_id} 的结果已保存到 {filepath}")
        return filepath
    
    def clear_results(self, crawler_id: str = None) -> bool:
        """
        清除爬虫结果
        
        Args:
            crawler_id: 爬虫ID，如果为None则清除所有结果
            
        Returns:
            bool: 是否成功清除
        """
        if crawler_id is None:
            # 清除所有结果
            self.crawl_results.clear()
            logger.info("已清除所有爬虫结果")
        elif crawler_id in self.crawl_results:
            # 清除指定爬虫的结果
            del self.crawl_results[crawler_id]
            logger.info(f"已清除爬虫 {crawler_id} 的结果")
        else:
            logger.warning(f"爬虫ID '{crawler_id}' 不存在或没有结果")
            return False
        
        return True
    
    def get_crawler_results(self, crawler_id: str) -> List[Dict[str, Any]]:
        """
        获取爬虫的结果
        
        Args:
            crawler_id: 爬虫ID
            
        Returns:
            List[Dict[str, Any]]: 爬虫结果
            
        Raises:
            ValueError: 如果爬虫ID不存在
        """
        if crawler_id not in self.crawl_results:
            raise ValueError(f"爬虫ID '{crawler_id}' 不存在或没有结果")
        
        return self.crawl_results[crawler_id]
    
    def wait_for_crawler(self, crawler_id: str, timeout: Optional[float] = None) -> bool:
        """
        等待爬虫完成
        
        Args:
            crawler_id: 爬虫ID
            timeout: 超时时间(秒)，None表示无限等待
            
        Returns:
            bool: 爬虫是否已完成
            
        Raises:
            ValueError: 如果爬虫ID不存在
        """
        if crawler_id not in self.crawler_threads:
            raise ValueError(f"爬虫ID '{crawler_id}' 不存在或未启动")
        
        thread = self.crawler_threads[crawler_id]
        thread.join(timeout)
        return not thread.is_alive()
    
    def close(self):
        """
        关闭管理器并停止所有爬虫
        """
        logger.info("关闭爬虫管理器...")
        
        # 停止所有运行中的爬虫
        for crawler_id in list(self.active_crawlers.keys()):
            status = self.crawler_statuses.get(crawler_id, {})
            if status.get("status") == "running":
                try:
                    self.stop_crawler(crawler_id)
                except Exception as e:
                    logger.error(f"停止爬虫 {crawler_id} 时发生错误: {str(e)}")
        
        # 关闭所有爬虫
        for crawler_id, crawler in list(self.active_crawlers.items()):
            try:
                crawler.close()
            except Exception as e:
                logger.error(f"关闭爬虫 {crawler_id} 时发生错误: {str(e)}")
        
        logger.info("爬虫管理器已关闭") 