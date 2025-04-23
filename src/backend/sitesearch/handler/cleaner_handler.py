import logging
from typing import Dict, Any, List, Optional
import json

from src.backend.sitesearch.handler.base_handler import BaseHandler, SkipError
from src.backend.sitesearch.cleaner import DataCleaner

class CleanerHandler(BaseHandler):
    """清洗器Handler，用于从队列获取爬虫数据并进行清洗"""
    
    def __init__(self, 
                 redis_url: str,
                 input_queue: str = "crawl",
                 output_queue: str = "clean",
                 handler_id: str = None,
                 batch_size: int = 5,
                 sleep_time: float = 0.1,
                 max_retries: int = 3,
                 strategies: List = None):
        """
        初始化清洗器Handler
        
        Args:
            redis_url: Redis连接URL
            input_queue: 输入队列名称，默认为"crawl"
            output_queue: 输出队列名称，默认为"clean"
            handler_id: Handler标识符
            batch_size: 批处理大小
            sleep_time: 队列为空时的睡眠时间（秒）
            max_retries: 最大重试次数
            strategies: 清洗策略列表
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
        
        # 初始化清洗器
        self.cleaner = DataCleaner(strategies=strategies)
        self.logger = logging.getLogger(f"CleanerHandler:{self.handler_id}")
        self.logger.setLevel(logging.WARNING)
    
    async def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理清洗任务
        
        Args:
            task_data: 包含爬取结果的任务数据
            
        Returns:
            Dict[str, Any]: 清洗后的数据
        """
        self.logger.info(f"开始清洗网页: {task_data.get('url', '未知URL')}")
        
        # 验证任务数据
        if 'status' in task_data and task_data['status'] == 'skipped':
            self.logger.info(f"跳过清洗: {task_data.get('url', '未知URL')}")
            raise SkipError(f"跳过清洗: {task_data.get('url', '未知URL')}")
        if 'status' in task_data and task_data['status'] == 'error':
            self.logger.info(f"跳过爬取失败的URL: {task_data.get('url', '未知URL')}")
            raise SkipError(f"跳过爬取失败的URL: {task_data.get('url', '未知URL')}")
        if 'url' not in task_data or 'content' not in task_data:
            raise ValueError("任务数据缺少必要字段: url 或 content")
        
        # 准备清洗数据
        # 处理content，可能是文本或二进制数据
        content = task_data['content']
        
        # 如果content是二进制数据（以字节表示），转换成bytes对象
        if isinstance(content, str) and task_data.get('mimetype', '').startswith(('application/', 'image/')):
            import base64
            try:
                content = base64.b64decode(content)
            except Exception as e:
                self.logger.warning(f"无法将content解码为二进制数据: {str(e)}")
        
        # 执行清洗
        clean_content = self.cleaner.clean(task_data['url'], task_data['mimetype'], content)
        
        # 将清洗结果添加到任务数据中
        result = task_data.copy()
        result['clean_content'] = clean_content
        
        self.logger.info(f"网页清洗完成: {task_data.get('url', '未知URL')}")
        return result 