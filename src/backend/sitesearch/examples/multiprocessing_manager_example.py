import time
import threading
import sys
import os
import django
from django.conf import settings
import signal
import argparse
import json
import multiprocessing
from multiprocessing import Process, Queue
from typing import Dict, Any, List
from src.backend.sitesearch.pipeline_manager import MultiProcessSiteSearchManager

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..'))

# 加载环境变量
import dotenv
dotenv.load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', '.env'), override=True)

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

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='多进程站点搜索管理器')
    parser.add_argument('--crawler-workers', type=int, default=8, help='爬虫worker数量')
    parser.add_argument('--cleaner-workers', type=int, default=2, help='清洗器worker数量')
    parser.add_argument('--storage-workers', type=int, default=2, help='存储器worker数量')
    parser.add_argument('--indexer-workers', type=int, default=8, help='索引器worker数量')
    
    parser.add_argument('--site-id', type=str, default='cuhksz', help='站点ID')
    parser.add_argument('--base-url', type=str, default='https://www.cuhk.edu.cn', help='起始URL')
    parser.add_argument('--max-urls', type=int, default=1000, help='最大爬取URL数量')
    parser.add_argument('--max-depth', type=int, default=3, help='最大爬取深度')
    
    return parser.parse_args()

def main():
    """主函数"""
    # 解析命令行参数
    args = parse_arguments()
    
    # 使用环境变量或命令行参数
    redis_url = os.getenv("REDIS_URL")
    milvus_uri = os.getenv("MILVUS_URI")

    site_id = args.site_id
    base_url = args.base_url
    
    # 检查Redis URL
    if not redis_url:
        print("未提供Redis URL，请在环境变量或命令行参数中指定")
        return
    
    # 注册信号处理器
    def signal_handler(sig, frame):
        print("\n接收到停止信号，正在关闭系统...")
        if 'manager' in globals():
            manager.shutdown()
        print("系统已安全关闭")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 创建管理器实例
    global manager
    
    manager = MultiProcessSiteSearchManager(redis_url, milvus_uri)
    
    try:
        # 初始化组件配置
        crawler_config = {
            "base_url": base_url,
            "verify_ssl": False,
            "max_urls": args.max_urls,
            "max_depth": args.max_depth,
            # 包含cuhk.edu.cn的链接：itso.cuhk.edu.cn
            "regpattern": r"https://(.*\.cuhk\.edu\.cn).*"
        }
        
        # 初始化组件
        manager.initialize_components(
            crawler_config=crawler_config
        )
        
        # 启动worker进程
        manager.start_workers(
            crawler_workers=args.crawler_workers,
            cleaner_workers=args.cleaner_workers,
            storage_workers=args.storage_workers,
            indexer_workers=args.indexer_workers
        )
        
        # 如果提供了URL，添加到爬取队列
        if base_url:
            manager.add_url_to_queue(base_url, site_id)
            print(f"已将URL添加到爬取队列: {base_url}")
        
        # 启动监控
        manager.start_monitoring()
        
        # 保持主进程运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n接收到停止信号，正在关闭系统...")
            
    finally:
        # 清理资源
        manager.shutdown()
        print("系统已安全关闭")

if __name__ == "__main__":
    # 多进程支持
    multiprocessing.set_start_method('spawn', force=True)
    
    # 初始化Django
    init_django()
    
    # 运行主函数
    main() 