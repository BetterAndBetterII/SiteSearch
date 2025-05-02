from django.apps import AppConfig
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'src.backend.sitesearch.api'
    label = 'sitesearch_api'
    
    def ready(self):
        """
        当Django应用程序准备好后，此方法被调用。
        在这里启动策略检查守护进程。
        """
        # 避免在Django自动重载时重复启动进程
        import os
        if os.environ.get('RUN_MAIN') != 'true':
            try:
                # 导入并启动守护进程
                from src.backend.sitesearch.api.scheduler_daemon import start_policy_check_daemon
                
                # 从配置中获取轮询间隔
                interval = getattr(settings, 'POLICY_CHECK_INTERVAL', 60)
                start_policy_check_daemon(interval)
                logger.info(f"策略检查守护进程已在应用启动时启动，轮询间隔: {interval}秒")
            except Exception as e:
                logger.exception(f"启动策略检查守护进程时出错: {str(e)}") 