import unittest
import time
import os
import sys

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.backend.sitesearch.utils.queue_manager import get_queue_manager, QueueManager, TaskStatus

class TestQueueManager(unittest.TestCase):
    """队列管理器测试类"""
    
    def setUp(self):
        """测试前准备"""
        # 从环境变量获取Redis URL
        redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
        # 创建队列管理器实例
        self.queue_manager = QueueManager(redis_url)
        # 测试队列名称
        self.test_queue = "test_queue"
        # 清空队列
        self.queue_manager.clear_queue(self.test_queue)
    
    def tearDown(self):
        """测试后清理"""
        # 清空队列
        self.queue_manager.clear_queue(self.test_queue)
    
    def test_enqueue_dequeue(self):
        """测试入队和出队功能"""
        # 创建测试任务
        task_data = {"test_key": "test_value"}
        
        # 入队
        task_id = self.queue_manager.enqueue(self.test_queue, task_data)
        
        # 验证队列长度
        self.assertEqual(self.queue_manager.get_queue_length(self.test_queue), 1)
        
        # 出队
        task = self.queue_manager.dequeue(self.test_queue, block=False)
        
        # 验证任务内容
        self.assertIsNotNone(task)
        self.assertEqual(task["id"], task_id)
        self.assertEqual(task["data"], task_data)
        self.assertEqual(task["status"], TaskStatus.PROCESSING.value)
    
    def test_task_status_flow(self):
        """测试任务状态流转"""
        # 创建测试任务
        task_data = {"test_key": "test_value"}
        
        # 入队
        task_id = self.queue_manager.enqueue(self.test_queue, task_data)
        
        # 获取任务状态
        task_status = self.queue_manager.get_task_status(task_id)
        self.assertEqual(task_status["status"], TaskStatus.PENDING.value)
        
        # 出队
        task = self.queue_manager.dequeue(self.test_queue, block=False)
        
        # 验证任务状态为处理中
        task_status = self.queue_manager.get_task_status(task_id)
        self.assertEqual(task_status["status"], TaskStatus.PROCESSING.value)
        
        # 完成任务
        result = {"result_key": "result_value"}
        self.queue_manager.complete_task(self.test_queue, task_id, result)
        
        # 验证任务状态为已完成
        task_status = self.queue_manager.get_task_status(task_id)
        self.assertEqual(task_status["status"], TaskStatus.COMPLETED.value)
        self.assertEqual(task_status["result"], result)
    
    def test_fail_and_retry(self):
        """测试任务失败和重试"""
        # 创建测试任务
        task_data = {"test_key": "test_value"}
        
        # 入队
        task_id = self.queue_manager.enqueue(self.test_queue, task_data)
        
        # 出队
        task = self.queue_manager.dequeue(self.test_queue, block=False)
        
        # 标记为失败需重试
        error = "测试错误"
        self.queue_manager.fail_task(self.test_queue, task_id, error, retry=True)
        
        # 验证任务状态
        task_status = self.queue_manager.get_task_status(task_id)
        self.assertEqual(task_status["status"], TaskStatus.RETRY.value)
        self.assertEqual(task_status["error"], error)
        self.assertEqual(task_status["retry_count"], 1)
        
        # 验证队列长度为1
        self.assertEqual(self.queue_manager.get_queue_length(self.test_queue), 1)
        
        # 再次取出任务
        task = self.queue_manager.dequeue(self.test_queue, block=False)
        self.assertEqual(task["id"], task_id)
        self.assertEqual(task["retry_count"], 1)
        
        # 标记为最终失败
        self.queue_manager.fail_task(self.test_queue, task_id, error, retry=False)
        
        # 验证任务状态
        task_status = self.queue_manager.get_task_status(task_id)
        self.assertEqual(task_status["status"], TaskStatus.FAILED.value)
        
        # 验证队列为空
        self.assertEqual(self.queue_manager.get_queue_length(self.test_queue), 0)
    
    def test_queue_metrics(self):
        """测试队列指标统计"""
        # 创建多个测试任务
        task_ids = []
        for i in range(5):
            task_data = {"index": i}
            task_id = self.queue_manager.enqueue(self.test_queue, task_data)
            task_ids.append(task_id)
        
        # 处理3个任务
        for i in range(3):
            task = self.queue_manager.dequeue(self.test_queue, block=False)
            task_id = task["id"]
            if i < 2:
                # 完成2个任务
                self.queue_manager.complete_task(self.test_queue, task_id)
            else:
                # 失败1个任务
                self.queue_manager.fail_task(self.test_queue, task_id, "测试错误")
        
        # 获取队列指标
        metrics = self.queue_manager.get_queue_metrics(self.test_queue)
        
        # 验证指标
        self.assertEqual(metrics.queue_name, self.test_queue)
        self.assertEqual(metrics.pending_tasks, 2)  # 剩余2个任务
        self.assertEqual(metrics.processing_tasks, 0)  # 没有处理中的任务
        self.assertEqual(metrics.completed_tasks, 2)  # 2个已完成
        self.assertEqual(metrics.failed_tasks, 1)    # 1个失败
        
    def test_process_queue(self):
        """测试队列批量处理"""
        # 创建多个测试任务
        for i in range(5):
            task_data = {"index": i}
            self.queue_manager.enqueue(self.test_queue, task_data)
        
        # 定义处理函数
        def processor(task):
            # 简单处理，返回索引值加1
            return {"result": task["data"]["index"] + 1}
        
        # 批量处理3个任务
        processed = self.queue_manager.process_queue(self.test_queue, processor, max_tasks=3)
        
        # 验证处理数量
        self.assertEqual(processed, 3)
        
        # 验证队列长度
        self.assertEqual(self.queue_manager.get_queue_length(self.test_queue), 2)
        
        # 验证完成的任务数
        metrics = self.queue_manager.get_queue_metrics(self.test_queue)
        self.assertEqual(metrics.completed_tasks, 3)
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        # 获取两个队列管理器实例
        manager1 = get_queue_manager()
        manager2 = get_queue_manager()
        
        # 验证是同一个实例
        self.assertIs(manager1, manager2)

if __name__ == "__main__":
    unittest.main() 