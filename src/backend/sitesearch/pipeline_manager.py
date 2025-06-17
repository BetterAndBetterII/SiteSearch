import logging
import time
import threading
from typing import Dict, List, Optional, Any
import redis
from datetime import datetime
import time
import threading
import sys
import signal
import json
from multiprocessing import Process
from typing import Dict, Any, List
import uuid
import os
import psutil

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 定义每个组件的worker进程函数
def component_worker(component_type, redis_url, milvus_uri, worker_id, config, start_delay=0.0):
    """
    组件worker进程的入口函数
    
    Args:
        component_type: 组件类型 (crawler, cleaner, storage, indexer)
        redis_url: Redis连接URL
        milvus_uri: Milvus连接URI (仅用于索引器)
        worker_id: worker ID
        config: 组件配置
    """
    # 初始化Django
    from src.backend.sitesearch.utils.django_init import init_django
    init_django()
    from src.backend.sitesearch.handler import HandlerFactory, ComponentStatus
    
    # 初始化Redis客户端用于记录处理时间和更新活动时间
    redis_client = redis.from_url(redis_url)
    
    handler_id = f"{component_type}-worker-{worker_id}"
    print(f"启动 {handler_id}")
    
    # 提取配置信息
    batch_size = config.get("batch_size", 1)
    sleep_time = config.get("sleep_time", 0.5)
    input_queue = config.get("input_queue", component_type)  # 默认使用组件名作为队列名
    output_queue = config.get("output_queue", None)  # 可以为None，由组件默认值决定
    
    # 根据组件类型创建对应的handler
    handler = None
    try:
        if component_type == "crawler":
            # 爬虫需要特殊处理，因为每个任务有自己的input_queue
            handler = HandlerFactory.create_crawler_handler(
                redis_url=redis_url,
                handler_id=handler_id,
                input_queue=input_queue,  # 使用配置中的input_queue
                output_queue=output_queue or "crawler",  # 如果未指定，使用默认值
                crawler_config=config.get("crawler_config", {}),
                batch_size=batch_size,
                sleep_time=sleep_time,
                start_delay=start_delay,
                auto_exit=True
            )
        elif component_type == "cleaner":
            handler = HandlerFactory.create_cleaner_handler(
                redis_url=redis_url,
                handler_id=handler_id,
                output_queue=output_queue or "cleaner",
                strategies=config.get("strategies", None),
                batch_size=batch_size,
                sleep_time=sleep_time
            )
        elif component_type == "storage":
            handler = HandlerFactory.create_storage_handler(
                redis_url=redis_url,
                handler_id=handler_id,
                output_queue=output_queue or "storage",
                batch_size=batch_size,
                sleep_time=sleep_time
            )
        elif component_type == "indexer" and milvus_uri:
            handler = HandlerFactory.create_indexer_handler(
                redis_url=redis_url,
                milvus_uri=milvus_uri,
                handler_id=handler_id,
                batch_size=batch_size,
                sleep_time=sleep_time
            )
        else:
            print(f"未知的组件类型: {component_type}")
            return
        
        # 设置信号处理
        def signal_handler(sig, frame):
            print(f"\n进程 {handler_id} 接收到停止信号，正在关闭...")
            if handler:
                handler.stop()
            print(f"进程 {handler_id} 已安全关闭")
            sys.exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # 启动handler
        if handler:
            handler.start()
            print(f"{handler_id} 已启动")
            
            # 保持进程运行
            try:
                while True:
                    if not handler.running:
                        break
                    # 更新最后活动时间
                    last_activity_key = f"sitesearch:last_activity:{input_queue}"
                    current_time = time.time()
                    redis_client.set(last_activity_key, str(current_time))
                        
                    # 获取处理统计信息
                    status = handler.get_stats()
                    
                    # 如果有处理任务数据，记录处理时间
                    if status and "processed_count" in status and status["processed_count"] > 0:
                        if "avg_processing_time" in status and status["avg_processing_time"] > 0:
                            processing_times_key = f"sitesearch:processing_times:{input_queue}"
                            # 最多保存100个最近的处理时间
                            redis_client.lpush(processing_times_key, str(status["avg_processing_time"]))
                            redis_client.ltrim(processing_times_key, 0, 99)
                    
                    time.sleep(5)
            except KeyboardInterrupt:
                print(f"\n进程 {handler_id} 接收到停止信号")
            finally:
                if handler:
                    handler.stop()
                print(f"进程 {handler_id} 已关闭")
    
    except Exception as e:
        print(f"{handler_id} 发生错误: {str(e)}")
        if handler:
            handler.stop()


