import time
import threading
import sys
import os
import django
from django.conf import settings
import dotenv
import argparse
import signal

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..'))

dotenv.load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', '.env'))

# 设置Django环境
def init_django():
    # 设置Django设置模块
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'src.backend.sitesearch.conf.settings')
    
    # 如果没有完整的Django项目，可以手动配置设置
    if not settings.configured:
        settings.configure(
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.postgresql',  # 或其他数据库引擎
                    'NAME': os.getenv('DB_NAME'),
                    'USER': os.getenv('DB_USER'),
                    'PASSWORD': os.getenv('DB_PASSWORD'),
                    'HOST': os.getenv('DB_HOST'),
                    'PORT': os.getenv('DB_PORT'),
                }
            },
            INSTALLED_APPS=[
                'src.backend.sitesearch.storage',  # 包含models.py的应用
            ],
        )
    
    # 初始化Django
    django.setup()

# 信号处理函数
def signal_handler(sig, frame):
    print("\n接收到停止信号，正在关闭系统...")
    if 'manager' in globals():
        manager.cleanup()
    print("系统已安全关闭")
    sys.exit(0)

def main():
    redis_url = os.getenv("REDIS_URL")
    milvus_url = os.getenv("MILVUS_URI")
    site_id = "cuhksz"
    base_url = "https://www.cuhk.edu.cn"
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 创建管理器实例
    global manager
    manager = SiteSearchManager(redis_url, milvus_url)
    
    try:
        # 初始化各个组件
        crawler_config = {
            "base_url": base_url,
            "verify_ssl": False,
            "max_urls": 100,
            "max_depth": 3,
            # 包含cuhk.edu.cn的链接：itso.cuhk.edu.cn
            "regpattern": r"https://(.*\.cuhk\.edu\.cn).*"
        }
        
        # 初始化组件
        manager.initialize_components(
            crawler_config=crawler_config
        )
        
        # 如果提供了URL，添加到爬取队列
        if base_url:
            manager.add_url_to_queue(base_url, site_id)
            print(f"已将URL添加到爬取队列: {base_url}")
        
        # 启动监控（在单独的线程中）
        manager.start_monitoring()
        
        # 启动所有组件
        if manager.start_all_components():
            print("所有组件启动成功")
        else:
            print("部分组件启动失败")
            
        # 模拟系统运行一段时间
        try:
            while True:
                # 每10秒打印一次系统状态
                status = manager.get_system_status()
                print("\n系统状态:")
                print("组件状态:", status["components"])
                print("队列状态:")
                for queue_name, queue_stats in status["queues"].items():
                    print(f"  {queue_name}:")
                    print(f"    待处理任务: {queue_stats['pending']}")
                    print(f"    处理中任务: {queue_stats['processing']}")
                    print(f"    已完成任务: {queue_stats['completed']}")
                    print(f"    失败任务: {queue_stats['failed']}")
                    print(f"    平均处理时间: {queue_stats['avg_processing_time']:.2f}秒")
                    print(f"    最后活动时间: {queue_stats['last_activity']}")
                
                time.sleep(10)
                
        except KeyboardInterrupt:
            print("\n接收到停止信号，正在关闭系统...")
            
    finally:
        # 清理资源
        manager.cleanup()
        print("系统已安全关闭")

if __name__ == "__main__":
    init_django()
    
    from src.backend.sitesearch.pipeline_manager import SiteSearchManager

    main() 