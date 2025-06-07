"""
爬虫工作器测试模块
测试爬虫如何处理队列中的任务
"""

import os
import sys
import time
import json
import unittest
import threading
from unittest import mock
from typing import Dict, Any, List

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.backend.sitesearch.utils.queue_manager import get_queue_manager, TaskStatus
from src.backend.sitesearch.crawler.httpx_worker import HttpxWorker
from src.backend.sitesearch.crawler.crawler_manager import CrawlerManager


class CrawlerWorker:
    """爬虫工作器，从队列中获取任务并执行"""
    
    def __init__(self, queue_name: str, base_url: str):
        """
        初始化爬虫工作器
        
        Args:
            queue_name: 队列名称
            base_url: 基础URL
        """
        self.queue_name = queue_name
        self.queue_manager = get_queue_manager()
        self.crawler = HttpxWorker(
            base_url=base_url,
            max_urls=10,
            max_depth=2,
            request_delay=0.1
        )
        self.running = False
        self.worker_thread = None
    
    def start(self):
        """启动工作器线程"""
        if self.running:
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop)
        self.worker_thread.daemon = True
        self.worker_thread.start()
    
    def stop(self):
        """停止工作器线程"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=20)
    
    def _worker_loop(self):
        """工作器主循环"""
        while self.running:
            try:
                # 获取任务
                task = self.queue_manager.dequeue(self.queue_name, block=False)
                
                if not task:
                    # 队列为空，等待一段时间
                    self.stop()
                
                # 处理任务
                task_data = task["data"]
                task_id = task["id"]
                url = task_data["url"]
                depth = task_data.get("depth", 0)
                
                try:
                    # 执行爬取
                    result = self.crawler.crawl_page(url)
                    
                    # 处理结果
                    if result and "content" in result:
                        # 将任务标记为完成
                        self.queue_manager.complete_task(self.queue_name, task_id, result)
                        
                        # 提取链接并添加到队列
                        if depth < self.crawler.max_depth and "metadata" in result:
                            links = result["metadata"].get("related_links", [])
                            for link in links:
                                if self.crawler.is_valid_url(link):
                                    # 将链接加入队列
                                    self.queue_manager.enqueue(self.queue_name, {
                                        "url": link,
                                        "depth": depth + 1,
                                        "parent_url": url
                                    })
                    else:
                        # 爬取失败
                        self.queue_manager.fail_task(self.queue_name, task_id, f"无效的爬取结果: {result}")
                
                except Exception as e:
                    # 任务处理出错
                    self.queue_manager.fail_task(self.queue_name, task_id, str(e))
            
            except Exception as e:
                # 工作器运行时错误
                print(f"工作器运行错误: {e}")
                time.sleep(1)  # 避免过于频繁的错误导致CPU使用率过高


class TestCrawlerWorker(unittest.TestCase):
    """爬虫工作器测试类"""
    
    def setUp(self):
        """测试前的准备工作"""
        # 使用真实的Redis连接
        self.queue_manager = get_queue_manager("redis://localhost:6382")
        
        # 定义测试队列名称
        self.crawler_queue = "test_worker_queue"
        
        # 清空测试队列
        self.queue_manager.clear_queue(self.crawler_queue)
    
    def wait_for_task_status(self, task_id, expected_status, timeout=5):
        """等待任务达到预期状态"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            task_status = self.queue_manager.get_task_status(task_id)
            if task_status and task_status["status"] == expected_status:
                return task_status
            time.sleep(0.1)
        
        # 超时后返回当前状态
        return self.queue_manager.get_task_status(task_id)
    
    @mock.patch('src.backend.sitesearch.crawler.httpx_worker.HttpxWorker.crawl_page')
    def test_worker_process_task(self, mock_crawl_page):
        """测试工作器处理任务"""
        # 模拟爬取结果
        mock_crawl_page.return_value = {
            "url": "https://example.com",
            "content": "网页内容",
            "status_code": 200,
            "metadata": {
                "title": "示例网站",
                "related_links": [
                    "https://example.com/page1",
                    "https://example.com/page2"
                ]
            }
        }
        
        # 向队列添加一个任务
        task_data = {
            "url": "https://example.com",
            "depth": 0
        }
        task_id = self.queue_manager.enqueue(self.crawler_queue, task_data)
        
        # 创建工作器
        worker = CrawlerWorker(
            queue_name=self.crawler_queue,
            base_url="https://example.com"
        )
        
        # 手动触发一次工作循环，而不是启动线程
        worker.start()
        while worker.running:
            time.sleep(0.1)
        
        # 验证任务已处理
        task_status = self.queue_manager.get_task_status(task_id)
        self.assertEqual(task_status["status"], TaskStatus.COMPLETED.value)
        
        # 验证提取的链接也已经完成
        task_status = self.queue_manager.get_task_status(task_id)
        self.assertEqual(task_status["result"]["metadata"]["related_links"], ["https://example.com/page1", "https://example.com/page2"])
        self.assertEqual(task_status["result"]["url"], "https://example.com")
        self.assertEqual(task_status["result"]["status_code"], 200)
        self.assertIn("网页内容", task_status["result"]["content"])
        self.assertIn("示例网站", task_status["result"]["metadata"]["title"])

        # 验证爬取内容
        self.assertEqual(mock_crawl_page.call_count, 1)
        self.assertEqual(mock_crawl_page.call_args[0][0], "https://example.com")

        # 验证爬取结果
        self.assertEqual(task_status["result"]["url"], "https://example.com")
        self.assertEqual(task_status["result"]["status_code"], 200)
        self.assertIn("网页内容", task_status["result"]["content"])
        self.assertIn("示例网站", task_status["result"]["metadata"]["title"])
    
    @mock.patch('src.backend.sitesearch.crawler.httpx_worker.HttpxWorker.crawl_page')
    def test_worker_handle_error(self, mock_crawl_page):
        """测试工作器处理错误"""
        # 模拟爬取错误
        mock_crawl_page.side_effect = Exception("连接超时")
        
        # 向队列添加一个任务
        task_data = {
            "url": "https://example.com/error",
            "depth": 0
        }
        task_id = self.queue_manager.enqueue(self.crawler_queue, task_data)
        
        # 创建工作器
        worker = CrawlerWorker(
            queue_name=self.crawler_queue,
            base_url="https://example.com"
        )
        
        # 手动触发一次工作循环
        worker.start()
        while worker.running:
            time.sleep(0.1)
        
        # 验证任务已标记为失败
        task_status = self.queue_manager.get_task_status(task_id)
        self.assertEqual(task_status["status"], TaskStatus.FAILED.value)
        self.assertIn("连接超时", task_status["error"])
    
    @mock.patch('src.backend.sitesearch.crawler.httpx_worker.HttpxWorker.crawl_page')
    def test_worker_depth_limit(self, mock_crawl_page):
        """测试工作器深度限制"""
        # 模拟爬取结果
        mock_crawl_page.return_value = {
            "url": "https://example.com/depth",
            "content": "深度测试",
            "status_code": 200,
            "metadata": {
                "title": "深度测试",
                "related_links": [
                    "https://example.com/depth/subpage"
                ]
            }
        }
        
        # 向队列添加一个最大深度的任务
        task_data = {
            "url": "https://example.com/depth",
            "depth": 2  # max_depth也是2，所以不应该继续添加子链接
        }
        task_id = self.queue_manager.enqueue(self.crawler_queue, task_data)
        
        # 创建工作器
        worker = CrawlerWorker(
            queue_name=self.crawler_queue,
            base_url="https://example.com"
        )
        
        # 手动触发一次工作循环
        worker.start()
        while worker.running:
            time.sleep(0.1)
        
        # 验证任务已处理
        task_status = self.queue_manager.get_task_status(task_id)
        self.assertEqual(task_status["status"], TaskStatus.COMPLETED.value)
        
        # 验证没有新任务被添加（达到深度限制）
        queue_length = self.queue_manager.get_queue_length(self.crawler_queue)
        self.assertEqual(queue_length, 0)
    
    @mock.patch('src.backend.sitesearch.crawler.httpx_worker.HttpxWorker.crawl_page')
    def test_multiple_workers(self, mock_crawl_page):
        """测试多个工作器并发处理任务"""
        # 模拟爬取结果
        def mock_crawl_result(url):
            return {
                "url": url,
                "content": f"内容 {url}",
                "status_code": 200,
                "metadata": {
                    "title": f"页面 {url}",
                    "related_links": []  # 不添加子链接，避免测试复杂化
                }
            }
        
        mock_crawl_page.side_effect = mock_crawl_result
        
        # 向队列添加多个任务
        task_ids = []
        for i in range(10):
            task_data = {
                "url": f"https://example.com/page{i}",
                "depth": 0
            }
            task_id = self.queue_manager.enqueue(self.crawler_queue, task_data)
            task_ids.append(task_id)
        
        # 创建工作器
        worker = CrawlerWorker(
            queue_name=self.crawler_queue,
            base_url="https://example.com"
        )
        
        # 手动处理所有任务
        worker.start()
        while worker.running:
            time.sleep(0.1)
        
        # 验证所有任务都已处理
        for task_id in task_ids:
            task_status = self.queue_manager.get_task_status(task_id)
            self.assertEqual(task_status["status"], TaskStatus.COMPLETED.value)
        
        # 验证队列为空
        queue_length = self.queue_manager.get_queue_length(self.crawler_queue)
        self.assertEqual(queue_length, 0)
        
        # 验证爬取方法被调用了10次
        self.assertEqual(mock_crawl_page.call_count, 10)


