import redis
import json
import time
import logging
import os
from typing import Dict, Any, List, Optional, Union, Callable
from enum import Enum
from dataclasses import dataclass

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('queue_manager')

# 任务状态枚举
class TaskStatus(str, Enum):
    PENDING = "pending"      # 等待处理
    PROCESSING = "processing"  # 正在处理中
    COMPLETED = "completed"  # 处理完成
    FAILED = "failed"        # 处理失败
    RETRY = "retry"          # 需要重试

@dataclass
class QueueMetrics:
    """队列指标数据类"""
    queue_name: str
    pending_tasks: int = 0
    processing_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    avg_processing_time: float = 0.0

class QueueManager:
    """统一队列管理器，支持Redis后端"""
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        初始化队列管理器
        
        Args:
            redis_url: Redis连接URL，如果未提供则从环境变量获取
        """
        if not redis_url:
            redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
        
        # 解析Redis URL获取连接信息
        try:
            self.redis_client = redis.from_url(redis_url)
            logger.info(f"成功连接到Redis: {redis_url}")
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            raise
        
        # 队列键前缀
        self.queue_prefix = "sitesearch:queue:"
        # 工作中的任务集合前缀
        self.processing_prefix = "sitesearch:processing:"
        # 完成的任务集合前缀
        self.completed_prefix = "sitesearch:completed:"
        # 失败的任务集合前缀
        self.failed_prefix = "sitesearch:failed:"
        # 任务元数据前缀
        self.task_meta_prefix = "sitesearch:task:meta:"
        # 队列统计前缀
        self.stats_prefix = "sitesearch:stats:"
    
    def _get_queue_key(self, queue_name: str) -> str:
        """获取完整的队列键名"""
        return f"{self.queue_prefix}{queue_name}"
    
    def _get_processing_key(self, queue_name: str) -> str:
        """获取正在处理的任务集合键名"""
        return f"{self.processing_prefix}{queue_name}"
    
    def _get_completed_key(self, queue_name: str) -> str:
        """获取已完成任务集合键名"""
        return f"{self.completed_prefix}{queue_name}"
    
    def _get_failed_key(self, queue_name: str) -> str:
        """获取失败任务集合键名"""
        return f"{self.failed_prefix}{queue_name}"
    
    def _get_task_meta_key(self, task_id: str) -> str:
        """获取任务元数据键名"""
        return f"{self.task_meta_prefix}{task_id}"
    
    def _get_stats_key(self, queue_name: str) -> str:
        """获取队列统计键名"""
        return f"{self.stats_prefix}{queue_name}"
    
    def enqueue(self, queue_name: str, task_data: Dict[str, Any], task_id: Optional[str] = None) -> str:
        """
        将任务加入队列
        
        Args:
            queue_name: 队列名称
            task_data: 任务数据字典
            task_id: 可选的任务ID，如果不提供则自动生成
            
        Returns:
            str: 任务ID
        """
        if task_id is None:
            # 生成唯一任务ID: 时间戳+随机数
            task_id = f"{int(time.time() * 1000)}-{os.urandom(4).hex()}"
        
        # 创建任务元数据
        task_meta = {
            "id": task_id,
            "queue": queue_name,
            "status": TaskStatus.PENDING.value,
            "data": task_data,
            "created_at": time.time(),
            "updated_at": time.time(),
            "started_at": None,
            "completed_at": None,
            "error": None,
            "retry_count": 0
        }
        
        # 序列化任务元数据
        task_meta_json = json.dumps(task_meta)
        
        # 任务数据串行化
        task_json = json.dumps({"id": task_id})
        
        # 使用管道执行多个Redis操作，确保原子性
        with self.redis_client.pipeline() as pipe:
            # 存储任务元数据
            pipe.set(self._get_task_meta_key(task_id), task_meta_json)
            # 将任务ID加入队列
            pipe.lpush(self._get_queue_key(queue_name), task_json)
            # 更新统计信息
            pipe.hincrby(self._get_stats_key(queue_name), "total_enqueued", 1)
            pipe.hincrby(self._get_stats_key(queue_name), "pending", 1)
            # 执行所有命令
            pipe.execute()
        
        logger.info(f"任务 {task_id} 已加入队列 {queue_name}")
        return task_id
    
    def dequeue(self, queue_name: str, block: bool = True, timeout: int = 0) -> Optional[Dict[str, Any]]:
        """
        从队列中获取任务
        
        Args:
            queue_name: 队列名称
            block: 是否阻塞等待任务
            timeout: 阻塞超时时间(秒)，0表示无限等待
            
        Returns:
            Optional[Dict[str, Any]]: 任务数据，如果队列为空则返回None
        """
        queue_key = self._get_queue_key(queue_name)
        processing_key = self._get_processing_key(queue_name)
        
        # 获取任务
        if block:
            # 阻塞式获取任务
            result = self.redis_client.brpop(queue_key, timeout)
            if result is None:
                return None
            _, task_json = result
        else:
            # 非阻塞式获取任务
            task_json = self.redis_client.rpop(queue_key)
            if task_json is None:
                return None
        
        # 解析任务ID
        task_info = json.loads(task_json)
        task_id = task_info["id"]
        
        # 获取任务元数据
        task_meta_json = self.redis_client.get(self._get_task_meta_key(task_id))
        if task_meta_json is None:
            logger.error(f"无法找到任务 {task_id} 的元数据")
            return None
        
        task_meta = json.loads(task_meta_json)
        
        # 标记任务为处理中
        task_meta["status"] = TaskStatus.PROCESSING.value
        task_meta["started_at"] = time.time()
        task_meta["updated_at"] = time.time()
        
        # 使用管道更新任务状态
        with self.redis_client.pipeline() as pipe:
            pipe.set(self._get_task_meta_key(task_id), json.dumps(task_meta))
            pipe.sadd(processing_key, task_id)
            pipe.hincrby(self._get_stats_key(queue_name), "pending", -1)
            pipe.hincrby(self._get_stats_key(queue_name), "processing", 1)
            pipe.execute()
        
        logger.info(f"任务 {task_id} 已从队列 {queue_name} 中取出")
        return task_meta
    
    def complete_task(self, queue_name: str, task_id: str, result: Optional[Dict[str, Any]] = None) -> bool:
        """
        标记任务为已完成
        
        Args:
            queue_name: 队列名称
            task_id: 任务ID
            result: 可选的任务执行结果
            
        Returns:
            bool: 操作是否成功
        """
        processing_key = self._get_processing_key(queue_name)
        completed_key = self._get_completed_key(queue_name)
        task_meta_key = self._get_task_meta_key(task_id)
        
        # 获取任务元数据
        task_meta_json = self.redis_client.get(task_meta_key)
        if task_meta_json is None:
            logger.error(f"无法找到任务 {task_id} 的元数据")
            return False
        
        task_meta = json.loads(task_meta_json)
        
        # 检查任务是否处于处理中状态
        if task_meta["status"] != TaskStatus.PROCESSING.value:
            logger.warning(f"尝试完成非处理中状态的任务 {task_id}，当前状态: {task_meta['status']}")
        
        # 更新任务状态
        task_meta["status"] = TaskStatus.COMPLETED.value
        task_meta["completed_at"] = time.time()
        task_meta["updated_at"] = time.time()
        task_meta["result"] = result
        
        # 计算处理时间
        processing_time = task_meta["completed_at"] - task_meta["started_at"] if task_meta["started_at"] else 0
        
        # 使用管道更新任务状态和统计信息
        with self.redis_client.pipeline() as pipe:
            pipe.set(task_meta_key, json.dumps(task_meta))
            pipe.srem(processing_key, task_id)
            pipe.sadd(completed_key, task_id)
            pipe.hincrby(self._get_stats_key(queue_name), "processing", -1)
            pipe.hincrby(self._get_stats_key(queue_name), "completed", 1)
            pipe.hincrbyfloat(self._get_stats_key(queue_name), "total_processing_time", processing_time)
            pipe.execute()
        
        logger.info(f"任务 {task_id} 已完成，处理时间: {processing_time:.2f}秒")
        return True
    
    def fail_task(self, queue_name: str, task_id: str, error: str, retry: bool = False) -> bool:
        """
        标记任务为失败
        
        Args:
            queue_name: 队列名称
            task_id: 任务ID
            error: 错误信息
            retry: 是否需要重试
            
        Returns:
            bool: 操作是否成功
        """
        processing_key = self._get_processing_key(queue_name)
        failed_key = self._get_failed_key(queue_name)
        task_meta_key = self._get_task_meta_key(task_id)
        
        # 获取任务元数据
        task_meta_json = self.redis_client.get(task_meta_key)
        if task_meta_json is None:
            logger.error(f"无法找到任务 {task_id} 的元数据")
            return False
        
        task_meta = json.loads(task_meta_json)
        
        # 更新任务状态
        if retry:
            task_meta["status"] = TaskStatus.RETRY.value
            task_meta["retry_count"] = task_meta.get("retry_count", 0) + 1
        else:
            task_meta["status"] = TaskStatus.FAILED.value
        
        task_meta["error"] = error
        task_meta["updated_at"] = time.time()
        
        # 使用管道更新任务状态
        with self.redis_client.pipeline() as pipe:
            pipe.set(task_meta_key, json.dumps(task_meta))
            pipe.srem(processing_key, task_id)
            
            if retry:
                # 将任务重新放入队列
                pipe.lpush(self._get_queue_key(queue_name), json.dumps({"id": task_id}))
                pipe.hincrby(self._get_stats_key(queue_name), "retries", 1)
                pipe.hincrby(self._get_stats_key(queue_name), "pending", 1)
            else:
                # 将任务加入失败集合
                pipe.sadd(failed_key, task_id)
                pipe.hincrby(self._get_stats_key(queue_name), "failed", 1)
            
            pipe.hincrby(self._get_stats_key(queue_name), "processing", -1)
            pipe.execute()
        
        status = "重试" if retry else "失败"
        logger.info(f"任务 {task_id} 已{status}，错误: {error}")
        return True
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[Dict[str, Any]]: 任务元数据，如果任务不存在则返回None
        """
        task_meta_json = self.redis_client.get(self._get_task_meta_key(task_id))
        if task_meta_json is None:
            return None
        
        return json.loads(task_meta_json)
    
    def get_queue_metrics(self, queue_name: str) -> QueueMetrics:
        """
        获取队列指标
        
        Args:
            queue_name: 队列名称
            
        Returns:
            QueueMetrics: 队列指标数据
        """
        stats_key = self._get_stats_key(queue_name)
        
        # 从Redis获取统计数据
        stats = self.redis_client.hgetall(stats_key)
        
        # 如果没有统计数据，返回默认值
        if not stats:
            return QueueMetrics(queue_name=queue_name)
        
        # 将字节字符串转换为Python类型
        stats = {k.decode(): int(float(v.decode())) for k, v in stats.items()}
        
        # 计算平均处理时间
        total_processing_time = float(stats.get("total_processing_time", 0))
        completed_tasks = stats.get("completed", 0)
        avg_processing_time = total_processing_time / completed_tasks if completed_tasks > 0 else 0
        
        return QueueMetrics(
            queue_name=queue_name,
            pending_tasks=stats.get("pending", 0),
            processing_tasks=stats.get("processing", 0),
            completed_tasks=stats.get("completed", 0),
            failed_tasks=stats.get("failed", 0),
            avg_processing_time=avg_processing_time
        )
    
    def clear_queue(self, queue_name: str) -> bool:
        """
        清空队列
        
        Args:
            queue_name: 队列名称
            
        Returns:
            bool: 操作是否成功
        """
        queue_key = self._get_queue_key(queue_name)
        processing_key = self._get_processing_key(queue_name)
        completed_key = self._get_completed_key(queue_name)
        failed_key = self._get_failed_key(queue_name)
        stats_key = self._get_stats_key(queue_name)
        
        # 获取所有任务ID
        pending_tasks = self.redis_client.lrange(queue_key, 0, -1)
        processing_tasks = self.redis_client.smembers(processing_key)
        completed_tasks = self.redis_client.smembers(completed_key)
        failed_tasks = self.redis_client.smembers(failed_key)
        
        all_tasks = []
        for tasks in [pending_tasks, processing_tasks, completed_tasks, failed_tasks]:
            for task_json in tasks:
                try:
                    task_info = json.loads(task_json)
                    if isinstance(task_info, dict) and "id" in task_info:
                        all_tasks.append(task_info["id"])
                except:
                    pass
        
        # 使用管道一次性删除所有相关数据
        with self.redis_client.pipeline() as pipe:
            # 删除队列和集合
            pipe.delete(queue_key, processing_key, completed_key, failed_key, stats_key)
            
            # 删除所有任务元数据
            for task_id in all_tasks:
                pipe.delete(self._get_task_meta_key(task_id))
                
            # 执行操作
            pipe.execute()
        
        logger.info(f"队列 {queue_name} 已清空")
        return True
    
    def get_queue_length(self, queue_name: str) -> int:
        """
        获取队列长度
        
        Args:
            queue_name: 队列名称
            
        Returns:
            int: 队列中等待处理的任务数量
        """
        return self.redis_client.llen(self._get_queue_key(queue_name))
    
    def process_queue(self, queue_name: str, processor: Callable[[Dict[str, Any]], Union[Dict[str, Any], None]], max_tasks: int = None) -> int:
        """
        处理队列中的任务
        
        Args:
            queue_name: 队列名称
            processor: 处理任务的回调函数
            max_tasks: 最大处理任务数，None表示处理所有任务
            
        Returns:
            int: 成功处理的任务数量
        """
        processed_count = 0
        
        while max_tasks is None or processed_count < max_tasks:
            # 非阻塞式获取任务
            task = self.dequeue(queue_name, block=False)
            if task is None:
                break
            
            task_id = task["id"]
            try:
                # 执行任务处理
                result = processor(task)
                # 标记任务完成
                self.complete_task(queue_name, task_id, result)
                processed_count += 1
            except Exception as e:
                # 标记任务失败
                error_message = str(e)
                self.fail_task(queue_name, task_id, error_message)
                logger.error(f"处理任务 {task_id} 时出错: {error_message}")
        
        return processed_count

# 单例模式，确保整个应用中只有一个队列管理器实例
_queue_manager_instance = None

def get_queue_manager(redis_url: Optional[str] = None) -> QueueManager:
    """
    获取队列管理器单例
    
    Args:
        redis_url: Redis连接URL，仅在首次调用时有效
        
    Returns:
        QueueManager: 队列管理器实例
    """
    global _queue_manager_instance
    if _queue_manager_instance is None:
        _queue_manager_instance = QueueManager(redis_url)
    return _queue_manager_instance 