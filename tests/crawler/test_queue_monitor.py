"""
队列监控测试模块
测试爬虫队列监控功能
"""

import os
import sys
import time
import unittest
from unittest import mock
from threading import Event

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.backend.sitesearch.utils.queue_manager import get_queue_manager, TaskStatus
from src.backend.sitesearch.utils.queue_monitor import get_queue_monitor, QueueHealthStatus


class TestQueueMonitor(unittest.TestCase):
    """队列监控测试类"""
    
    def setUp(self):
        """测试前的准备工作"""
        # 使用真实的Redis连接
        self.redis_url = "redis://localhost:6382"
        self.queue_manager = get_queue_manager(self.redis_url)
        
        # 定义测试队列名称
        self.test_queues = ["test_monitor_queue_1", "test_monitor_queue_2"]
        
        # 清空测试队列
        for queue in self.test_queues:
            self.queue_manager.clear_queue(queue)
        
        # 创建队列监控器
        self.queue_monitor = get_queue_monitor(
            queue_names=self.test_queues,
            check_interval=1,
            max_pending_threshold=50,
            max_error_rate=0.2,
            activity_timeout=5
        )
        
        # 清空健康状态缓存
        self.queue_monitor.health_status = {}
        
        # 记录收到的告警
        self.alerts = []
        
        # 添加告警回调
        def alert_callback(health_status: QueueHealthStatus):
            self.alerts.append(health_status)
        
        self.queue_monitor.add_alert_callback(alert_callback)
    
    def tearDown(self):
        """测试后的清理工作"""
        # 停止监控
        self.queue_monitor.stop()
        
        # 清空测试队列
        for queue in self.test_queues:
            self.queue_manager.clear_queue(queue)
    
    def test_monitor_queue_health(self):
        """测试监控队列健康状态"""
        queue_name = self.test_queues[0]
        
        # 确保健康状态缓存是空的
        self.queue_monitor.health_status = {}
        
        # 初始状态下应该没有健康状态
        health = self.queue_monitor.get_queue_health(queue_name)
        self.assertIsNone(health)
        
        # 手动触发一次检查
        self.queue_monitor._check_queue_health(queue_name)
        
        # 现在应该有健康状态了
        health = self.queue_monitor.get_queue_health(queue_name)
        self.assertIsNotNone(health)
        self.assertEqual(health.queue_name, queue_name)
        self.assertTrue(health.is_healthy)  # 空队列应该是健康的
    
    def test_detect_backlog_warning(self):
        """测试检测队列积压警告"""
        queue_name = self.test_queues[0]
        
        # 添加超过阈值的任务
        for i in range(60):  # 超过 max_pending_threshold=50
            self.queue_manager.enqueue(queue_name, {"test": i})
        
        # 手动触发检查
        self.queue_monitor._check_queue_health(queue_name)
        
        # 获取健康状态
        health = self.queue_monitor.get_queue_health(queue_name)
        
        # 验证告警
        self.assertIsNotNone(health)
        self.assertFalse(health.is_healthy)
        self.assertTrue(health.backlog_size_warning)
        self.assertIn("队列积压任务过多", health.message)
        
        # 验证告警回调被触发
        self.assertEqual(len(self.alerts), 1)
        self.assertEqual(self.alerts[0].queue_name, queue_name)
        self.assertTrue(self.alerts[0].backlog_size_warning)
    
    def test_detect_error_rate_warning(self):
        """测试检测错误率警告"""
        queue_name = self.test_queues[0]
        
        # 准备任务
        task_ids = []
        for i in range(10):
            task_id = self.queue_manager.enqueue(queue_name, {"test": i})
            task_ids.append(task_id)
        
        # 处理任务: 8个失败，2个成功 (80%错误率 > 20%阈值)
        for i in range(10):
            task = self.queue_manager.dequeue(queue_name, block=False)
            if task:  # 确保任务不为None
                if i < 8:
                    self.queue_manager.fail_task(queue_name, task["id"], f"错误 {i}")
                else:
                    self.queue_manager.complete_task(queue_name, task["id"])
        
        # 手动触发检查
        self.queue_monitor._check_queue_health(queue_name)
        
        # 获取健康状态
        health = self.queue_monitor.get_queue_health(queue_name)
        
        # 验证告警
        self.assertIsNotNone(health)
        self.assertFalse(health.is_healthy)
        self.assertTrue(health.error_rate_warning)
        self.assertIn("队列错误率过高", health.message)
    
    @mock.patch('time.time')
    def test_detect_stalled_queue(self, mock_time):
        """测试检测停滞的队列"""
        queue_name = self.test_queues[0]
        
        # 设置初始时间
        current_time = 1000.0
        mock_time.return_value = current_time
        
        # 添加一个任务并开始处理
        task_id = self.queue_manager.enqueue(queue_name, {"test": "stall"})
        task = self.queue_manager.dequeue(queue_name, block=False)
        
        # 确保有任务被处理中
        self.assertIsNotNone(task)
        
        # 第一次检查
        self.queue_monitor._check_queue_health(queue_name)
        health1 = self.queue_monitor.get_queue_health(queue_name)
        
        # 设置经过了超时时间
        mock_time.return_value = current_time + self.queue_monitor.activity_timeout + 1
        
        # 再次检查
        self.queue_monitor._check_queue_health(queue_name)
        health2 = self.queue_monitor.get_queue_health(queue_name)
        
        # 验证告警
        self.assertIsNotNone(health1)
        self.assertIsNotNone(health2)
        self.assertTrue(health1.is_healthy)  # 第一次检查应该是健康的
        self.assertFalse(health2.is_healthy)  # 第二次检查应该不健康
        self.assertTrue(health2.stalled)     # 应该检测到停滞
        self.assertIn("队列处理活动长时间无变化", health2.message)
    
    def test_monitor_loop(self):
        """测试监控循环"""
        # 启动监控
        self.queue_monitor.start()
        
        # 添加超过阈值的任务以触发告警
        queue_name = self.test_queues[0]
        for i in range(60):  # 超过 max_pending_threshold=50
            self.queue_manager.enqueue(queue_name, {"test": i})
        
        # 等待监控检查 (略大于check_interval)
        time.sleep(1.5)
        
        # 停止监控
        self.queue_monitor.stop()
        
        # 验证告警被触发
        self.assertGreater(len(self.alerts), 0)
        self.assertEqual(self.alerts[0].queue_name, queue_name)
        self.assertTrue(self.alerts[0].backlog_size_warning)
    
    def test_get_summary_report(self):
        """测试获取摘要报告"""
        # 准备队列数据
        for i, queue_name in enumerate(self.test_queues):
            # 添加一些任务
            for j in range(5):
                task_id = self.queue_manager.enqueue(queue_name, {"test": j})
            
            # 处理一些任务
            for j in range(3):
                task = self.queue_manager.dequeue(queue_name, block=False)
                if task:  # 确保任务不为None
                    if i == 0 and j < 2:
                        self.queue_manager.complete_task(queue_name, task["id"])
                    else:
                        self.queue_manager.fail_task(queue_name, task["id"], f"错误 {j}")
        
        # 手动检查所有队列
        for queue_name in self.test_queues:
            self.queue_monitor._check_queue_health(queue_name)
        
        # 获取摘要报告
        report = self.queue_monitor.get_summary_report()
        
        # 验证报告
        self.assertEqual(report["total_queues"], 2)
        self.assertGreaterEqual(report["unhealthy_queues"], 1)  # 至少有一个不健康的队列
        self.assertEqual(report["total_pending_tasks"], 4)  # 每个队列剩余2个任务
        self.assertEqual(report["total_failed_tasks"], 4)  # 队列1: 1个失败, 队列2: 3个失败


if __name__ == "__main__":
    unittest.main() 