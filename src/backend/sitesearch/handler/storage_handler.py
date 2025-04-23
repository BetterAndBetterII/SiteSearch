import logging
from typing import Dict, Any, Optional

from src.backend.sitesearch.handler.base_handler import BaseHandler
from src.backend.sitesearch.storage.manager import DataStorage
from asgiref.sync import sync_to_async

class StorageHandler(BaseHandler):
    """存储器Handler，用于从队列获取清洗后的数据并存储到数据库"""
    
    def __init__(self, 
                 redis_url: str,
                 input_queue: str = "clean",
                 output_queue: str = "index",
                 handler_id: str = None,
                 batch_size: int = 5,
                 sleep_time: float = 0.1,
                 max_retries: int = 3):
        """
        初始化存储器Handler
        
        Args:
            redis_url: Redis连接URL
            input_queue: 输入队列名称，默认为"clean"
            output_queue: 输出队列名称，默认为"index"
            handler_id: Handler标识符
            batch_size: 批处理大小
            sleep_time: 队列为空时的睡眠时间（秒）
            max_retries: 最大重试次数
        """
        super().__init__(
            redis_url=redis_url,
            input_queue=input_queue,
            output_queue=output_queue,
            handler_id=handler_id,
            batch_size=batch_size,
            sleep_time=sleep_time,
            max_retries=max_retries
        )
        
        # 初始化存储器
        self.storage = DataStorage()
        self.logger = logging.getLogger(f"StorageHandler:{self.handler_id}")
        self.logger.setLevel(logging.WARNING)
    
    async def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理存储任务
        
        Args:
            task_data: 包含清洗后的网页数据的任务数据
            
        Returns:
            Dict[str, Any]: 包含存储结果的数据
        """
        self.logger.info(f"开始存储数据: {task_data.get('url', '未知URL')}")
        
        # 验证任务数据
        if 'url' not in task_data or 'content' not in task_data:
            raise ValueError("任务数据缺少必要字段: url 或 content")
        
        # 首先检查是否已存在相同的文档
        exists, existing_doc, operation = await sync_to_async(self.storage.check_exists)(
            url=task_data['url'], 
            content_hash=task_data.get('content_hash')
        )
        
        if operation == "skip":
            # 文档内容未变化，跳过存储
            self.logger.info(f"文档 {task_data['url']} 内容未变化，跳过存储")
            # 虽然跳过存储，但仍然需要传递给索引器以防索引状态变化
            result = task_data.copy()
            result['index_operation'] = "skip"
            if existing_doc:
                result['document_id'] = existing_doc.id
            return result
        
        # 存储文档，处理new或edit操作
        try:
            document, op = await sync_to_async(self.storage.save_document)(task_data)
            
            # 准备返回数据
            result = task_data.copy()
            result['document_id'] = document.id
            result['index_operation'] = op  # 'new' 或 'edit'
            
            self.logger.info(f"数据存储完成: {task_data.get('url', '未知URL')}, 操作类型: {op}")
            return result
            
        except Exception as e:
            self.logger.exception(f"存储数据时发生错误: {str(e)}")
            # 在发生错误时仍然返回结果，但标记操作为error
            result = task_data.copy()
            result['index_operation'] = "error"
            result['error'] = str(e)
            return result 