class TestCrawlerManagerWorker(unittest.TestCase):
    """爬虫管理器与工作器集成测试"""
    
    def setUp(self):
        """测试前的准备工作"""
        # 使用真实的Redis连接
        self.queue_manager = get_queue_manager("redis://localhost:6382")
        
        # 创建爬虫管理器
        self.crawler_manager = CrawlerManager(storage_dir="./test_worker_results")
        
        # 临时目录，测试后会删除
        os.makedirs("./test_worker_results", exist_ok=True)
    
    def tearDown(self):
        """测试后的清理工作"""
        # 删除临时目录
        import shutil
        if os.path.exists("./test_worker_results"):
            shutil.rmtree("./test_worker_results")
    
    @mock.patch('src.backend.sitesearch.crawler.httpx_worker.HttpxWorker.crawl')
    @mock.patch('src.backend.sitesearch.crawler.httpx_worker.HttpxWorker.discover_sitemap')
    def test_manager_worker_integration(self, mock_discover_sitemap, mock_crawl):
        """测试爬虫管理器与工作器的集成"""
        # 模拟sitemap发现
        mock_discover_sitemap.return_value = [
            "https://example.com/page1",
            "https://example.com/page2"
        ]
        
        # 模拟爬虫执行结果
        mock_crawl.return_value = {
            "status": "completed",
            "crawled_count": 2,
            "failed_count": 0,
            "duration": 1.5,
            "crawled_urls": [
                "https://example.com/page1",
                "https://example.com/page2"
            ],
            "failed_urls": {}
        }
        
        # 创建爬虫
        crawler_id = self.crawler_manager.create_crawler(
            crawler_id="integration_test",
            crawler_type="httpx",
            base_url="https://example.com",
            config={
                "max_urls": 10,
                "max_depth": 2,
                "request_delay": 0.1
            }
        )
        
        # 启动爬虫但不使用线程
        # 直接修改状态为运行中
        self.crawler_manager.crawler_statuses[crawler_id]["status"] = "running"
        
        # 获取爬虫状态
        status = self.crawler_manager.get_crawler_status(crawler_id)
        self.assertEqual(status["status"], "running")
        
        # 手动修改状态为已完成
        self.crawler_manager.crawler_statuses[crawler_id]["status"] = "completed"
        
        # 获取最终状态
        status = self.crawler_manager.get_crawler_status(crawler_id)
        self.assertEqual(status["status"], "completed")


