#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
爬虫系统示例脚本
演示如何使用爬虫管理器和HTTPX爬虫
"""

import os
import sys
import time
import logging
import argparse
from typing import Dict, Any

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.backend.sitesearch.crawler.crawler_manager import CrawlerManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('crawler_demo.log')
    ]
)

logger = logging.getLogger('crawler_demo')

def process_page(page_data: Dict[str, Any]):
    """
    处理爬取到的页面数据
    
    Args:
        page_data: 爬取到的页面数据
    """
    logger.info(f"处理页面: {page_data.get('url')}")
    logger.info(f"页面标题: {page_data.get('title')}")
    logger.info(f"页面内容长度: {len(page_data.get('content', ''))}")
    logger.info(f"链接数量: {len(page_data.get('links', []))}")
    logger.info("-" * 50)

def run_crawler(url: str, crawler_id: str, max_pages: int = 10, max_depth: int = 2, 
                delay: float = 0.5, timeout: float = 30, wait: bool = True):
    """
    运行爬虫示例
    
    Args:
        url: 要爬取的网站URL
        crawler_id: 爬虫ID
        max_pages: 最大爬取页面数
        max_depth: 最大爬取深度
        delay: 请求延迟(秒)
        timeout: 请求超时(秒)
        wait: 是否等待爬虫完成
    """
    # 创建爬虫管理器
    manager = CrawlerManager(storage_dir="./crawl_results")
    
    try:
        # 配置爬虫
        config = {
            "max_pages": max_pages,
            "max_depth": max_depth,
            "delay": delay,
            "timeout": timeout,
            "headers": {
                "User-Agent": "SiteSearch-Crawler/1.0"
            },
            "follow_external_links": False,  # 不跟随外部链接
            "respect_robots_txt": True,      # 尊重robots.txt
        }
        
        # 创建爬虫
        manager.create_crawler(
            crawler_id=crawler_id,
            crawler_type="httpx",
            base_url=url,
            config=config,
            callback=process_page
        )
        
        logger.info(f"开始爬取 {url}")
        
        # 启动爬虫
        manager.start_crawler(crawler_id, discover_sitemap=True)
        
        # 如果需要等待爬虫完成
        if wait:
            logger.info("等待爬虫完成...")
            while True:
                status = manager.get_crawler_status(crawler_id)
                logger.info(f"状态: {status['status']}, "
                           f"已爬取: {status['stats'].get('pages_crawled', 0)}, "
                           f"失败: {status['stats'].get('pages_failed', 0)}")
                
                if status["status"] not in ["running", "created"]:
                    break
                    
                time.sleep(2)
            
            # 爬取完成后的处理
            logger.info("爬取完成，保存结果...")
            
            # 保存结果
            result_file = manager.save_results(crawler_id)
            logger.info(f"结果已保存到: {result_file}")
        else:
            logger.info("爬虫已在后台启动，您可以稍后检查结果")
            
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止爬虫...")
        manager.stop_crawler(crawler_id)
        
    except Exception as e:
        logger.error(f"爬取过程中发生错误: {str(e)}")
        
    finally:
        # 关闭管理器
        manager.close()
        logger.info("爬虫演示结束")

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="网站爬虫演示")
    parser.add_argument("url", help="要爬取的网站URL")
    parser.add_argument("--id", dest="crawler_id", default="demo_crawler", help="爬虫ID")
    parser.add_argument("--max-pages", dest="max_pages", type=int, default=10, help="最大爬取页面数")
    parser.add_argument("--max-depth", dest="max_depth", type=int, default=2, help="最大爬取深度")
    parser.add_argument("--delay", type=float, default=0.5, help="请求延迟(秒)")
    parser.add_argument("--timeout", type=float, default=30, help="请求超时(秒)")
    parser.add_argument("--no-wait", dest="wait", action="store_false", help="不等待爬虫完成")
    
    args = parser.parse_args()
    
    # 运行爬虫
    run_crawler(
        url=args.url,
        crawler_id=args.crawler_id,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        delay=args.delay,
        timeout=args.timeout,
        wait=args.wait
    )

if __name__ == "__main__":
    main() 