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

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))

from src.backend.sitesearch.handler import HandlerFactory, ComponentStatus
from src.backend.sitesearch.crawler import BaseCrawler
from src.backend.sitesearch.cleaner import DataCleaner
from src.backend.sitesearch.storage.manager import DataStorage
from src.backend.sitesearch.indexer import DataIndexer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 定义每个组件的worker进程函数
def component_worker(component_type, redis_url, milvus_uri, worker_id, config):
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
    # init_django()
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
                sleep_time=sleep_time
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
            self.redis_client.delete(f"sitesearch:queue:{queue_name}")
        print("已删除已完成的队列")
        # 未完成的放到队列头部
        for queue_name in ["crawler", "cleaner", "storage", "indexer"]:
            # self.redis_client.lpush(f"sitesearch:queue:{queue_name}", "https://www.baidu.com")
            self.redis_client.delete(f"sitesearch:processing:{queue_name}")
            self.redis_client.delete(f"sitesearch:completed:{queue_name}")
            self.redis_client.delete(f"sitesearch:failed:{queue_name}")
            self.redis_client.delete(f"sitesearch:processing_times:{queue_name}")
        
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
                              cleaner_workers: int = 1, 
                              storage_workers: int = 1, 
                              indexer_workers: int = 1):
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
        获取组件状态
        
        Args:
            component_type: 组件类型
            
        Returns:
            Dict[str, Any]: 组件状态信息
        """
        processes = self.processes.get(component_type, [])
        
        # 获取活跃进程数
        active_count = sum(1 for p in processes if p.is_alive())
        
        # 获取组件配置
        config = self.component_configs.get(component_type, {})
        
        # 获取队列指标 (对应的队列名称)        
        queue_metrics = self.get_queue_metrics(component_type)
        
        return {
            "type": component_type,
            "total_processes": len(processes),
            "active_processes": active_count,
            "status": "running" if active_count > 0 else "stopped",
            "config": config,
            "queue_metrics": queue_metrics
        }
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        获取系统状态信息，包括所有组件进程状态、队列状态和任务状态
        
        Returns:
            Dict[str, Any]: 系统状态信息
        """
        import psutil
        
        # 获取组件状态
        components = {}
        for component_type in ["cleaner", "storage", "indexer"]:
            components[component_type] = self.get_component_status(component_type)
        
        # 获取队列状态
        queues = {}
        for queue_name in ["crawler", "cleaner", "storage"]:
            queues[queue_name] = self.get_queue_metrics(queue_name)
        
        # 获取系统资源使用情况
        system_resources = {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "timestamp": datetime.now().isoformat()
        }
        
        # 获取所有任务状态
        tasks = self.get_all_tasks_status()
        
        # 获取工作进程计数
        workers_count = self.get_workers_count()
        
        # 监控状态
        monitoring = {
            "is_active": self.is_monitoring,
            "interval": self.monitor_interval
        }
        
        return {
            "components": components,
            "queues": queues,
            "tasks": tasks,
            "workers_count": workers_count,
            "system_resources": system_resources,
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
            site_id: str = "default", 
            max_urls: int = 1000,
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
            "crawler_type": crawler_type
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
                args=("crawler", self.redis_url, self.milvus_uri, f"{task_id}-{i}", task_config)
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
            print(f"已将URL添加到任务 {task_id} 的爬取队列: {url}")
            return True
        except Exception as e:
            print(f"添加URL到任务队列失败: {str(e)}")
            return False
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        获取指定任务的状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict[str, Any]: 任务状态信息
        """
        if task_id not in self.tasks:
            return {"error": "任务不存在"}
        
        task_info = self.tasks[task_id].copy()
        
        # 添加队列统计信息（使用get_queue_metrics）
        input_queue = task_info["input_queue"]
        queue_metrics = self.get_queue_metrics(input_queue)
        
        # 检查爬虫进程是否还在运行
        active_processes = sum(1 for p in task_info["processes"] if p.is_alive())
        if active_processes == 0 and queue_metrics["pending"] == 0:
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
        task_info["active_processes"] = active_processes
        
        # 移除不需要返回的进程对象
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
        
        # 清空任务的队列
        input_queue = task_info["input_queue"]
        self.redis_client.delete(input_queue)
        
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
        import psutil
        
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
    
    def add_url_to_queue(self, url: str, site_id: str = "default") -> str:
        """
        向爬取队列添加URL（创建一个新的爬取任务）
        
        Args:
            url: 要爬取的URL
            site_id: 站点ID
            
        Returns:
            str: 创建的任务ID
        """
        # 创建新任务
        task_id = self.create_crawl_task(
            start_url=url,
            site_id=site_id,
            max_urls=1000,
            max_depth=3
        )
        return task_id
    
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
