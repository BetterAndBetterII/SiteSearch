import os
import sys
import time
import json
import logging
import signal
import argparse
from typing import Dict, Any

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..'))

# 导入Handler模块
from src.backend.sitesearch.handler import HandlerFactory

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("handler_example")

# 创建信号处理函数
def signal_handler(sig, frame):
    """处理CTRL+C信号，优雅地关闭所有Handler"""
    logger.info("接收到停止信号，正在关闭所有Handler...")
    HandlerFactory.stop_all_handlers()
    logger.info("所有Handler已停止，退出程序")
    sys.exit(0)

def add_url_to_queue(redis_url: str, url: str, site_id: str = "default"):
    """添加URL到爬取队列"""
    import redis
    redis_client = redis.from_url(redis_url)
    
    # 准备爬取任务
    task = {
        "url": url,
        "site_id": site_id,
        "timestamp": time.time(),
        "task_id": f"task-{int(time.time())}"
    }
    
    # 将任务添加到爬取队列
    redis_client.lpush("sitesearch:queue:url", json.dumps(task))
    logger.info(f"已将URL添加到爬取队列: {url}")

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='SiteSearch Handler示例')
    parser.add_argument('--redis', type=str, default="redis://localhost:6382/0", help='Redis连接URL')
    parser.add_argument('--milvus', type=str, default="http://localhost:19535", help='Milvus连接URL')
    parser.add_argument('--url', type=str, help='要爬取的URL')
    parser.add_argument('--site', type=str, default="default", help='站点ID')
    parser.add_argument('--handlers', type=str, default="all", help='要启动的Handler类型 (crawler,cleaner,storage,indexer 或 all)')
    args = parser.parse_args()
    
    # 注册信号处理函数
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 确定要启动的Handler类型
    handlers_to_start = args.handlers.lower().split(',')
    if 'all' in handlers_to_start:
        handlers_to_start = ['crawler', 'cleaner', 'storage', 'indexer']
    
    # 创建并启动Handler
    active_handlers = {}
    
    if 'crawler' in handlers_to_start:
        crawler = HandlerFactory.create_crawler_handler(
            redis_url=args.redis,
            handler_id="example-crawler",
            auto_start=True
        )
        active_handlers['crawler'] = crawler
        logger.info("爬虫Handler已启动")
    
    if 'cleaner' in handlers_to_start:
        cleaner = HandlerFactory.create_cleaner_handler(
            redis_url=args.redis,
            handler_id="example-cleaner",
            auto_start=True
        )
        active_handlers['cleaner'] = cleaner
        logger.info("清洗器Handler已启动")
    
    if 'storage' in handlers_to_start:
        storage = HandlerFactory.create_storage_handler(
            redis_url=args.redis,
            handler_id="example-storage",
            auto_start=True
        )
        active_handlers['storage'] = storage
        logger.info("存储器Handler已启动")
    
    if 'indexer' in handlers_to_start:
        indexer = HandlerFactory.create_indexer_handler(
            redis_url=args.redis,
            milvus_uri=args.milvus,
            handler_id="example-indexer",
            auto_start=True
        )
        active_handlers['indexer'] = indexer
        logger.info("索引器Handler已启动")
    
    # 如果提供了URL，添加到爬取队列
    if args.url:
        add_url_to_queue(args.redis, args.url, args.site)
    
    logger.info("所有Handler已启动，按Ctrl+C停止")
    
    # 监控Handler状态
    try:
        while True:
            # 每10秒打印一次Handler状态
            time.sleep(10)
            
            # 获取每个Handler的状态
            for handler_type, handler in active_handlers.items():
                stats = handler.get_stats()
                
                logger.info(f"{handler_type.capitalize()} Handler状态: ")
                logger.info(f"  状态: {stats['status']}")
                logger.info(f"  队列: 待处理={stats['queues']['pending']}, "
                            f"处理中={stats['queues']['processing']}, "
                            f"已完成={stats['queues']['completed']}, "
                            f"失败={stats['queues']['failed']}")
                logger.info(f"  处理统计: 总任务={stats['stats']['tasks_processed']}, "
                            f"成功={stats['stats']['tasks_succeeded']}, "
                            f"失败={stats['stats']['tasks_failed']}")
                
    except KeyboardInterrupt:
        logger.info("接收到用户中断，正在关闭...")
        HandlerFactory.stop_all_handlers()
        logger.info("所有Handler已停止")

if __name__ == "__main__":
    main() 