import logging
import asyncio
from typing import Dict, Any
from asgiref.sync import sync_to_async
import json

from src.backend.sitesearch.handler.base_handler import BaseHandler

from django.utils import timezone
import datetime

logger = logging.getLogger(__name__)

class RefreshDB:
    def __init__(self):
        self.site = None
        self.manager = None

    def get_site(self, site_id):
        from src.backend.sitesearch.api.models import Site
        return Site.objects.get(id=site_id)

    def get_documents_batch(self, site_id, limit, offset):
        from src.backend.sitesearch.storage.utils import get_documents_by_site
        return list(get_documents_by_site(site_id, limit=limit, offset=offset))

    def update_policy(self, site_id):
        from src.backend.sitesearch.api.models import RefreshPolicy
        try:
            policy = RefreshPolicy.objects.get(site_id=site_id)
            policy.last_refresh = timezone.now()
            if policy.enabled:
                policy.next_refresh = policy.last_refresh + datetime.timedelta(days=policy.refresh_interval_days)
            policy.save()
        except RefreshPolicy.DoesNotExist:
            pass


async def perform_site_refresh(db: RefreshDB, redis_client, site_id, crawl_task_id, strategy, url_patterns, exclude_patterns, max_age_days, priority_patterns):
    """
    执行刷新任务的实际逻辑（异步版本）。
    这个函数由一个独立的后台worker来调用，而不是在Web进程的线程中运行。
    """
    try:
        site = await sync_to_async(db.get_site)(site_id)
        
        # 爬取任务已经由API创建，我们只需要向其队列中添加URL
        crawl_task_queue = f"sitesearch:queue:sitesearch:task:{crawl_task_id}:queue"

        # 为了避免一次性加载所有URL到内存，我们分批处理
        batch_size = 200
        offset = 0
        while True:
            documents_batch = await sync_to_async(db.get_documents_batch)(site_id, limit=batch_size, offset=offset)
            if not documents_batch:
                break
            
            # 准备要推送到队列的任务列表
            tasks_to_queue = []
            for doc in documents_batch:
                task = {
                    "url": doc.url,
                    "site_id": site_id,
                    "timestamp": timezone.now().timestamp(),
                    "task_id": crawl_task_id
                }
                tasks_to_queue.append(json.dumps(task))
            
            # 将批处理的URL添加到任务队列
            if tasks_to_queue:
                # 使用 pipeline 提高效率
                pipeline = redis_client.pipeline()
                pipeline.lpush(crawl_task_queue, *tasks_to_queue)
                await sync_to_async(pipeline.execute)()
            
            # 如果获取到的批次小于指定的批次大小，说明是最后一批
            if len(documents_batch) < batch_size:
                break
                
            offset += len(documents_batch)
        
        # 如果存在刷新策略，更新最后刷新时间和下次刷新时间
        await sync_to_async(db.update_policy)(site_id)

        print(f"站点 {site_id} 的后台刷新任务已完成，URL已添加到爬取任务 {crawl_task_id} 的队列")

    except Exception as e:
        # 在生产环境中，应该使用更健壮的日志记录
        logger.exception(f"后台刷新任务失败，站点ID: {site_id}, 错误: {e}") 


class RefreshHandler(BaseHandler):
    """
    刷新器Handler，用于从刷新队列获取任务并执行站点内容刷新。
    """

    def __init__(self, 
                 redis_url: str,
                 component_type: str = "refresh",
                 input_queue: str = "sitesearch:queue:refresh",
                 handler_id: str = None,
                 batch_size: int = 1,
                 sleep_time: float = 1.0,
                 max_retries: int = 3):
        """
        初始化刷新器Handler
        
        Args:
            redis_url: Redis连接URL
            component_type: 组件类型
            input_queue: 输入队列名称，默认为"sitesearch:queue:refresh"
            handler_id: Handler标识符
            batch_size: 批处理大小
            sleep_time: 队列为空时的睡眠时间（秒）
            max_retries: 最大重试次数
        """
        # 注意：这里的 input_queue 需要去除 'sitesearch:queue:' 前缀
        # 因为 BaseHandler 会自动添加它
        if input_queue.startswith("sitesearch:queue:"):
            input_queue = input_queue.replace("sitesearch:queue:", "")

        super().__init__(
            redis_url=redis_url,
            component_type=component_type,
            input_queue=input_queue,
            output_queue=None, # 刷新任务没有输出队列
            handler_id=handler_id,
            batch_size=batch_size,
            sleep_time=sleep_time,
            max_retries=max_retries
        )
        self.logger = logging.getLogger(f"RefreshHandler:{self.handler_id}")
        self.logger.setLevel(logging.INFO)
        self.db = RefreshDB()

        print(f"刷新器初始化完成，监听队列：{self.input_queue}")

    async def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理刷新任务
        
        Args:
            task_data: 包含刷新策略参数的任务数据
            
        Returns:
            一个空字典，因为这是流水线的终点。
        """
        site_id = task_data.get('site_id')
        self.logger.info(f"开始处理站点 {site_id} 的刷新任务。")

        try:
            # 验证任务数据
            if not site_id:
                raise ValueError("任务数据缺少 'site_id'")
            
            crawl_task_id = task_data.get('crawl_task_id')
            if not crawl_task_id:
                raise ValueError("任务数据缺少 'crawl_task_id'")

            # 提取任务参数
            strategy = task_data.get('strategy')
            url_patterns = task_data.get('url_patterns', [])
            exclude_patterns = task_data.get('exclude_patterns', [])
            max_age_days = task_data.get('max_age_days')
            priority_patterns = task_data.get('priority_patterns', [])

            await perform_site_refresh(
                self.db, self.redis_client, site_id, crawl_task_id, strategy, url_patterns, exclude_patterns, max_age_days, priority_patterns
            )

            self.logger.info(f"站点 {site_id} 的刷新任务已成功派发。")
            return {}  # 没有输出到下一个队列

        except Exception as e:
            self.logger.exception(f"处理站点 {site_id} 的刷新任务失败: {str(e)}")
            raise e 