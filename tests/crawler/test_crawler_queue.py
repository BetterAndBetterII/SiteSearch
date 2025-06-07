"""
爬虫队列测试模块
测试爬虫任务队列的各项功能
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
from src.backend.sitesearch.crawler.crawler_manager import CrawlerManager


class MockRedis:
    """Redis客户端的模拟实现，用于测试"""
    
    def __init__(self):
        self.data = {}
        self.lists = {}
        self.sets = {}
        self.hashes = {}
        self.pubsub_channels = {}
    
    def from_url(self, url):
        """模拟from_url方法"""
        return self
    
    def set(self, key, value):
        """模拟SET命令"""
        self.data[key] = value
        return True
    
    def get(self, key):
        """模拟GET命令"""
        return self.data.get(key)
    
    def delete(self, *keys):
        """模拟DEL命令"""
        count = 0
        for key in keys:
            if key in self.data:
                del self.data[key]
                count += 1
        return count
    
    def lpush(self, key, value):
        """模拟LPUSH命令"""
        if key not in self.lists:
            self.lists[key] = []
        self.lists[key].insert(0, value)
        return len(self.lists[key])
    
    def rpop(self, key):
        """模拟RPOP命令"""
        if key not in self.lists or not self.lists[key]:
            return None
        return self.lists[key].pop()
    
    def brpop(self, key, timeout=0):
        """模拟BRPOP命令"""
        if key not in self.lists or not self.lists[key]:
            if timeout == 0:
                # 模拟无限等待，实际上立即返回None
                return None
            time.sleep(0.1)  # 短暂睡眠模拟阻塞
            return None
        value = self.lists[key].pop()
        return (key, value)
    
    def llen(self, key):
        """模拟LLEN命令"""
        if key not in self.lists:
            return 0
        return len(self.lists[key])
    
    def lrange(self, key, start, end):
        """模拟LRANGE命令"""
        if key not in self.lists:
            return []
        if end == -1:
            end = len(self.lists[key])
        return self.lists[key][start:end]
    
    def sadd(self, key, *values):
        """模拟SADD命令"""
        if key not in self.sets:
            self.sets[key] = set()
        added = 0
        for value in values:
            if value not in self.sets[key]:
                self.sets[key].add(value)
                added += 1
        return added
    
    def srem(self, key, *values):
        """模拟SREM命令"""
        if key not in self.sets:
            return 0
        removed = 0
        for value in values:
            if value in self.sets[key]:
                self.sets[key].remove(value)
                removed += 1
        return removed
    
    def smembers(self, key):
        """模拟SMEMBERS命令"""
        if key not in self.sets:
            return set()
        return self.sets[key]
    
    def hincrby(self, key, field, increment=1):
        """模拟HINCRBY命令"""
        if key not in self.hashes:
            self.hashes[key] = {}
        if field not in self.hashes[key]:
            self.hashes[key][field] = 0
        self.hashes[key][field] += increment
        return self.hashes[key][field]
    
    def hincrbyfloat(self, key, field, increment=1.0):
        """模拟HINCRBYFLOAT命令"""
        if key not in self.hashes:
            self.hashes[key] = {}
        if field not in self.hashes[key]:
            self.hashes[key][field] = 0.0
        self.hashes[key][field] += increment
        return self.hashes[key][field]
    
    def hgetall(self, key):
        """模拟HGETALL命令"""
        if key not in self.hashes:
            return {}
        # 将值转换为字节字符串，模拟Redis的行为
        return {k.encode(): str(v).encode() for k, v in self.hashes[key].items()}
    
    def pipeline(self):
        """模拟管道"""
        return MockRedisPipeline(self)


class MockRedisPipeline:
    """Redis管道的模拟实现"""
    
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.commands = []
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def set(self, key, value):
        """模拟管道中的SET命令"""
        self.commands.append(("set", key, value))
        return self
    
    def lpush(self, key, value):
        """模拟管道中的LPUSH命令"""
        self.commands.append(("lpush", key, value))
        return self
    
    def rpop(self, key):
        """模拟管道中的RPOP命令"""
        self.commands.append(("rpop", key))
        return self
    
    def sadd(self, key, value):
        """模拟管道中的SADD命令"""
        self.commands.append(("sadd", key, value))
        return self
    
    def srem(self, key, value):
        """模拟管道中的SREM命令"""
        self.commands.append(("srem", key, value))
        return self
    
    def hincrby(self, key, field, increment=1):
        """模拟管道中的HINCRBY命令"""
        self.commands.append(("hincrby", key, field, increment))
        return self
    
    def hincrbyfloat(self, key, field, increment=1.0):
        """模拟管道中的HINCRBYFLOAT命令"""
        self.commands.append(("hincrbyfloat", key, field, increment))
        return self
    
    def delete(self, *keys):
        """模拟管道中的DEL命令"""
        self.commands.append(("delete", keys))
        return self
    
    def execute(self):
        """执行管道中的所有命令"""
        results = []
        for cmd in self.commands:
            if cmd[0] == "set":
                results.append(self.redis_client.set(cmd[1], cmd[2]))
            elif cmd[0] == "lpush":
                results.append(self.redis_client.lpush(cmd[1], cmd[2]))
            elif cmd[0] == "rpop":
                results.append(self.redis_client.rpop(cmd[1]))
            elif cmd[0] == "sadd":
                results.append(self.redis_client.sadd(cmd[1], cmd[2]))
            elif cmd[0] == "srem":
                results.append(self.redis_client.srem(cmd[1], cmd[2]))
            elif cmd[0] == "hincrby":
                results.append(self.redis_client.hincrby(cmd[1], cmd[2], cmd[3]))
            elif cmd[0] == "hincrbyfloat":
                results.append(self.redis_client.hincrbyfloat(cmd[1], cmd[2], cmd[3]))
            elif cmd[0] == "delete":
                results.append(self.redis_client.delete(*cmd[1]))
        self.commands = []
        return results


class TestCrawlerQueue(unittest.TestCase):
    """爬虫队列测试类"""
    
    def setUp(self):
        """测试前的准备工作"""
        # 使用真实的Redis连接
        self.queue_manager = get_queue_manager("redis://localhost:6379")
        
        # 定义测试队列名称前缀
        self.queue_prefix = "test_crawler_queue_"
        
    def tearDown(self):
        """测试后的清理工作"""
        # 清空所有测试队列
        for i in range(10):
            self.queue_manager.clear_queue(f"{self.queue_prefix}{i}")
    
    def test_enqueue_task(self):
        """测试任务入队"""
        queue_name = f"{self.queue_prefix}1"
        self.queue_manager.clear_queue(queue_name)
        
        task_data = {
            "url": "https://www.cuhk.edu.cn/zh-hans",
            "depth": 0,
            "crawler_id": "test_crawler"
        }
        
        # 将任务加入队列
        task_id = self.queue_manager.enqueue(queue_name, task_data)
        
        # 验证任务ID不为空
        self.assertIsNotNone(task_id)
        
        # 验证队列长度
        queue_length = self.queue_manager.get_queue_length(queue_name)
        self.assertEqual(queue_length, 1)
        
        # 验证任务状态
        task_status = self.queue_manager.get_task_status(task_id)
        self.assertIsNotNone(task_status)
        self.assertEqual(task_status["status"], TaskStatus.PENDING.value)
        self.assertEqual(task_status["data"], task_data)
    
    def test_dequeue_task(self):
        """测试任务出队"""
        queue_name = f"{self.queue_prefix}2"
        self.queue_manager.clear_queue(queue_name)
        
        # 先入队一个任务
        task_data = {
            "url": "https://www.cuhk.edu.cn/zh-hans",
            "depth": 0,
            "crawler_id": "test_crawler"
        }
        task_id = self.queue_manager.enqueue(queue_name, task_data)
        
        # 出队任务
        task = self.queue_manager.dequeue(queue_name, block=False)
        
        # 验证任务不为空
        self.assertIsNotNone(task)
        self.assertEqual(task["id"], task_id)
        self.assertEqual(task["data"], task_data)
        self.assertEqual(task["status"], TaskStatus.PROCESSING.value)
        
        # 验证队列为空
        queue_length = self.queue_manager.get_queue_length(queue_name)
        self.assertEqual(queue_length, 0)
    
    def test_complete_task(self):
        """测试完成任务"""
        queue_name = f"{self.queue_prefix}3"
        self.queue_manager.clear_queue(queue_name)
        
        # 先入队并出队一个任务
        task_data = {
            "url": "https://www.cuhk.edu.cn/zh-hans",
            "depth": 0,
            "crawler_id": "test_crawler"
        }
        task_id = self.queue_manager.enqueue(queue_name, task_data)
        task = self.queue_manager.dequeue(queue_name, block=False)
        
        # 完成任务
        result = {
            "content": "网页内容",
            "links": ["https://www.cuhk.edu.cn/zh-hans/page1", "https://www.cuhk.edu.cn/zh-hans/page2"]
        }
        success = self.queue_manager.complete_task(queue_name, task_id, result)
        
        # 验证操作成功
        self.assertTrue(success)
        
        # 验证任务状态
        task_status = self.queue_manager.get_task_status(task_id)
        self.assertEqual(task_status["status"], TaskStatus.COMPLETED.value)
        self.assertEqual(task_status["result"], result)
    
    def test_fail_task(self):
        """测试失败任务"""
        queue_name = f"{self.queue_prefix}4"
        self.queue_manager.clear_queue(queue_name)
        
        # 先入队并出队一个任务
        task_data = {
            "url": "https://www.cuhk.edu.cn/zh-hans",
            "depth": 0,
            "crawler_id": "test_crawler"
        }
        task_id = self.queue_manager.enqueue(queue_name, task_data)
        task = self.queue_manager.dequeue(queue_name, block=False)
        
        # 标记任务失败
        error = "连接超时"
        success = self.queue_manager.fail_task(queue_name, task_id, error)
        
        # 验证操作成功
        self.assertTrue(success)
        
        # 验证任务状态
        task_status = self.queue_manager.get_task_status(task_id)
        self.assertEqual(task_status["status"], TaskStatus.FAILED.value)
        self.assertEqual(task_status["error"], error)
    
    def test_retry_task(self):
        """测试重试任务"""
        queue_name = f"{self.queue_prefix}5"
        self.queue_manager.clear_queue(queue_name)
        
        # 先入队并出队一个任务
        task_data = {
            "url": "https://www.cuhk.edu.cn/zh-hans",
            "depth": 0,
            "crawler_id": "test_crawler"
        }
        task_id = self.queue_manager.enqueue(queue_name, task_data)
        task = self.queue_manager.dequeue(queue_name, block=False)
        
        # 标记任务需要重试
        error = "临时网络错误"
        success = self.queue_manager.fail_task(queue_name, task_id, error, retry=True)
        
        # 验证操作成功
        self.assertTrue(success)
        
        # 验证任务状态
        task_status = self.queue_manager.get_task_status(task_id)
        self.assertEqual(task_status["status"], TaskStatus.RETRY.value)
        self.assertEqual(task_status["error"], error)
        self.assertEqual(task_status["retry_count"], 1)
        
        # 验证任务重新入队
        queue_length = self.queue_manager.get_queue_length(queue_name)
        self.assertEqual(queue_length, 1)
    
    def test_get_queue_metrics(self):
        """测试获取队列指标"""
        queue_name = f"{self.queue_prefix}6"
        self.queue_manager.clear_queue(queue_name)
        
        # 准备测试数据：入队3个任务
        task_ids = []
        for i in range(3):
            task_data = {
                "url": f"https://www.cuhk.edu.cn/zh-hans/page{i}",
                "depth": 0,
                "crawler_id": "test_crawler"
            }
            task_id = self.queue_manager.enqueue(queue_name, task_data)
            task_ids.append(task_id)
        
        # 出队并完成2个任务
        for i in range(2):
            task = self.queue_manager.dequeue(queue_name, block=False)
            if task:  # 确保任务不为None
                self.queue_manager.complete_task(queue_name, task["id"])
        
        # 出队并失败1个任务
        task = self.queue_manager.dequeue(queue_name, block=False)
        if task:  # 确保任务不为None
            self.queue_manager.fail_task(queue_name, task["id"], "404 Not Found")
        
        # 获取队列指标
        metrics = self.queue_manager.get_queue_metrics(queue_name)
        
        # 验证指标
        self.assertEqual(metrics.pending_tasks, 0)  # 所有任务都已出队
        self.assertEqual(metrics.completed_tasks, 2)  # 2个任务完成
        self.assertEqual(metrics.failed_tasks, 1)  # 1个任务失败
    
    def test_multiple_tasks(self):
        """测试多任务处理"""
        queue_name = f"{self.queue_prefix}7"
        self.queue_manager.clear_queue(queue_name)
        
        # 入队10个任务
        task_ids = []
        for i in range(10):
            task_data = {
                "url": f"https://www.cuhk.edu.cn/zh-hans/page{i}",
                "depth": 0,
                "crawler_id": "test_crawler"
            }
            task_id = self.queue_manager.enqueue(queue_name, task_data)
            task_ids.append(task_id)
        
        # 验证队列长度
        queue_length = self.queue_manager.get_queue_length(queue_name)
        self.assertEqual(queue_length, 10)
        
        # 模拟多线程处理任务
        def worker():
            task = self.queue_manager.dequeue(queue_name, block=False)
            if task:
                # 50%的任务成功，50%的任务失败
                if int(task["id"].split("-")[0]) % 2 == 0:
                    self.queue_manager.complete_task(queue_name, task["id"])
                else:
                    self.queue_manager.fail_task(queue_name, task["id"], "随机错误")
        
        # 创建5个工作线程
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker)
            thread.start()
            threads.append(thread)
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 检查剩余任务
        remaining_tasks = self.queue_manager.get_queue_length(queue_name)
        self.assertLessEqual(remaining_tasks, 5)  # 最多应该剩下5个任务
        
        # 继续处理剩余任务
        while True:
            task = self.queue_manager.dequeue(queue_name, block=False)
            if not task:
                break
            self.queue_manager.complete_task(queue_name, task["id"])
        
        # 获取队列指标
        metrics = self.queue_manager.get_queue_metrics(queue_name)
        
        # 验证所有任务都已处理
        self.assertEqual(metrics.pending_tasks, 0)
        self.assertEqual(metrics.processing_tasks, 0)
        completed_failed = metrics.completed_tasks + metrics.failed_tasks
        self.assertEqual(completed_failed, 10)


class TestCrawlerManagerQueue(unittest.TestCase):
    """爬虫管理器队列集成测试"""
    
    def setUp(self):
        """测试前的准备工作"""
        # 使用真实的Redis连接
        self.queue_manager = get_queue_manager("redis://localhost:6379")
        
        # 清空任何可能的队列
        self.queue_manager.clear_queue("test_crawler_integration")
        
        # 创建爬虫管理器
        self.crawler_manager = CrawlerManager(storage_dir="./test_crawl_results")
        
        # 临时目录，测试后会删除
        os.makedirs("./test_crawl_results", exist_ok=True)
    
    def tearDown(self):
        """测试后的清理工作"""
        # 删除临时目录
        import shutil
        if os.path.exists("./test_crawl_results"):
            shutil.rmtree("./test_crawl_results")
    
    @mock.patch('src.backend.sitesearch.crawler.httpx_worker.HttpxWorker')
    def test_crawler_integration(self, mock_httpx_worker):
        """测试爬虫与队列的集成"""
        # 模拟HttpxWorker的方法
        mock_instance = mock_httpx_worker.return_value
        mock_instance.crawl.return_value = {
            "status": "completed",
            "crawled_count": 5,
            "failed_count": 1,
            "duration": 2.5,
            "crawled_urls": ["https://www.cuhk.edu.cn/zh-hans", "https://www.cuhk.edu.cn/zh-hans/page1"],
            "failed_urls": {"https://www.cuhk.edu.cn/zh-hans/404": "404 Not Found"}
        }
        mock_instance.discover_sitemap.return_value = [
            "https://www.cuhk.edu.cn/zh-hans/sitemap1",
            "https://www.cuhk.edu.cn/zh-hans/sitemap2"
        ]
        
        # 创建爬虫
        crawler_id = self.crawler_manager.create_crawler(
            crawler_id="test_crawler",
            crawler_type="httpx",
            base_url="https://www.cuhk.edu.cn/zh-hans",
            config={"max_urls": 10, "max_depth": 2}
        )
        
        # 启动爬虫
        success = self.crawler_manager.start_crawler(crawler_id, discover_sitemap=False)
        self.assertTrue(success)
        
        # 验证爬虫状态
        status = self.crawler_manager.get_crawler_status(crawler_id)
        self.assertEqual(status["status"], "running")
        
        # 等待爬虫"完成"（由于我们模拟了爬虫方法，不需要实际等待）
        # 手动修改爬虫状态
        self.crawler_manager.crawler_statuses[crawler_id]["status"] = "completed"
        
        # 验证爬虫状态
        status = self.crawler_manager.get_crawler_status(crawler_id)
        self.assertEqual(status["status"], "completed")
        
        # 测试停止爬虫
        success = self.crawler_manager.stop_crawler(crawler_id)
        # 由于状态已经是completed，所以停止应该失败
        self.assertFalse(success)
        
        # 删除爬虫
        success = self.crawler_manager.delete_crawler(crawler_id)
        self.assertTrue(success)
        
        # 验证爬虫已被删除
        with self.assertRaises(ValueError):
            self.crawler_manager.get_crawler_status(crawler_id)


if __name__ == "__main__":
    unittest.main() 