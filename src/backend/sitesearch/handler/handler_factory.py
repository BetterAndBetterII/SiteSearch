import os
import logging
from typing import Dict, Any, List, Optional

from .base_handler import BaseHandler
from .crawler_handler import CrawlerHandler
from .cleaner_handler import CleanerHandler
from .storage_handler import StorageHandler
from .indexer_handler import IndexerHandler
from .refresh_handler import RefreshHandler

logger = logging.getLogger("handler_factory")

class HandlerFactory:
    """Handler工厂类，用于创建和管理各种Handler"""
    
    # 存储已创建的Handler实例
    _handlers: Dict[str, BaseHandler] = {}
    
    @classmethod
    def create_crawler_handler(
        cls,
        redis_url: str,
        handler_id: str = None,
        input_queue: str = "url",
        output_queue: str = "crawler",
        crawler_config: Dict[str, Any] = None,
        batch_size: int = 1,
        sleep_time: float = 0.5,
        start_delay: float = 0.0,
        max_retries: int = 3,
        auto_start: bool = False,
        auto_exit: bool = False
    ) -> CrawlerHandler:
        """
        创建爬虫Handler
        
        Args:
            redis_url: Redis连接URL
            handler_id: Handler标识符
            input_queue: 输入队列名称
            output_queue: 输出队列名称
            crawler_type: 爬虫类型
            crawler_config: 爬虫配置
            batch_size: 批处理大小
            sleep_time: 休眠时间
            start_delay: 启动延迟时间
            max_retries: 最大重试次数
            auto_start: 是否自动启动
            auto_exit: 是否自动退出
        Returns:
            CrawlerHandler: 爬虫Handler实例
        """
        handler_id = handler_id or f"crawler-{len(cls._handlers)}"
        
        # 检查是否已存在相同ID的Handler
        if handler_id in cls._handlers:
            logger.warning(f"已存在ID为 {handler_id} 的Handler，返回现有实例")
            return cls._handlers[handler_id]
        
        # 创建新的Handler
        handler = CrawlerHandler(
            redis_url=redis_url,
            component_type="crawler",
            input_queue=input_queue,
            output_queue=output_queue,
            handler_id=handler_id,
            batch_size=batch_size,
            sleep_time=sleep_time,
            start_delay=start_delay,
            max_retries=max_retries,
            crawler_config=crawler_config,
            auto_exit=auto_exit
        )

        # 存储Handler实例
        cls._handlers[handler_id] = handler
        
        # 如果需要，自动启动Handler
        if auto_start:
            handler.start()
        
        return handler
    
    @classmethod
    def create_cleaner_handler(
        cls,
        redis_url: str,
        handler_id: str = None,
        input_queue: str = "crawler",
        output_queue: str = "cleaner",
        strategies: List = None,
        batch_size: int = 5,
        sleep_time: float = 0.1,
        max_retries: int = 3,
        auto_start: bool = False
    ) -> CleanerHandler:
        """
        创建清洗器Handler
        
        Args:
            redis_url: Redis连接URL
            handler_id: Handler标识符
            input_queue: 输入队列名称
            output_queue: 输出队列名称
            strategies: 清洗策略列表
            batch_size: 批处理大小
            sleep_time: 休眠时间
            max_retries: 最大重试次数
            auto_start: 是否自动启动
            
        Returns:
            CleanerHandler: 清洗器Handler实例
        """
        handler_id = handler_id or f"cleaner-{len(cls._handlers)}"
        
        # 检查是否已存在相同ID的Handler
        if handler_id in cls._handlers:
            logger.warning(f"已存在ID为 {handler_id} 的Handler，返回现有实例")
            return cls._handlers[handler_id]
        
        # 创建新的Handler
        handler = CleanerHandler(
            redis_url=redis_url,
            component_type="cleaner",
            input_queue=input_queue,
            output_queue=output_queue,
            handler_id=handler_id,
            batch_size=batch_size,
            sleep_time=sleep_time,
            max_retries=max_retries,
            strategies=strategies
        )
        
        # 存储Handler实例
        cls._handlers[handler_id] = handler
        
        # 如果需要，自动启动Handler
        if auto_start:
            handler.start()
        
        return handler
    
    @classmethod
    def create_storage_handler(
        cls,
        redis_url: str,
        handler_id: str = None,
        input_queue: str = "cleaner",
        output_queue: str = "storage",
        batch_size: int = 5,
        sleep_time: float = 0.1,
        max_retries: int = 3,
        auto_start: bool = False
    ) -> StorageHandler:
        """
        创建存储器Handler
        
        Args:
            redis_url: Redis连接URL
            handler_id: Handler标识符
            input_queue: 输入队列名称
            output_queue: 输出队列名称
            batch_size: 批处理大小
            sleep_time: 休眠时间
            max_retries: 最大重试次数
            auto_start: 是否自动启动
            
        Returns:
            StorageHandler: 存储器Handler实例
        """
        handler_id = handler_id or f"storage-{len(cls._handlers)}"
        
        # 检查是否已存在相同ID的Handler
        if handler_id in cls._handlers:
            logger.warning(f"已存在ID为 {handler_id} 的Handler，返回现有实例")
            return cls._handlers[handler_id]
        
        # 创建新的Handler
        handler = StorageHandler(
            redis_url=redis_url,
            component_type="storage",
            input_queue=input_queue,
            output_queue=output_queue,
            handler_id=handler_id,
            batch_size=batch_size,
            sleep_time=sleep_time,
            max_retries=max_retries
        )
        
        # 存储Handler实例
        cls._handlers[handler_id] = handler
        
        # 如果需要，自动启动Handler
        if auto_start:
            handler.start()
        
        return handler
    
    @classmethod
    def create_indexer_handler(
        cls,
        redis_url: str,
        milvus_uri: str,
        handler_id: str = None,
        input_queue: str = "storage",
        batch_size: int = 3,
        sleep_time: float = 0.2,
        max_retries: int = 3,
        auto_start: bool = False
    ) -> IndexerHandler:
        """
        创建索引器Handler
        
        Args:
            redis_url: Redis连接URL
            milvus_uri: Milvus连接URI
            handler_id: Handler标识符
            input_queue: 输入队列名称
            batch_size: 批处理大小
            sleep_time: 休眠时间
            max_retries: 最大重试次数
            auto_start: 是否自动启动
            
        Returns:
            IndexerHandler: 索引器Handler实例
        """
        handler_id = handler_id or f"indexer-{len(cls._handlers)}"
        
        # 检查是否已存在相同ID的Handler
        if handler_id in cls._handlers:
            logger.warning(f"已存在ID为 {handler_id} 的Handler，返回现有实例")
            return cls._handlers[handler_id]
        
        # 创建新的Handler
        handler = IndexerHandler(
            redis_url=redis_url,
            milvus_uri=milvus_uri,
            component_type="indexer",
            input_queue=input_queue,
            handler_id=handler_id,
            batch_size=batch_size,
            sleep_time=sleep_time,
            max_retries=max_retries
        )
        
        # 存储Handler实例
        cls._handlers[handler_id] = handler
        
        # 如果需要，自动启动Handler
        if auto_start:
            handler.start()
        
        return handler
    
    @classmethod
    def create_refresh_handler(
        cls,
        redis_url: str,
        handler_id: str = None,
        input_queue: str = "refresh",
        batch_size: int = 1,
        sleep_time: float = 1.0,
        max_retries: int = 3,
        auto_start: bool = False
    ) -> "RefreshHandler":
        """
        创建刷新器Handler
        
        Args:
            redis_url: Redis连接URL
            handler_id: Handler标识符
            input_queue: 输入队列名称
            batch_size: 批处理大小
            sleep_time: 休眠时间
            max_retries: 最大重试次数
            auto_start: 是否自动启动
            
        Returns:
            RefreshHandler: 刷新器Handler实例
        """
        handler_id = handler_id or f"refresh-{len(cls._handlers)}"
        
        if handler_id in cls._handlers:
            logger.warning(f"已存在ID为 {handler_id} 的Handler，返回现有实例")
            return cls._handlers[handler_id]
        
        handler = RefreshHandler(
            redis_url=redis_url,
            handler_id=handler_id,
            input_queue=input_queue,
            batch_size=batch_size,
            sleep_time=sleep_time,
            max_retries=max_retries,
        )
        
        cls._handlers[handler_id] = handler
        
        if auto_start:
            handler.start()
            
        return handler
    
    @classmethod
    def create_complete_pipeline(
        cls,
        redis_url: str,
        milvus_uri: str,
        prefix: str = "",
        auto_start: bool = True
    ) -> Dict[str, BaseHandler]:
        """
        创建完整的处理流水线，包括爬虫、清洗器、存储器和索引器
        
        Args:
            redis_url: Redis连接URL
            milvus_uri: Milvus连接URI
            prefix: Handler ID前缀
            auto_start: 是否自动启动所有Handler
            
        Returns:
            Dict[str, BaseHandler]: 处理流水线中的所有Handler
        """
        prefix = f"{prefix}-" if prefix else ""
        
        # 创建所有Handler
        crawler = cls.create_crawler_handler(
            redis_url=redis_url,
            handler_id=f"{prefix}crawler",
            auto_start=auto_start
        )
        
        cleaner = cls.create_cleaner_handler(
            redis_url=redis_url,
            handler_id=f"{prefix}cleaner",
            auto_start=auto_start
        )
        
        storage = cls.create_storage_handler(
            redis_url=redis_url,
            handler_id=f"{prefix}storage",
            auto_start=auto_start
        )
        
        indexer = cls.create_indexer_handler(
            redis_url=redis_url,
            milvus_uri=milvus_uri,
            handler_id=f"{prefix}indexer",
            auto_start=auto_start
        )
        
        # 返回所有Handler
        return {
            "crawler": crawler,
            "cleaner": cleaner,
            "storage": storage,
            "indexer": indexer
        }
    
    @classmethod
    def get_handler(cls, handler_id: str) -> Optional[BaseHandler]:
        """
        获取指定ID的Handler
        
        Args:
            handler_id: Handler ID
            
        Returns:
            Optional[BaseHandler]: Handler实例，如果不存在则返回None
        """
        return cls._handlers.get(handler_id)
    
    @classmethod
    def get_all_handlers(cls) -> Dict[str, BaseHandler]:
        """
        获取所有Handler
        
        Returns:
            Dict[str, BaseHandler]: 所有Handler
        """
        return cls._handlers.copy()
    
    @classmethod
    def stop_all_handlers(cls) -> None:
        """停止所有Handler"""
        for handler in cls._handlers.values():
            handler.stop()
    
    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """
        获取所有Handler的统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            handler_id: handler.get_stats()
            for handler_id, handler in cls._handlers.items()
        } 