class MultiProcessSiteSearchManager:
    """支持多进程的站点搜索管理器"""
    
    def __init__(self, redis_url: str, milvus_uri: str = None):
        """
        初始化管理器
        
        Args:
            redis_url: Redis连接URL
            milvus_uri: Milvus连接URI，用于索引器
        """
        self.main_pid = os.getpid()
        self.redis_url = redis_url
        self.milvus_uri = milvus_uri
        
        # 导入redis模块
        self.redis_client = redis.from_url(redis_url)
        
        # 进程管理
        self.processes = {
            "crawler": [],
            "cleaner": [],
            "storage": [],
            "indexer": []
        }
        
        # 组件配置
        self.component_configs = {
            "crawler": {},
            "cleaner": {},
            "storage": {},
            "indexer": {}
        }

        # 任务管理
        self.tasks = {}  # 存储任务信息
        self.crawler_handlers = {}  # 存储每个任务的爬虫handler
        
        # 共享处理组件
        self.shared_components = {
            "cleaner": None,
            "storage": None,
            "indexer": None
        }
        
        # 监控线程
        self.monitor_thread = None
        self.is_monitoring = False
        self.monitor_interval = 10

        self.setup_queues()

    def setup_queues(self):
        """
        设置队列，策略：删除已完成的，未完成的放到队列头部，失败的由用户决定
        """
        # 删除已完成的
        for queue_name in ["crawler", "cleaner", "storage", "indexer"]:
            self.redis_client.delete(f"sitesearch:processing:{queue_name}")
            self.redis_client.delete(f"sitesearch:completed:{queue_name}")
            self.redis_client.delete(f"sitesearch:failed:{queue_name}")
            self.redis_client.delete(f"sitesearch:processing_times:{queue_name}")
        print("已删除已完成的队列")
        # 未完成的放到队列头部
        # for queue_name in ["crawler", "cleaner", "storage", "indexer"]:
            # self.redis_client.lpush(f"sitesearch:queue:{queue_name}", "https://www.baidu.com")
            # self.redis_client.delete(f"sitesearch:processing:{queue_name}")
            # self.redis_client.delete(f"sitesearch:completed:{queue_name}")
            # self.redis_client.delete(f"sitesearch:failed:{queue_name}")
            # self.redis_client.delete(f"sitesearch:processing_times:{queue_name}")
            # for item in self.redis_client.lrange(f"sitesearch:queue:{queue_name}", 0, -1):
            #     self.redis_client.lpush(f"sitesearch:queue:{queue_name}", item)
        
    def initialize_components(self, 
                            crawler_config: Dict[str, Any] = None,
                            cleaner_strategies: List = None,
                            storage_config: Dict[str, Any] = None,
                            indexer_config: Dict[str, Any] = None):
        """
        初始化所有组件配置
        
        Args:
            crawler_config: 爬虫配置
            cleaner_strategies: 清洗策略列表
            storage_config: 存储配置
            indexer_config: 索引器配置
        """
        # 存储配置
        self.component_configs["crawler"] = {
            "crawler_config": crawler_config or {},
            "batch_size": 1,
            "sleep_time": 0.5
        }
        
        self.component_configs["cleaner"] = {
            "strategies": cleaner_strategies,
            "batch_size": 5,
            "sleep_time": 0.1
        }
        
        self.component_configs["storage"] = {
            "storage_config": storage_config or {},
            "batch_size": 5,
            "sleep_time": 0.1
        }
        
        self.component_configs["indexer"] = {
            "indexer_config": indexer_config or {},
            "batch_size": 8,
            "sleep_time": 0.2
        }
        
        print("所有组件配置已初始化")
        
    def start_shared_components(self, 
                              cleaner_workers: int = 2, 
                              storage_workers: int = 1, 
                              indexer_workers: int = 4):
        """
        启动共享组件（清洗器、存储器、索引器）
        
        Args:
            cleaner_workers: 清洗器worker数量
            storage_workers: 存储器worker数量
            indexer_workers: 索引器worker数量
        """
        # 启动清洗器workers
        for i in range(cleaner_workers):
            p = Process(
                target=component_worker,
                args=("cleaner", self.redis_url, self.milvus_uri, i, self.component_configs["cleaner"])
            )
            p.daemon = True
            p.start()
            self.processes["cleaner"].append(p)
            print(f"已启动清洗器进程 {i}")
        
        # 启动存储器workers
        for i in range(storage_workers):
            p = Process(
                target=component_worker,
                args=("storage", self.redis_url, self.milvus_uri, i, self.component_configs["storage"])
            )
            p.daemon = True
            p.start()
            self.processes["storage"].append(p)
            print(f"已启动存储器进程 {i}")
        
        # 启动索引器workers（如果有Milvus URI）
        if self.milvus_uri:
            for i in range(indexer_workers):
                p = Process(
                    target=component_worker,
                    args=("indexer", self.redis_url, self.milvus_uri, i, self.component_configs["indexer"])
                )
                p.daemon = True
                p.start()
                self.processes["indexer"].append(p)
                print(f"已启动索引器进程 {i}")
                
        print("所有共享组件进程已启动")
    
    def adjust_workers(self, component_type: str, target_count: int) -> bool:
        """
        动态调整指定共享组件的工作进程数量
        
        Args:
            component_type: 组件类型，可选值为 "cleaner", "storage", "indexer"
            target_count: 目标进程数量
            
        Returns:
            bool: 是否成功调整
        """
        # 确保组件类型有效
        if component_type not in ["crawler", "cleaner", "storage", "indexer"]:
            print(f"无效的组件类型: {component_type}，只能调整共享组件")
            return False
            
        # 如果是索引器组件但没有Milvus URI，则返回失败
        if component_type == "indexer" and not self.milvus_uri:
            print("无法调整索引器组件，未配置Milvus URI")
            return False
            
        current_count = len(self.processes[component_type])
        print(f"当前 {component_type} 组件进程数: {current_count}，目标进程数: {target_count}")
        
        # 如果目标数量与当前数量相同，无需调整
        if target_count == current_count:
            print(f"{component_type} 组件进程数已经是 {target_count}，无需调整")
            return True
            
        # 如果需要增加进程
        if target_count > current_count:
            # 计算需要新增的进程数
            new_processes_count = target_count - current_count
            
            # 创建新进程
            for i in range(current_count, target_count):
                if component_type == "crawler":
                    for task_id, task_info in self.tasks.items():
                        if task_info["status"] == "running":
                            task_config = self.component_configs[component_type].copy()
                            task_config["input_queue"] = task_info["input_queue"]
                            task_config["output_queue"] = "crawler"
                            task_config["crawler_config"] = task_info["crawler_config"]
                            task_config["batch_size"] = task_info["crawler_workers"]
                            task_config["sleep_time"] = task_info["sleep_time"]

                            p = Process(
                                target=component_worker,
                                args=(component_type, self.redis_url, self.milvus_uri, f"{task_id}-{i}", task_config)
                            )
                            p.daemon = True
                            p.start()
                            self.processes[component_type].append(p)
                            print(f"已增加 {component_type} 进程 {i}")
                else:
                    p = Process(
                        target=component_worker,
                        args=(component_type, self.redis_url, self.milvus_uri, i, self.component_configs[component_type])
                    )
                    p.daemon = True
                    p.start()
                    self.processes[component_type].append(p)
                    print(f"已增加 {component_type} 进程 {i}")
                
            print(f"已成功增加 {new_processes_count} 个 {component_type} 进程")
            return True
            
        # 如果需要减少进程
        elif target_count < current_count:
            if component_type == "crawler":
                raise ValueError("爬虫组件不能手动减少进程数量")
            # 获取要关闭的进程
            processes_to_close = self.processes[component_type][target_count:]
            
            # 从列表中移除（保留前 target_count 个进程）
            self.processes[component_type] = self.processes[component_type][:target_count]
            
            # 关闭多余的进程
            for i, p in enumerate(processes_to_close):
                if p.is_alive():
                    p.terminate()
                    print(f"已发送终止信号给 {component_type} 进程 {i + target_count}")
            
            # 等待进程结束
            for i, p in enumerate(processes_to_close):
                p.join(timeout=5)
                if not p.is_alive():
                    print(f"{component_type} 进程 {i + target_count} 已正常终止")
                
            # 强制终止未能正常结束的进程
            for i, p in enumerate(processes_to_close):
                if p.is_alive():
                    print(f"{component_type} 进程 {i + target_count} 未能正常终止，强制终止")
                    p.kill()
            
            print(f"已成功减少 {len(processes_to_close)} 个 {component_type} 进程")
            return True
        
        return False
        
    def get_workers_count(self) -> Dict[str, int]:
        """
        获取各组件当前工作进程数量
        
        Returns:
            Dict[str, int]: 各组件的工作进程数量
        """
        result = {}
        
        # 获取共享组件的进程数
        for component_type in ["cleaner", "storage", "indexer"]:
            result[component_type] = len(self.processes[component_type])
        
        # 获取爬虫进程数（按任务分组）
        crawler_count = len(self.processes["crawler"])
        result["crawler"] = crawler_count
        
        # 按任务分组的爬虫进程数
        task_crawler_counts = {}
        for task_id, task_info in self.tasks.items():
            active_crawlers = sum(1 for p in task_info.get("processes", []) if p.is_alive())
            task_crawler_counts[task_id] = active_crawlers
        
        result["task_crawlers"] = task_crawler_counts
        
        return result
    
    def get_queue_metrics(self, component_type: str) -> Dict[str, Any]:
        """
        获取队列指标数据
        
        Args:
            component_type: 组件类型
            
        Returns:
            Dict[str, Any]: 队列指标数据
        """
        # 获取队列统计信息
        stats_key = f"sitesearch:stats:{component_type}"
        
        # 获取队列长度
        pending = self.redis_client.llen(f"sitesearch:queue:{component_type}")
        processing = self.redis_client.llen(f"sitesearch:processing:{component_type}")
        completed = self.redis_client.llen(f"sitesearch:completed:{component_type}")
        failed = self.redis_client.llen(f"sitesearch:failed:{component_type}")
        
        # 获取处理时间统计
        processing_times_key = f"sitesearch:processing_times:{component_type}"
        processing_times = self.redis_client.lrange(processing_times_key, 0, -1)
        
        # 计算平均处理时间
        if processing_times:
            processing_times = [float(t) for t in processing_times]
            avg_processing_time = sum(processing_times) / len(processing_times)
        else:
            avg_processing_time = 0
        
        # 获取最后活动时间
        last_activity_key = f"sitesearch:last_activity:{component_type}"
        last_activity = self.redis_client.get(last_activity_key)
        
        if last_activity:
            last_activity = float(last_activity)
            last_activity_time = datetime.fromtimestamp(last_activity).isoformat()
        else:
            last_activity_time = None
        
        return {
            "pending": pending,
            "processing": processing,
            "completed": completed,
            "failed": failed,
            "avg_processing_time": avg_processing_time,
            "last_activity": last_activity_time
        }
    
    def get_component_status(self, component_type: str) -> Dict[str, Any]:
        """
        获取组件状态，包括每个worker进程的资源占用情况
        
        Args:
            component_type: 组件类型
            
        Returns:
            Dict[str, Any]: 组件状态信息
        """
        processes = self.processes.get(component_type, [])
        
        alive_processes = []
        worker_details = []
        total_memory_rss_mb = 0
        total_cpu_percent = 0

        # 遍历所有已知进程，分离出存活和已死亡的
        for p in processes:
            if p.is_alive():
                alive_processes.append(p)
                try:
                    proc_info = psutil.Process(p.pid)
                    
                    # This is a blocking call, but necessary for a one-shot CPU reading.
                    # A small interval is used to minimize delay.
                    cpu_percent = proc_info.cpu_percent(interval=0.02)
                    
                    # Use oneshot() for other, non-blocking stats.
                    with proc_info.oneshot():
                        mem_info = proc_info.memory_info()
                        create_time_ts = proc_info.create_time()
                        
                    mem_rss_mb = mem_info.rss / (1024 * 1024)
                    total_memory_rss_mb += mem_rss_mb
                    total_cpu_percent += cpu_percent

                    worker_details.append({
                        "pid": p.pid,
                        "name": p.name,
                        "memory_rss_mb": round(mem_rss_mb, 2),
                        "cpu_percent": round(cpu_percent, 2),
                        "create_time": datetime.fromtimestamp(create_time_ts).isoformat(),
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    # 进程在 is_alive() 和 psutil.Process() 调用之间死掉了,
                    # 会在下一次检查中被清理
                    pass
            else:
                # 尝试优雅地join已死亡的进程
                p.join(timeout=0.1)

        # 更新组件的进程列表，只保留存活的
        if self.processes.get(component_type) is not None:
            self.processes[component_type] = alive_processes
        
        active_count = len(alive_processes)
        config = self.component_configs.get(component_type, {})
        queue_metrics = self.get_queue_metrics(component_type)
        
        return {
            "type": component_type,
            "active_processes": active_count,
            "status": "running" if active_count > 0 else "stopped",
            "config": config,
            "queue_metrics": queue_metrics,
            "workers": worker_details,
            "total_memory_rss_mb": round(total_memory_rss_mb, 2),
            "total_cpu_percent": round(total_cpu_percent, 2),
        }
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        获取系统状态信息，包括所有组件进程状态、队列状态和任务状态
        
        Returns:
            Dict[str, Any]: 系统状态信息
        """
        # 获取共享组件状态
        components = {}

        # 聚合所有爬虫任务，形成一个'crawler'组件状态
        all_crawler_workers = []
        total_crawler_processes = 0
        total_crawler_memory_mb = 0
        total_crawler_cpu_percent = 0
        
        # 获取所有任务状态, 这会更新任务详情，包括worker信息
        tasks = self.get_all_tasks_status()

        for task_id, task_info in tasks.items():
            if task_info.get("status") == "running":
                total_crawler_processes += task_info.get("active_processes", 0)
                total_crawler_memory_mb += task_info.get("total_memory_rss_mb", 0)
                total_crawler_cpu_percent += task_info.get("total_cpu_percent", 0)
                if "workers" in task_info:
                    all_crawler_workers.extend(task_info.get("workers", []))
        
        # 'crawler' 队列指标是所有爬虫的共享输出队列
        crawler_queue_metrics = self.get_queue_metrics("crawler")

        components["crawler"] = {
            "type": "crawler",
            "active_processes": total_crawler_processes,
            "status": "running" if total_crawler_processes > 0 else "stopped",
            "config": self.component_configs.get("crawler", {}),
            "queue_metrics": crawler_queue_metrics,
            "workers": all_crawler_workers,
            "total_memory_rss_mb": round(total_crawler_memory_mb, 2),
            "total_cpu_percent": round(total_crawler_cpu_percent, 2),
        }

        for component_type in ["cleaner", "storage", "indexer"]:
            components[component_type] = self.get_component_status(component_type)

        # 获取所有相关队列的状态
        queues = {}
        for queue_name in ["crawler", "cleaner", "storage", "indexer"]:
            queues[queue_name] = self.get_queue_metrics(queue_name)
        
        # 将每个活动任务的队列统计信息也添加到主队列对象中
        for task_id, task_info in tasks.items():
            if task_info.get("status") in ["running", "starting"] and "queue_stats" in task_info:
                task_queue_name = task_info.get("input_queue")
                if task_queue_name:
                    queues[task_queue_name] = task_info["queue_stats"]

        # 获取系统资源使用情况
        system_resources = {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "timestamp": datetime.now().isoformat()
        }
        
        # 获取主进程资源使用情况
        main_process_resources = {}
        try:
            main_proc = psutil.Process(self.main_pid)
            with main_proc.oneshot():
                main_process_resources = {
                    "pid": self.main_pid,
                    "memory_rss_mb": round(main_proc.memory_info().rss / (1024 * 1024), 2),
                    "cpu_percent": round(main_proc.cpu_percent(interval=0.02), 2),
                    "name": main_proc.name()
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            main_process_resources = {"error": "无法获取主进程信息"}
        
        # 获取工作进程计数
        workers_count = self.get_workers_count()
        
        # 监控状态
        monitoring = {
            "is_active": self.is_monitoring,
            "interval": self.monitor_interval
        }

        # 获取Redis指标
        redis_stats = {}
        try:
            info = self.redis_client.info()
            db_keys = 0
            for key in info:
                if key.startswith("db"):
                    db_keys += info[key].get('keys', 0)

            redis_stats = {
                "redis_version": info.get("redis_version"),
                "used_memory_human": info.get("used_memory_human"),
                "used_memory_peak_human": info.get("used_memory_peak_human"),
                "total_system_memory_human": info.get("total_system_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "total_keys": db_keys,
                "uptime_in_days": info.get("uptime_in_days"),
            }
        except Exception as e:
            print(f"无法获取Redis指标: {e}")
            redis_stats = {"error": str(e)}
        
        return {
            "components": components,
            "queues": queues,
            "tasks": tasks,
            "workers_count": workers_count,
            "system_resources": system_resources,
            "main_process_resources": main_process_resources,
            "redis_stats": redis_stats,
            "monitoring": monitoring,
            "timestamp": datetime.now().isoformat()
        }
    
    def update_last_activity(self, queue_name: str):
        """
        更新队列最后活动时间
        
        Args:
            queue_name: 队列名称
        """
        last_activity_key = f"sitesearch:last_activity:{queue_name}"
        current_time = time.time()
        self.redis_client.set(last_activity_key, str(current_time))
        
    def record_processing_time(self, queue_name: str, processing_time: float):
        """
        记录任务处理时间
        
        Args:
            queue_name: 队列名称
            processing_time: 处理时间（秒）
        """
        processing_times_key = f"sitesearch:processing_times:{queue_name}"
        # 最多保存100个最近的处理时间
        self.redis_client.lpush(processing_times_key, str(processing_time))
        self.redis_client.ltrim(processing_times_key, 0, 99)
    
    def create_crawl_task(
            self, 
            start_url: str, 
            site_id: str, 
            max_urls: int,
            max_depth: int = 3,
            regpattern: str = "*",
            crawler_type: str = "httpx",
            crawler_workers: int = 1
        ) -> str:
        """
        创建新的遍历任务
        
        Args:
            start_url: 起始URL
            site_id: 站点ID
            max_urls: 最大URL数量
            max_depth: 最大爬取深度
            regpattern: URL正则匹配模式
            crawler_workers: 爬虫worker数量
            
        Returns:
            str: 任务ID
        """
        # 生成任务ID
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        
        # 为任务创建特殊的输入队列
        input_queue = f"sitesearch:task:{task_id}:queue"
        
        # 配置爬虫
        crawler_config = self.component_configs["crawler"]["crawler_config"].copy()
        crawler_config.update({
            "max_urls": max_urls,
            "max_depth": max_depth,
            "regpattern": regpattern,
            "crawler_type": crawler_type,
            "bfs": True
        })

        task_config = {
            "crawler_config": crawler_config,
            "batch_size": 1,
            "sleep_time": 0.5,
            "input_queue": input_queue,
            "output_queue": "crawler"  # 所有爬虫共享同一个输出队列
        }
        
        # 存储任务信息
        self.tasks[task_id] = {
            "task_id": task_id,
            "start_url": start_url,
            "site_id": site_id,
            "max_urls": max_urls,
            "max_depth": max_depth,
            "regpattern": regpattern,
            "input_queue": input_queue,
            "crawler_workers": crawler_workers,
            "start_time": datetime.now().isoformat(),
            "status": "starting",
            "crawled_urls": 0,
            "crawler_config": crawler_config,
            "batch_size": 1,
            "sleep_time": 0.5,
        }
        
        # 启动爬虫workers
        crawler_processes = []
        for i in range(crawler_workers):
            
            p = Process(
                target=component_worker,
                args=("crawler", self.redis_url, self.milvus_uri, f"{task_id}-{i}", task_config, i * 3)
            )
            p.daemon = True
            p.start()
            crawler_processes.append(p)

        self.processes["crawler"].extend(crawler_processes)
        self.tasks[task_id]["processes"] = crawler_processes
        self.tasks[task_id]["status"] = "running"
        
        # 添加起始URL到任务队列
        self.add_url_to_task_queue(task_id, start_url, site_id)
        
        print(f"已创建任务: {task_id}, 起始URL: {start_url}")
        return task_id
    
    def create_crawl_update_task(
            self, 
            site_id: str, 
            urls: List[str],
            crawler_type: str = "httpx",
            crawler_workers: int = 1
        ) -> str:
        """
        创建爬取更新任务
        
        Args:
            site_id: 站点ID
            urls: 要爬取的URL列表
            
        Returns:
            str: 任务ID
        """
        task_id = f"task-{uuid.uuid4().hex[:8]}"

        # 为任务创建特殊的输入队列
        input_queue = f"sitesearch:task:{task_id}:queue"

        crawler_config = self.component_configs["crawler"]["crawler_config"].copy()
        crawler_config.update({
            "max_urls": 99999999,
            "max_depth": 99999999,
            "regpattern": "*",
            "crawler_type": crawler_type,
            "bfs": False
        })

        task_config = {
            "crawler_config": crawler_config,
            "batch_size": 1,
            "sleep_time": 0.5,
            "input_queue": input_queue,
            "output_queue": "crawler"
        }

        # 存储任务信息
        self.tasks[task_id] = {
            "task_id": task_id,
            "start_url": urls[0],
            "site_id": site_id,
            "max_urls": 99999999,
            "max_depth": 99999999,
            "regpattern": "*",
            "input_queue": input_queue,
            "crawler_workers": crawler_workers,
            "start_time": datetime.now().isoformat(),
            "status": "starting",
            "crawled_urls": 0,
            "crawler_config": crawler_config,
            "batch_size": 1,
            "sleep_time": 0.5,
        }

        crawler_processes = []
        for i in range(crawler_workers):
            p = Process(
                target=component_worker,
                args=("crawler", self.redis_url, self.milvus_uri, f"{task_id}-{i}", task_config, i * 3)
            )
            p.daemon = True
            p.start()
            crawler_processes.append(p)

        self.processes["crawler"].extend(crawler_processes)
        self.tasks[task_id]["processes"] = crawler_processes
        self.tasks[task_id]["status"] = "running"

        for url in urls:
            self.add_url_to_task_queue(task_id, url, site_id)

        print(f"已创建任务: {task_id}, 爬取更新任务")
        return task_id


    def create_document_index_task(self) -> str:
        """
        创建文档索引任务
        
        Args:
            site_id: 站点ID
            
        Returns:
            str: 任务ID
        """
        from src.backend.sitesearch.storage.utils import get_pending_index_documents, get_document_sites
        documents = get_pending_index_documents(limit=1000000000)
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        for document in documents:
            indexer_input_queue = f"sitesearch:queue:storage"
            sites = get_document_sites(document.id)
            for site in sites:
                task = {  
                    "url": document.url,
                    "content": document.content,
                    "document_id": document.id,
                    "clean_content": document.clean_content,
                    "status_code": document.status_code,
                    "headers": document.headers,
                    "timestamp": document.timestamp,
                    "links": document.links,
                    "mimetype": document.mimetype,
                    "metadata": document.metadata,
                    "content_hash": document.content_hash,
                    "crawler_id": document.crawler_id,
                    "crawler_type": document.crawler_type,
                    "crawler_config": document.crawler_config,
                    "site_id": site,
                    "version": document.version,
                    "index_operation": "new",
                    "is_indexed": False
                }
            self.redis_client.lpush(indexer_input_queue, json.dumps(task))

        return task_id
    
    def add_url_to_task_queue(self, task_id: str, url: str, site_id: str = None) -> bool:
        """
        向指定任务的爬取队列添加URL
        
        Args:
            task_id: 任务ID
            url: 要爬取的URL
            site_id: 站点ID (如果为None，使用任务的默认site_id)
            
        Returns:
            bool: 是否成功添加
        """
        try:
            # 检查任务是否存在
            if task_id not in self.tasks:
                print(f"任务不存在: {task_id}")
                return False
            
            # 如果没有指定site_id，使用任务默认的site_id
            if site_id is None:
                site_id = self.tasks[task_id]["site_id"]
            
            # 获取任务的输入队列名称
            input_queue = f"sitesearch:queue:{self.tasks[task_id]['input_queue']}"
            
            # 准备爬取任务
            task = {
                "url": url,
                "site_id": site_id,
                "timestamp": time.time(),
                "task_id": task_id
            }
            
            # 将任务添加到爬取队列
            self.redis_client.lpush(input_queue, json.dumps(task))
            print(f"已将URL添加到任务 {input_queue} 的爬取队列: {url}")
            return True
        except Exception as e:
            print(f"添加URL到任务队列失败: {str(e)}")
            return False
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        获取指定任务的状态，包括其worker进程的资源占用情况
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict[str, Any]: 任务状态信息
        """
        if task_id not in self.tasks:
            return {"error": "任务不存在"}
        
        task_info = self.tasks[task_id].copy()
        
        input_queue = task_info["input_queue"]
        queue_metrics = self.get_queue_metrics(input_queue)

        # 获取任务相关进程的详细信息
        task_processes = task_info.get("processes", [])
        alive_processes = []
        worker_details = []
        total_memory_rss_mb = 0
        total_cpu_percent = 0

        for p in task_processes:
            if p.is_alive():
                alive_processes.append(p)
                try:
                    proc_info = psutil.Process(p.pid)

                    # This is a blocking call, but necessary for a one-shot CPU reading.
                    cpu_percent = proc_info.cpu_percent(interval=0.02)

                    with proc_info.oneshot():
                        mem_info = proc_info.memory_info()
                        create_time_ts = proc_info.create_time()

                    mem_rss_mb = mem_info.rss / (1024 * 1024)
                    total_memory_rss_mb += mem_rss_mb
                    total_cpu_percent += cpu_percent
                    
                    worker_details.append({
                        "pid": p.pid,
                        "name": p.name,
                        "memory_rss_mb": round(mem_rss_mb, 2),
                        "cpu_percent": round(cpu_percent, 2),
                        "create_time": datetime.fromtimestamp(create_time_ts).isoformat(),
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            else:
                p.join(timeout=0.1)

        # 更新任务的进程列表，只保留存活的
        self.tasks[task_id]["processes"] = alive_processes
        
        active_count = len(alive_processes)
        if active_count == 0 and queue_metrics["pending"] == 0 and queue_metrics["processing"] == 0:
            task_info["status"] = "completed"
        
        # 更新任务状态信息
        task_info["queue_stats"] = {
            "pending": queue_metrics["pending"],
            "processing": queue_metrics["processing"],
            "completed": queue_metrics["completed"],
            "failed": queue_metrics["failed"],
            "avg_processing_time": queue_metrics["avg_processing_time"],
            "last_activity": queue_metrics["last_activity"]
        }
        task_info["active_processes"] = active_count
        task_info["workers"] = worker_details
        task_info["total_memory_rss_mb"] = round(total_memory_rss_mb, 2)
        task_info["total_cpu_percent"] = round(total_cpu_percent, 2)
        
        # 移除不需要返回的原始进程对象
        if "processes" in task_info:
            del task_info["processes"]
        
        return task_info
    
    def stop_task(self, task_id: str) -> bool:
        """
        停止指定任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功停止
        """
        if task_id not in self.tasks:
            print(f"任务不存在: {task_id}")
            return False
        
        task_info = self.tasks[task_id]
        
        # 停止任务的爬虫进程
        for p in task_info["processes"]:
            if p.is_alive():
                p.terminate()
                
        # 等待进程结束
        for p in task_info["processes"]:
            p.join(timeout=5)
            
        # 检查是否有未结束的进程
        for i, p in enumerate(task_info["processes"]):
            if p.is_alive():
                print(f"任务 {task_id} 的爬虫进程 {i} 未能正常终止，强制终止")
                p.kill()
        
        # 从爬虫进程列表中移除
        self.processes["crawler"] = [p for p in self.processes["crawler"] if p not in task_info["processes"]]
        
        # 清空任务的队列和去重集合
        input_queue_name = task_info["input_queue"]
        
        # 构造所有相关的Redis键
        full_input_queue_key = f"sitesearch:queue:{input_queue_name}"
        crawled_urls_key = f"crawler:crawled_urls:{full_input_queue_key}"
        last_activity_key = f"sitesearch:last_activity:{input_queue_name}"
        processing_times_key = f"sitesearch:processing_times:{input_queue_name}"

        # 一次性删除所有相关的键
        self.redis_client.delete(
            full_input_queue_key, 
            crawled_urls_key,
            last_activity_key,
            processing_times_key
        )
        
        # 更新任务状态
        task_info["status"] = "stopped"
        task_info["end_time"] = datetime.now().isoformat()
        
        print(f"任务 {task_id} 已停止")
        return True
    
    def start_monitoring(self):
        """开始监控系统状态"""
        if self.is_monitoring:
            print("监控已在运行")
            return
            
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("开始系统监控")
    
    def _monitor_loop(self):
        """监控循环，定期检查系统状态和进程状态"""
        while self.is_monitoring:
            try:
                # 检查共享组件进程状态
                for component in ["crawler", "cleaner", "storage", "indexer"]:
                    alive_count = sum(1 for p in self.processes[component] if p.is_alive())
                    print(f"{component}: {alive_count}/{len(self.processes[component])} 个进程活跃")
                
                # 检查任务状态
                for task_id, task_info in self.tasks.items():
                    if task_info["status"] == "running":
                        active_processes = sum(1 for p in task_info["processes"] if p.is_alive())
                        
                        # 获取队列状态（使用get_queue_metrics）
                        queue_metrics = self.get_queue_metrics(task_id)
                        
                        print(f"任务 {task_id}:")
                        print(f"  活跃进程: {active_processes}/{len(task_info['processes'])}")
                        print(f"  队列状态: 待处理 {queue_metrics['pending']}, 处理中 {queue_metrics['processing']}, "
                              f"已完成 {queue_metrics['completed']}, 失败 {queue_metrics['failed']}")
                        
                        # 检查任务是否已完成
                        if active_processes == 0 and queue_metrics['pending'] == 0:
                            print(f"任务 {task_id} 已完成")
                            task_info["status"] = "completed"
                            task_info["end_time"] = datetime.now().isoformat()

                            # 清理任务相关的Redis数据
                            input_queue_name = task_info["input_queue"]
                            full_input_queue_key = f"sitesearch:queue:{input_queue_name}"
                            crawled_urls_key = f"crawler:crawled_urls:{full_input_queue_key}"
                            last_activity_key = f"sitesearch:last_activity:{input_queue_name}"
                            processing_times_key = f"sitesearch:processing_times:{input_queue_name}"

                            self.redis_client.delete(
                                full_input_queue_key,
                                crawled_urls_key,
                                last_activity_key,
                                processing_times_key
                            )
                            print(f"已清理任务 {task_id} 的所有相关Redis键")
                
                # 检查cleaner，storage，indexer队列（使用get_queue_metrics）
                for component in ["crawler", "cleaner", "storage", "indexer"]:
                    # 获取正确的队列名称                    
                    queue_metrics = self.get_queue_metrics(component)
                    print(f"{component} 队列状态:")
                    print(f"  待处理: {queue_metrics['pending']}")
                    print(f"  处理中: {queue_metrics['processing']}")
                    print(f"  已完成: {queue_metrics['completed']}")
                    print(f"  失败: {queue_metrics['failed']}")
                    print(f"  平均处理时间: {queue_metrics['avg_processing_time']:.4f}秒")
                    if queue_metrics['last_activity']:
                        print(f"  最后活动时间: {queue_metrics['last_activity']}")

                # 系统资源情况
                print("系统资源:")
                print(f"  CPU使用率: {psutil.cpu_percent()}%")
                print(f"  内存使用率: {psutil.virtual_memory().percent}%")
                
                print("-" * 50)
                
                # 休眠间隔
                time.sleep(self.monitor_interval)
                
            except Exception as e:
                print(f"监控过程发生错误: {str(e)}")
                time.sleep(self.monitor_interval)
                
    def stop_monitoring(self):
        """停止监控"""
        if not self.is_monitoring:
            return
            
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
            self.monitor_thread = None
        print("系统监控已停止")
    
    def get_all_tasks_status(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有任务的状态信息
        
        Returns:
            Dict[str, Dict[str, Any]]: 所有任务的状态信息
        """
        result = {}
        for task_id in self.tasks:
            result[task_id] = self.get_task_status(task_id)
        return result
    
    def shutdown(self):
        """关闭所有资源和进程"""
        print("正在关闭所有任务和组件...")
        
        # 停止监控
        self.stop_monitoring()
        
        # 停止所有任务
        for task_id in list(self.tasks.keys()):
            self.stop_task(task_id)
        
        # 关闭共享组件进程
        for component in ["cleaner", "storage", "indexer"]:
            for proc in self.processes[component]:
                if proc.is_alive():
                    proc.terminate()
            
        # 等待所有进程结束
        for component in ["cleaner", "storage", "indexer"]:
            for proc in self.processes[component]:
                proc.join(timeout=5)
                
        # 检查是否有未结束的进程
        for component in ["cleaner", "storage", "indexer"]:
            for i, proc in enumerate(self.processes[component]):
                if proc.is_alive():
                    print(f"{component} 进程 {i} 未能正常终止，强制终止")
                    proc.kill()
        
        # 清空队列
        print("清理Redis队列...")
        # 清理共享队列
        for queue_name in ["crawler", "cleaner", "storage"]:
            self.redis_client.delete(f"sitesearch:queue:{queue_name}")
            self.redis_client.delete(f"sitesearch:processing:{queue_name}")
            self.redis_client.delete(f"sitesearch:completed:{queue_name}")
            self.redis_client.delete(f"sitesearch:failed:{queue_name}")
            self.redis_client.delete(f"sitesearch:processing_times:{queue_name}")
        
        # 清理任务队列
        for task_id in self.tasks:
            input_queue = self.tasks[task_id]["input_queue"]
            self.redis_client.delete(input_queue)
            
        # 关闭Redis连接
        self.redis_client.close()
            
        print("系统已安全关闭")