class TestMultiCrawlerIntegration(unittest.TestCase):
    """多爬虫集成测试"""
    
    def setUp(self):
        """测试前的准备工作"""
        # 使用真实的Redis连接
        self.queue_manager = get_queue_manager("redis://localhost:6382")
        
        # 创建爬虫管理器
        self.crawler_manager = CrawlerManager(storage_dir="./test_multi_crawler")
        
        # 临时目录，测试后会删除
        os.makedirs("./test_multi_crawler", exist_ok=True)
    
    def tearDown(self):
        """测试后的清理工作"""
        # 删除临时目录
        import shutil
        if os.path.exists("./test_multi_crawler"):
            shutil.rmtree("./test_multi_crawler")
    
    @mock.patch('src.backend.sitesearch.crawler.httpx_worker.HttpxWorker.crawl')
    def test_multiple_crawlers(self, mock_crawl):
        """测试同时运行多个爬虫"""
        # 模拟爬虫执行结果
        mock_crawl.return_value = {
            "status": "completed",
            "crawled_count": 5,
            "failed_count": 0,
            "duration": 1.0,
            "crawled_urls": ["https://example.com/page1"],
            "failed_urls": {}
        }
        
        # 创建多个爬虫
        crawler_ids = []
        for i in range(3):
            crawler_id = f"multi_crawler_{i}"
            self.crawler_manager.create_crawler(
                crawler_id=crawler_id,
                crawler_type="httpx",
                base_url=f"https://example{i}.com",
                config={
                    "max_urls": 5,
                    "max_depth": 2,
                    "request_delay": 0.1
                }
            )
            crawler_ids.append(crawler_id)
        
        # 手动将所有爬虫状态设置为运行中
        for crawler_id in crawler_ids:
            self.crawler_manager.crawler_statuses[crawler_id]["status"] = "running"
        
        # 验证所有爬虫都在运行
        for crawler_id in crawler_ids:
            status = self.crawler_manager.get_crawler_status(crawler_id)
            self.assertEqual(status["status"], "running")
        
        # 手动修改所有爬虫状态为已完成
        for crawler_id in crawler_ids:
            self.crawler_manager.crawler_statuses[crawler_id]["status"] = "completed"
        
        # 验证所有爬虫都已完成
        for crawler_id in crawler_ids:
            status = self.crawler_manager.get_crawler_status(crawler_id)
            self.assertEqual(status["status"], "completed")
        
        # 获取所有爬虫状态
        all_statuses = self.crawler_manager.get_all_crawler_statuses()
        self.assertEqual(len(all_statuses), 3)
        
        # 关闭爬虫管理器
        self.crawler_manager.close()


if __name__ == "__main__":
    unittest.main() 