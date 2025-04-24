import logging
from typing import Dict, Any, Optional

from src.backend.sitesearch.handler.base_handler import BaseHandler, SkipError
from src.backend.sitesearch.storage.manager import DataStorage
from asgiref.sync import sync_to_async

class StorageHandler(BaseHandler):
    """存储器Handler，用于从队列获取清洗后的数据并存储到数据库"""
    
    def __init__(self, 
                 redis_url: str,
                 component_type: str,
                 input_queue: str = "cleaner",
                 output_queue: str = "storage",
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
            component_type=component_type,
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

        print(f"存储器初始化完成，监听队列：{self.input_queue}，输出队列：{self.output_queue}")
    
    async def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理存储任务
        
        Args:
            task_data: 包含清洗后的网页数据的任务数据
            
        Returns:
            Dict[str, Any]: 包含存储结果的数据
        """
        self.logger.info(f"开始存储数据: {task_data.get('url', '未知URL')}")
        try:
            # 验证任务数据
            if 'url' not in task_data or 'content' not in task_data:
                raise ValueError("任务数据缺少必要字段: url 或 content")
            
            # 确保站点ID字段存在
            site_id = task_data.get('site_id')
            if not site_id:
                self.logger.warning(f"任务数据缺少站点ID，无法确定文档归属: {task_data.get('url')}")
                # 可以设置一个默认站点，或者返回错误
                result = task_data.copy()
                result['index_operation'] = "skip"
                result['error'] = "任务数据缺少站点ID"
                return result
            
            # 首先检查文档是否在当前站点中存在
            # 这里传入site_id参数确保检查文档是否在特定站点中
            exists, existing_doc, operation = await sync_to_async(self.storage.check_exists)(
                url=task_data['url'], 
                site_id=site_id,
                content_hash=task_data.get('content_hash')
            )
            
            # 判断不同的操作类型
            if operation == "new":
                # 文档不存在，创建新文档
                self.logger.info(f"文档 {task_data['url']} 不存在，将创建新文档")
                try:
                    document, op = await sync_to_async(self.storage.save_document)(task_data)
                    result = task_data.copy()
                    result['document_id'] = document.id
                    result['index_operation'] = op
                    self.logger.info(f"新文档存储完成: {task_data.get('url')}")
                    return result
                except Exception as e:
                    self.logger.exception(f"创建新文档时发生错误: {str(e)}")
                    result = task_data.copy()
                    result['index_operation'] = "skip"
                    result['error'] = str(e)
                    return result
            
            elif operation == "new_site":
                # 文档已存在但不在当前站点中，添加到当前站点
                self.logger.info(f"文档 {task_data['url']} 已存在但不在站点 {site_id} 中，将添加到该站点")
                try:
                    document, op = await sync_to_async(self.storage.save_document)(task_data)
                    result = task_data.copy()
                    result['document_id'] = document.id
                    result['index_operation'] = op
                    self.logger.info(f"文档已添加到站点 {site_id}: {task_data.get('url')}")
                    return result
                except Exception as e:
                    self.logger.exception(f"将文档添加到站点时发生错误: {str(e)}")
                    result = task_data.copy()
                    result['index_operation'] = "skip"
                    result['error'] = str(e)
                    return result
            
            elif operation == "edit":
                # 文档在当前站点中存在，但内容已变化，需要更新
                self.logger.info(f"文档 {task_data['url']} 内容已变化，将更新")
                try:
                    document, op = await sync_to_async(self.storage.save_document)(task_data)
                    result = task_data.copy()
                    result['document_id'] = document.id
                    result['index_operation'] = op
                    self.logger.info(f"文档更新完成: {task_data.get('url')}")
                    return result
                except Exception as e:
                    self.logger.exception(f"更新文档时发生错误: {str(e)}")
                    result = task_data.copy()
                    result['index_operation'] = "skip"
                    result['error'] = str(e)
                    return result
            
            elif operation == "skip":
                # 文档在当前站点中存在且内容未变化，跳过处理
                self.logger.info(f"文档 {task_data['url']} 在站点 {site_id} 中已存在且内容未变化，跳过处理")
                result = task_data.copy()
                result['index_operation'] = "skip"
                if existing_doc:
                    result['document_id'] = existing_doc.id
                return result
            
            else:
                # 处理其他情况（如error）
                self.logger.warning(f"无法确定文档 {task_data['url']} 的操作类型: {operation}")
                result = task_data.copy()
                result['index_operation'] = "skip"
                result['error'] = f"无法确定操作类型: {operation}"
                return result 
        except SkipError as e:
            self.logger.info(f"存储跳过: {task_data.get('url', '未知URL')}, 原因: {str(e)}")
            raise e
        except Exception as e:
            self.logger.exception(f"处理存储任务时发生错误: {str(e)}")
            result = task_data.copy()
            result['index_operation'] = "skip"
            result['error'] = str(e)
            return result
