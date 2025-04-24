import logging
import asyncio
from typing import Dict, Any, Optional, List

from src.backend.sitesearch.handler.base_handler import BaseHandler
from src.backend.sitesearch.indexer.index_manager import IndexerFactory, DataIndexer
from src.backend.sitesearch.storage.manager import DataStorage
from asgiref.sync import sync_to_async

class IndexerHandler(BaseHandler):
    """索引器Handler，用于从队列获取存储后的数据并建立索引"""
    
    def __init__(self, 
                 redis_url: str,
                 milvus_uri: str,
                 component_type: str,
                 input_queue: str = "storage",
                 handler_id: str = None,
                 batch_size: int = 20,
                 sleep_time: float = 0.1,
                 max_retries: int = 3):
        """
        初始化索引器Handler
        
        Args:
            redis_url: Redis连接URL
            milvus_uri: Milvus连接URI
            input_queue: 输入队列名称，默认为"index"
            handler_id: Handler标识符
            batch_size: 批处理大小
            sleep_time: 队列为空时的睡眠时间（秒）
            max_retries: 最大重试次数
        """
        super().__init__(
            redis_url=redis_url,
            component_type=component_type,
            input_queue=input_queue,
            output_queue=None,  # 索引是最后一步，不需要输出队列
            handler_id=handler_id,
            batch_size=batch_size,
            sleep_time=sleep_time,
            max_retries=max_retries
        )
        
        # 存储服务与站点索引管理器映射
        self.indexers = {}
        self.milvus_uri = milvus_uri
        self.storage = DataStorage()
        self.logger = logging.getLogger(f"IndexerHandler:{self.handler_id}")
        self.logger.setLevel(logging.WARNING)

        print(f"索引器初始化完成，监听队列：{self.input_queue}")
    
    def get_indexer(self, site_id: str):
        """获取指定站点的索引器实例"""
        if site_id not in self.indexers:
            self.indexers[site_id] = IndexerFactory.get_instance(
                site_id=site_id,
                redis_uri=self.redis_url,
                milvus_uri=self.milvus_uri
            )
        return self.indexers[site_id]
    
    async def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理索引任务
        
        Args:
            task_data: 包含存储结果的任务数据
            
        Returns:
            Dict[str, Any]: 包含索引结果的数据
        """
        self.logger.info(f"开始索引文档: {task_data.get('url', '未知URL')}")

        # 验证任务数据
        if 'url' not in task_data or 'document_id' not in task_data:
            raise ValueError("任务数据缺少必要字段: url 或 document_id")
        
        # 获取站点ID，如果没有则使用默认值
        site_id = task_data.get('site_id', 'default')
        document_id = task_data.get('document_id')
        
        # 获取索引操作类型
        index_operation = task_data.get('index_operation', 'new')
        
        # 获取对应的索引管理器
        indexer: DataIndexer = self.get_indexer(site_id)
        
        try:
            if index_operation == "new" or index_operation == "edit" or index_operation == "skip":
                # 添加或更新索引
                result = await indexer.add_documents([task_data])
                # 标记文档为已索引
                if document_id:
                    await sync_to_async(self.storage.mark_indexed)(document_id)
                    
                self.logger.info(f"文档索引完成: {task_data.get('url', '未知URL')}, 操作: {index_operation}")
                return {"success": True, "document_ids": result}
                
            elif index_operation == "delete":
                # 删除索引
                doc_id = f"{site_id}:{task_data.get('content_hash', '')}"
                await indexer.remove_documents([doc_id])
                self.logger.info(f"文档索引已删除: {task_data.get('url', '未知URL')}")
                return {"success": True, "operation": "delete"}
                
            else:
                raise ValueError(f"未知的索引操作类型: {index_operation}")
                
        except Exception as e:
            self.logger.error(f"索引文档时发生错误: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "url": task_data.get('url'),
                "document_id": document_id
            } 