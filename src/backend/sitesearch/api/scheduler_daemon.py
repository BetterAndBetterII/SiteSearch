import threading
import time
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

class PolicyCheckDaemon(threading.Thread):
    """
    守护线程，定期轮询/api/check-policy-execution接口
    """
    def __init__(self, interval=None):
        """
        初始化守护线程
        
        Args:
            interval: 轮询间隔，单位为秒，默认从settings中获取
        """
        super().__init__(daemon=True)
        # 如果未指定间隔，则从设置中获取
        self.interval = interval or getattr(settings, 'POLICY_CHECK_INTERVAL', 60)
        self.running = False
        self.api_url = None

    def setup(self):
        """设置API URL并处理环境配置"""
        # 从Django设置中获取主机和端口
        host = getattr(settings, 'API_HOST', 'localhost')
        port = getattr(settings, 'API_PORT', '8000')
        self.api_url = f"http://{host}:{port}/api/check-policy-execution/"
        logger.info(f"策略执行检查守护进程已初始化，将轮询: {self.api_url}")

    def stop(self):
        """停止守护线程"""
        self.running = False
        logger.info("策略执行检查守护进程已停止")

    def run(self):
        """运行守护线程，定期轮询接口"""
        self.setup()
        self.running = True
        logger.info(f"策略执行检查守护进程已启动，轮询间隔: {self.interval}秒")
        time.sleep(10)
        while self.running:
            try:
                # 调用接口
                response = requests.get(self.api_url, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"策略执行检查完成: {result}")
                else:
                    logger.error(f"策略执行检查请求失败，状态码: {response.status_code}")
            except Exception as e:
                logger.exception(f"轮询过程中发生错误: {str(e)}")
                
            # 等待下一次轮询
            time.sleep(self.interval)


# 创建守护进程实例
policy_check_daemon = PolicyCheckDaemon()

def start_policy_check_daemon(interval=None):
    """
    启动策略检查守护进程
    
    Args:
        interval: 轮询间隔，单位为秒，默认从settings中获取
    """
    global policy_check_daemon
    
    # 确保只启动一次
    if not policy_check_daemon.is_alive():
        policy_check_daemon = PolicyCheckDaemon(interval=interval)
        policy_check_daemon.start()
        return True
    return False 