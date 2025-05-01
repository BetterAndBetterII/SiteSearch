import logging
import time
import json
import threading
import asyncio
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
import redis

class SkipError(Exception):
    """跳过错误类"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class StatusCodeError(Exception):
    """状态码错误类"""
    """
    状态码错误类，用于处理HTTP请求返回的状态码错误
    
    Args:
        message: 错误信息
        status_code: 状态码
    """
    status_code: int

    def __init__(self, message: str, status_code: int):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class ComponentStatus:
    """组件状态类"""
    STOPPED = "stopped"
    RUNNING = "running"
    ERROR = "error"
    PAUSED = "paused"

class BaseHandler(ABC):
    """基础Handler类，处理从Redis队列获取任务并处理的基本逻辑"""
    
    def __init__(self, 
                 redis_url: str,
                 component_type: str,
                 input_queue: str,
                 output_queue: Optional[str] = None,
                 handler_id: str = None,
                 batch_size: int = 1,
                 sleep_time: float = 0.1,
                 start_delay: float = 0.0,
                 max_retries: int = 3,
                 auto_exit: bool = False):
        """
        初始化Handler
        
        Args:
            redis_url: Redis连接URL
            input_queue: 输入队列名称
            output_queue: 输出队列名称（可选）
            handler_id: Handler标识符，如果不提供则自动生成
            batch_size: 批处理大小
            sleep_time: 队列为空时的睡眠时间（秒）
            max_retries: 最大重试次数
        """
        self.redis_url = redis_url
        self.redis_client = redis.from_url(redis_url)
        self.input_queue = f"sitesearch:queue:{input_queue}"
        self.processing_queue = f"sitesearch:processing:{component_type}"
        self.completed_queue = f"sitesearch:completed:{component_type}"
        self.failed_queue = f"sitesearch:failed:{component_type}"
        self.processing_times = f"sitesearch:processing_times:{component_type}"
        
        self.output_queue = f"sitesearch:queue:{output_queue}" if output_queue else None
        self.handler_id = handler_id or f"{self.__class__.__name__}-{os.getpid()}"
        
        self.batch_size = batch_size
        self.sleep_time = sleep_time
        self.start_delay = start_delay
        self.max_retries = max_retries
        
        self.status = ComponentStatus.STOPPED
        self.running = False
        self.thread = None
        self.loop = None
        self.auto_exit = auto_exit
        
        # 统计信息
        self.stats = {
            "tasks_processed": 0,
            "tasks_succeeded": 0,
            "tasks_failed": 0,
            "start_time": None,
            "last_activity": None
        }
        
        # 设置日志
        self.logger = logging.getLogger(f"{self.__class__.__name__}:{self.handler_id}")
        self.logger.setLevel(logging.INFO)
        # 设置日志文件
        os.makedirs(f"logs", exist_ok=True)
        self.logger.addHandler(logging.FileHandler(f"logs/{self.__class__.__name__}.log", mode='a'))
        
        # 任务处理回调，用于测试
        self.task_callback: Optional[Callable[[str, Dict[str, Any], bool], None]] = None

    @abstractmethod
    async def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理任务的抽象方法，子类必须实现
        
        Args:
            task_data: 任务数据
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        pass
    
    async def _handle_task(self, task_id: str, task_data: Dict[str, Any], raw_task_id=None) -> None:
        """
        处理单个任务
        
        Args:
            task_id: 任务ID
            task_data: 任务数据
            raw_task_id: 原始任务ID（用于从队列中移除）
        """
        start_time = time.time()
        success = False
        skiped = False
        result = None
        error = None
        
        try:
            # 处理任务
            result = await self.process_task(task_data)
            success = True
            self.stats["tasks_succeeded"] += 1
            
            # 将结果发送到输出队列
            if self.output_queue and result:
                # 确保任务ID在下游任务中保持一致
                result["task_id"] = task_id
                self.redis_client.lpush(self.output_queue, json.dumps(result))
        except TypeError as e:
            self.logger.exception(f"{task_data['url']}，mime: {task_data['mimetype']} 处理失败: {str(e)}")
            raise e
        except SkipError as e:
            self.logger.info(f"跳过任务: {task_id}, {e}")
            skiped = True
        except Exception as e:
            error = str(e)
            self.stats["tasks_failed"] += 1
            self.logger.exception(f"worker：{self.handler_id} 处理任务 {task_id} 时发生错误: {error}")
        
        finally:
            # 计算处理时间
            processing_time = time.time() - start_time
            
            # 更新任务状态，移除处理中队列中的任务
            if raw_task_id:
                # 使用原始的任务ID从处理队列中移除
                self.redis_client.lrem(self.processing_queue, 0, raw_task_id)
            else:
                # 向后兼容：尝试使用字符串任务ID移除
                self.redis_client.lrem(self.processing_queue, 0, task_id)

            if success:
                self.redis_client.lpush(self.completed_queue, task_id)
                self.redis_client.lpush(self.processing_times, str(processing_time))
                # 限制处理时间列表长度
                self.redis_client.ltrim(self.processing_times, 0, 99)
            elif skiped:
                pass
            else:
                # 存储失败信息
                failed_data = {
                    "task_id": task_id,
                    "error": error,
                    "task_data": task_data,
                    "timestamp": time.time()
                }
                self.redis_client.lpush(self.failed_queue, json.dumps(failed_data))

                print(f"{self.failed_queue} 入队")
            
            # 更新统计信息
            self.stats["tasks_processed"] += 1
            self.stats["last_activity"] = time.time()
            
            # 如果有回调，则调用回调
            if self.task_callback:
                self.task_callback(task_id, task_data, success)
    
    async def _process_batch(self) -> int:
        """
        处理一批任务
        
        Returns:
            int: 处理的任务数量
        """
        # 从输入队列中获取一批任务
        pipeline = self.redis_client.pipeline()
        pipeline.lrange(self.input_queue, 0, self.batch_size - 1)
        pipeline.ltrim(self.input_queue, self.batch_size, -1)
        result = pipeline.execute()
        
        task_ids = result[0]
        if not task_ids:
            return 0
        
        # 将任务移动到处理中队列
        pipeline = self.redis_client.pipeline()
        for raw_task_id in task_ids:
            pipeline.lpush(self.processing_queue, raw_task_id)
        pipeline.execute()

        # 并行处理任务
        tasks = []
        for raw_task_id in task_ids:
            try:
                task_data = json.loads(raw_task_id)
                # 获取或生成任务ID
                if isinstance(task_data, dict) and "task_id" in task_data:
                    t_id = task_data["task_id"]
                    # 传递原始的task_id给_handle_task，用于从队列中移除
                    tasks.append(self._handle_task(t_id, task_data, raw_task_id))
                else:
                    # 如果任务不是字典，或没有task_id，使用任务数据本身作为ID
                    tasks.append(self._handle_task(raw_task_id.decode('utf-8'), task_data, raw_task_id))
            except json.JSONDecodeError:
                self.logger.error(f"无法解析任务数据: {raw_task_id}")
                continue
        
        await asyncio.gather(*tasks)
        return len(tasks)
    
    async def _run_async(self) -> None:
        """异步运行处理循环"""
        self.stats["start_time"] = time.time()
        self.status = ComponentStatus.RUNNING
        self.logger.info(f"Handler {self.handler_id} 已启动，从队列 {self.input_queue} 处理任务")
        
        while self.running:
            try:
                # 处理一批任务
                processed = await self._process_batch()
                
                # 如果没有处理任何任务，则休眠一段时间
                if processed == 0:
                    if self.auto_exit:
                        self.logger.warning(f"Handler {self.handler_id} 没有处理任何任务，自动退出")
                        self.stop()
                    else:
                        await asyncio.sleep(self.sleep_time)
                
            except Exception as e:
                self.logger.exception(f"处理任务批次时发生错误: {str(e)}")
                self.status = ComponentStatus.ERROR
                await asyncio.sleep(self.sleep_time * 10)  # 错误后等待更长时间
    
    def _run_loop(self) -> None:
        """在新线程中运行事件循环"""
        time.sleep(self.start_delay)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._run_async())
        finally:
            self.loop.close()
    
    def start(self) -> None:
        """启动Handler"""
        if self.running:
            self.logger.warning(f"Handler {self.handler_id} 已经在运行")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
    
    def stop(self) -> None:
        """停止Handler"""
        if not self.running:
            return
        
        self.logger.info(f"正在停止Handler {self.handler_id}")
        self.running = False
        
        # if self.thread:
        #     self.thread.join(timeout=30)
        #     if self.thread.is_alive():
        #         self.logger.warning(f"Handler {self.handler_id} 线程未能正常终止")
        
        self.status = ComponentStatus.STOPPED
        self.logger.info(f"Handler {self.handler_id} 已停止")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取Handler的统计信息"""
        # 计算队列长度
        pending = self.redis_client.llen(self.input_queue)
        processing = self.redis_client.llen(self.processing_queue)
        completed = self.redis_client.llen(self.completed_queue)
        failed = self.redis_client.llen(self.failed_queue)
        
        # 计算平均处理时间
        avg_time = 0.0
        processing_times = self.redis_client.lrange(self.processing_times, 0, -1)
        if processing_times:
            avg_time = sum(float(t) for t in processing_times) / len(processing_times)
        
        return {
            "handler_id": self.handler_id,
            "status": self.status,
            "queues": {
                "pending": pending,
                "processing": processing,
                "completed": completed,
                "failed": failed,
                "avg_processing_time": avg_time
            },
            "stats": self.stats
        } 