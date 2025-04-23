#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Firecrawl爬虫示例脚本
演示如何使用Firecrawl爬虫
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
        logging.FileHandler('firecrawl_demo.log')
    ]
)

logger = logging.getLogger('firecrawl_demo')

def process_page(url: str, content: str, metadata: Dict[str, Any]):
    """
    处理爬取到的页面数据
    
    Args:
        url: 页面URL
        content: 页面内容
        metadata: 页面元数据
    """
    logger.info(f"处理页面: {url}")
    logger.info(f"页面标题: {metadata.get('title', '无标题')}")
    logger.info(f"页面内容长度: {len(content)}")
    logger.info(f"链接数量: {len(metadata.get('related_links', []))}")
    logger.info("-" * 50)

def run_crawler(url: str, crawler_id: str, api_key: str = None, 
                max_pages: int = 10, max_depth: int = 2, 
                formats: list = None, wait: bool = True):
    """
    运行Firecrawl爬虫示例
    
    Args:
        url: 要爬取的网站URL
        crawler_id: 爬虫ID
        api_key: Firecrawl API密钥，如不提供则从环境变量获取
        max_pages: 最大爬取页面数
        max_depth: 最大爬取深度
        formats: 输出格式列表，默认为["markdown"]
        wait: 是否等待爬虫完成
    """
    # 检查API密钥
    if not api_key and "FIRECRAWL_API_KEY" not in os.environ:
        logger.error("必须提供Firecrawl API密钥，通过--api-key参数或FIRECRAWL_API_KEY环境变量")
        sys.exit(1)
    
    # 创建爬虫管理器
    manager = CrawlerManager(storage_dir="./firecrawl_results")
    formats = formats or ["markdown"]
    
    try:
        # 配置爬虫
        config = {
            "api_key": api_key,
            "max_urls": max_pages,
            "max_depth": max_depth,
            "formats": formats,
            "headers": {
                "User-Agent": "SiteSearch-Crawler/1.0"
            },
            "request_delay": 1.0,  # 为了避免速率限制，设置1秒延迟
        }
        
        # 创建爬虫
        manager.create_crawler(
            crawler_id=crawler_id,
            crawler_type="firecrawl",
            base_url=url,
            config=config,
            callback=process_page
        )
        
        logger.info(f"开始爬取 {url}")
        
        # 启动爬虫
        manager.start_crawler(crawler_id)
        
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
                    
                time.sleep(5)  # 由于Firecrawl是云服务，我们设置更长的检查间隔
            
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
    parser = argparse.ArgumentParser(description="Firecrawl爬虫演示")
    parser.add_argument("url", help="要爬取的网站URL")
    parser.add_argument("--id", dest="crawler_id", default="firecrawl_demo", help="爬虫ID")
    parser.add_argument("--api-key", dest="api_key", help="Firecrawl API密钥")
    parser.add_argument("--max-pages", dest="max_pages", type=int, default=10, help="最大爬取页面数")
    parser.add_argument("--max-depth", dest="max_depth", type=int, default=2, help="最大爬取深度")
    parser.add_argument("--formats", nargs="+", default=["markdown"], 
                      choices=["markdown", "html", "text"], help="输出格式")
    parser.add_argument("--no-wait", dest="wait", action="store_false", help="不等待爬虫完成")
    
    args = parser.parse_args()
    
    # 运行爬虫
    run_crawler(
        url=args.url,
        crawler_id=args.crawler_id,
        api_key=args.api_key,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        formats=args.formats,
        wait=args.wait
    )

if __name__ == "__main__":
    main() 