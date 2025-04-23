import time
import logging
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from .queue_manager import get_queue_manager, QueueMetrics

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('queue_monitor')

@dataclass
class QueueHealthStatus:
    """队列健康状态"""
    queue_name: str
    is_healthy: bool = True
    pending_tasks: int = 0
    processing_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    avg_processing_time: float = 0.0
    last_activity_time: float = 0.0
    stalled: bool = False
    backlog_size_warning: bool = False
    error_rate_warning: bool = False
    message: str = ""

class QueueMonitor:
    """队列监控器，定期检查队列状态并提供告警"""
    
    def __init__(
        self, 
        queue_names: List[str],
        check_interval: int = 60,  # 检查间隔（秒）
        max_pending_threshold: int = 1000,  # 最大积压任务数量阈值
        max_error_rate: float = 0.1,  # 最大错误率阈值
        activity_timeout: int = 300,  # 活动超时时间（秒）
    ):
        """
        初始化队列监控器
        
        Args:
            queue_names: 要监控的队列名称列表
            check_interval: 检查间隔（秒）
            max_pending_threshold: 最大积压任务数量阈值
            max_error_rate: 最大错误率阈值
            activity_timeout: 活动超时时间（秒）
        """
        self.queue_manager = get_queue_manager()
        self.queue_names = queue_names
        self.check_interval = check_interval
        self.max_pending_threshold = max_pending_threshold
        self.max_error_rate = max_error_rate
        self.activity_timeout = activity_timeout
        
        # 存储队列健康状态
        self.health_status: Dict[str, QueueHealthStatus] = {}
        
        # 存储历史指标数据
        self.metrics_history: Dict[str, List[QueueMetrics]] = {queue: [] for queue in queue_names}
        
        # 最大历史记录数量
        self.max_history_size = 100
        
        # 告警回调函数
        self.alert_callbacks: List[Callable[[QueueHealthStatus], None]] = []
        
        # 监控线程
        self.monitor_thread = None
        self.stop_event = threading.Event()
    
    def start(self):
        """启动监控线程"""
        if self.monitor_thread is not None and self.monitor_thread.is_alive():
            logger.warning("监控线程已经在运行")
            return
        
        self.stop_event.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info(f"队列监控已启动，监控间隔: {self.check_interval}秒")
    
    def stop(self):
        """停止监控线程"""
        if self.monitor_thread is None or not self.monitor_thread.is_alive():
            logger.warning("监控线程未运行")
            return
        
        self.stop_event.set()
        self.monitor_thread.join(timeout=5)
        if self.monitor_thread.is_alive():
            logger.warning("监控线程无法正常停止")
        else:
            logger.info("队列监控已停止")
    
    def add_alert_callback(self, callback: Callable[[QueueHealthStatus], None]):
        """
        添加告警回调函数
        
        Args:
            callback: 当检测到队列异常时调用的回调函数
        """
        self.alert_callbacks.append(callback)
    
    def _monitor_loop(self):
        """监控循环"""
        while not self.stop_event.is_set():
            try:
                # 检查所有队列
                for queue_name in self.queue_names:
                    self._check_queue_health(queue_name)
                
                # 等待下次检查
                self.stop_event.wait(self.check_interval)
            except Exception as e:
                logger.error(f"监控线程出错: {e}")
                # 短暂等待后继续
                self.stop_event.wait(5)
    
    def _check_queue_health(self, queue_name: str):
        """
        检查队列健康状态
        
        Args:
            queue_name: 队列名称
        """
        try:
            # 获取队列指标
            metrics = self.queue_manager.get_queue_metrics(queue_name)
            
            # 记录活动时间
            current_time = time.time()
            
            # 添加到历史记录
            self.metrics_history[queue_name].append(metrics)
            if len(self.metrics_history[queue_name]) > self.max_history_size:
                self.metrics_history[queue_name].pop(0)
            
            # 创建健康状态对象
            health = QueueHealthStatus(
                queue_name=queue_name,
                pending_tasks=metrics.pending_tasks,
                processing_tasks=metrics.processing_tasks,
                completed_tasks=metrics.completed_tasks,
                failed_tasks=metrics.failed_tasks,
                avg_processing_time=metrics.avg_processing_time,
                last_activity_time=current_time
            )
            
            # 检查队列积压
            if metrics.pending_tasks > self.max_pending_threshold:
                health.backlog_size_warning = True
                health.is_healthy = False
                health.message += f"队列积压任务过多 ({metrics.pending_tasks}>{self.max_pending_threshold}). "
            
            # 计算错误率
            total_tasks = metrics.completed_tasks + metrics.failed_tasks
            if total_tasks > 0:
                error_rate = metrics.failed_tasks / total_tasks
                if error_rate > self.max_error_rate:
                    health.error_rate_warning = True
                    health.is_healthy = False
                    health.message += f"队列错误率过高 ({error_rate:.2%}>{self.max_error_rate:.2%}). "
            
            # 检查队列活动
            last_status = self.health_status.get(queue_name)
            if last_status:
                # 检查处理中的任务数量是否长时间不变
                if (metrics.processing_tasks > 0 and 
                    metrics.processing_tasks == last_status.processing_tasks and
                    current_time - last_status.last_activity_time > self.activity_timeout):
                    health.stalled = True
                    health.is_healthy = False
                    health.message += f"队列处理活动长时间无变化 ({int(current_time - last_status.last_activity_time)}秒). "
            
            # 更新健康状态
            self.health_status[queue_name] = health
            
            # 如果不健康，触发告警
            if not health.is_healthy:
                logger.warning(f"队列 {queue_name} 健康状态异常: {health.message}")
                # 调用所有告警回调函数
                for callback in self.alert_callbacks:
                    try:
                        callback(health)
                    except Exception as e:
                        logger.error(f"执行告警回调时出错: {e}")
            
        except Exception as e:
            logger.error(f"检查队列 {queue_name} 健康状态时出错: {e}")
    
    def get_queue_health(self, queue_name: str) -> Optional[QueueHealthStatus]:
        """
        获取队列健康状态
        
        Args:
            queue_name: 队列名称
            
        Returns:
            Optional[QueueHealthStatus]: 健康状态对象
        """
        return self.health_status.get(queue_name)
    
    def get_all_queue_health(self) -> Dict[str, QueueHealthStatus]:
        """
        获取所有队列的健康状态
        
        Returns:
            Dict[str, QueueHealthStatus]: 队列名称到健康状态的映射
        """
        return self.health_status.copy()
    
    def get_metrics_history(self, queue_name: str) -> List[QueueMetrics]:
        """
        获取队列指标历史记录
        
        Args:
            queue_name: 队列名称
            
        Returns:
            List[QueueMetrics]: 指标历史记录
        """
        return self.metrics_history.get(queue_name, []).copy()
    
    def get_summary_report(self) -> Dict[str, Any]:
        """
        生成监控摘要报告
        
        Returns:
            Dict[str, Any]: 包含队列健康状态摘要的字典
        """
        unhealthy_queues = []
        total_pending = 0
        total_processing = 0
        total_failed = 0
        
        for queue_name, health in self.health_status.items():
            total_pending += health.pending_tasks
            total_processing += health.processing_tasks
            total_failed += health.failed_tasks
            
            if not health.is_healthy:
                unhealthy_queues.append({
                    "name": queue_name,
                    "issues": health.message,
                    "pending": health.pending_tasks,
                    "processing": health.processing_tasks,
                    "failed": health.failed_tasks
                })
        
        return {
            "timestamp": time.time(),
            "total_queues": len(self.queue_names),
            "unhealthy_queues": len(unhealthy_queues),
            "unhealthy_details": unhealthy_queues,
            "total_pending_tasks": total_pending,
            "total_processing_tasks": total_processing,
            "total_failed_tasks": total_failed
        }

# 单例模式
_queue_monitor_instance = None

def get_queue_monitor(
    queue_names: Optional[List[str]] = None,
    check_interval: int = 60,
    max_pending_threshold: int = 1000,
    max_error_rate: float = 0.1,
    activity_timeout: int = 300
) -> QueueMonitor:
    """
    获取队列监控器单例
    
    Args:
        queue_names: 要监控的队列名称列表，仅在首次调用时有效
        check_interval: 检查间隔（秒），仅在首次调用时有效
        max_pending_threshold: 最大积压任务数量阈值，仅在首次调用时有效
        max_error_rate: 最大错误率阈值，仅在首次调用时有效
        activity_timeout: 活动超时时间（秒），仅在首次调用时有效
        
    Returns:
        QueueMonitor: 队列监控器实例
    """
    global _queue_monitor_instance
    if _queue_monitor_instance is None:
        if queue_names is None:
            raise ValueError("首次调用必须提供队列名称列表")
        _queue_monitor_instance = QueueMonitor(
            queue_names=queue_names,
            check_interval=check_interval,
            max_pending_threshold=max_pending_threshold,
            max_error_rate=max_error_rate,
            activity_timeout=activity_timeout
        )
    return _queue_monitor_instance 